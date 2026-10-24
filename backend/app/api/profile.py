"""The profile: who you are, what you have done, and changing both.

Three endpoints behind one screen. `/me/stats` is read-only and gathers
the numbers the profile shows; `/me` updates the editable fields; and
`/me/password` changes the password.

Password change is the security-sensitive one, so it does three things
beyond writing the new hash:

* requires the current password, even though the caller is already
  authenticated -- an access token can be lifted from a shared machine,
  and without this check that is enough to lock the owner out;
* bumps `token_version`, which invalidates every refresh token, so a
  change made because of a suspected compromise actually ends the other
  sessions rather than leaving them running for 30 days;
* refuses on a Google-only account, which has no current password to
  verify -- that path sets a password instead.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from ..core.auth import current_user
from ..core.database import get_db
from ..core.security import (
    MIN_PASSWORD_CHARS, create_access_token, create_refresh_token,
    hash_password, verify_password,
)
from ..models.activity import ActivityEvent, ActivityKind
from ..models.concepts import ConceptProgress, ConceptStatus
from ..models.exams import ExamSession
from ..models.models import Attempt, MistakeRegistry, Question
from ..models.rotation import CardView
from ..models.users import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/profile", tags=["Profile"])


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    # Not validated as a phone number: formats vary by country and a
    # strict pattern rejects legitimate input. It is a display label.
    phone: str | None = Field(default=None, max_length=32)


class PasswordChange(BaseModel):
    current_password: str = ""
    new_password: str = Field(min_length=MIN_PASSWORD_CHARS)


def _public(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name or "",
        "phone": user.phone or "",
        "role": user.role,
        "avatar_url": user.avatar_url or None,
        "has_password": user.has_password,
        "google_linked": bool(user.google_sub),
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login_at": (
            user.last_login_at.isoformat() if user.last_login_at else None
        ),
    }


@router.get("/me")
def get_profile(user: User = Depends(current_user)):
    """The account's own details."""
    return _public(user)


@router.patch("/me")
def update_profile(payload: ProfileUpdate,
                   db: Session = Depends(get_db),
                   user: User = Depends(current_user)):
    """Change the editable fields.

    Email is not editable here. It is the key Google sign-in links on, so
    changing it would silently detach the Google identity from the account
    and create a second one on the next sign-in.
    """
    if payload.display_name is not None:
        user.display_name = payload.display_name.strip()[:120]
    if payload.phone is not None:
        user.phone = payload.phone.strip()[:32] or None
    db.commit()
    db.refresh(user)
    return _public(user)


@router.post("/me/password")
def change_password(payload: PasswordChange,
                    db: Session = Depends(get_db),
                    user: User = Depends(current_user)):
    """Set or change the password.

    Returns fresh tokens, because bumping `token_version` invalidates the
    caller's own refresh token along with everyone else's -- without new
    ones the user would be signed out by the act of changing their
    password.
    """
    if user.has_password:
        # Required even though the caller holds a valid token: a token
        # taken from an unlocked machine would otherwise be enough to
        # change the password and lock the owner out.
        if not verify_password(payload.current_password,
                               user.password_hash or ""):
            raise HTTPException(403, "That current password is not correct")
    elif payload.current_password:
        # A Google-only account has none; a supplied value means the user
        # thinks they have one, which is worth saying rather than ignoring.
        raise HTTPException(
            400,
            "This account signs in with Google and has no password yet. "
            "Leave the current password blank to set one.",
        )

    try:
        new_hash = hash_password(payload.new_password)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    if user.password_hash and verify_password(payload.new_password,
                                              user.password_hash):
        raise HTTPException(400, "That is already your current password")

    user.password_hash = new_hash
    user.token_version = (user.token_version or 0) + 1
    db.commit()
    db.refresh(user)

    logger.info("Password changed for user %s", user.id)
    return {
        "user": _public(user),
        "access_token": create_access_token(user.id, user.role),
        "refresh_token": create_refresh_token(user.id, user.token_version),
        "token_type": "bearer",
    }


@router.get("/me/stats")
def profile_stats(db: Session = Depends(get_db),
                  user: User = Depends(current_user)):
    """The numbers shown on the profile.

    Deliberately a single endpoint rather than letting the profile screen
    assemble this from four others: it is one screen, and four round trips
    on a phone connection is four chances to render half a profile.
    """
    mine = Attempt.user_id == user.id

    attempts = db.query(func.count(Attempt.id)).filter(mine).scalar() or 0
    correct = (
        db.query(func.count(Attempt.id))
        .filter(mine, Attempt.is_correct.is_(True))
        .scalar() or 0
    )
    distinct_questions = (
        db.query(func.count(func.distinct(Attempt.question_id)))
        .filter(mine).scalar() or 0
    )
    marks = db.query(func.sum(Attempt.marks_obtained)).filter(mine).scalar()
    seconds = (
        db.query(func.sum(Attempt.time_spent_seconds)).filter(mine).scalar() or 0
    )

    # By question type, since GATE's negative marking differs per type and
    # a weakness in one is a different problem from a weakness in another.
    by_type = [
        {
            "question_type": qtype,
            "attempts": int(total or 0),
            "correct": int(ok or 0),
            "accuracy": (
                round(int(ok or 0) / int(total) * 100, 1) if total else None
            ),
        }
        for qtype, total, ok in (
            db.query(
                Question.question_type,
                func.count(Attempt.id),
                func.sum(case((Attempt.is_correct, 1), else_=0)),
            )
            .join(Attempt, Attempt.question_id == Question.id)
            .filter(mine)
            .group_by(Question.question_type)
            .all()
        )
    ]

    concepts = {
        status: count
        for status, count in (
            db.query(ConceptProgress.status, func.count(ConceptProgress.id))
            .filter(ConceptProgress.user_id == user.id)
            .group_by(ConceptProgress.status)
            .all()
        )
    }
    learned = sum(
        concepts.get(s, 0)
        for s in (ConceptStatus.LEARNED, ConceptStatus.REVISED,
                  ConceptStatus.MASTERED)
    )

    sessions = (
        db.query(
            ExamSession.kind,
            func.count(ExamSession.id),
            func.sum(ExamSession.score),
            func.max(ExamSession.score),
            func.avg(ExamSession.accuracy),
        )
        .filter(ExamSession.user_id == user.id,
                ExamSession.status == "submitted")
        .group_by(ExamSession.kind)
        .all()
    )

    cards = db.query(
        func.count(CardView.id),
        func.sum(CardView.seen_count),
        func.count(CardView.id).filter(CardView.mastered.is_(True)),
    ).filter(CardView.user_id == user.id).first()

    active_days = (
        db.query(func.count(func.distinct(func.date(ActivityEvent.created_at))))
        .filter(ActivityEvent.user_id == user.id,
                ActivityEvent.kind.in_(ActivityKind.COUNTS_AS_STUDY))
        .scalar() or 0
    )

    return {
        "questions": {
            "attempted": int(attempts),
            "distinct": int(distinct_questions),
            "correct": int(correct),
            "wrong": int(attempts) - int(correct),
            "accuracy": (
                round(int(correct) / int(attempts) * 100, 1) if attempts else None
            ),
            "marks_earned": round(float(marks or 0.0), 2),
            "minutes_spent": round(int(seconds) / 60, 1),
            "by_type": by_type,
        },
        "concepts": {
            "learned": learned,
            "learning": concepts.get(ConceptStatus.LEARNING, 0),
            "mastered": concepts.get(ConceptStatus.MASTERED, 0),
            "touched": sum(concepts.values()),
        },
        "cards": {
            "seen": int(cards[0] or 0) if cards else 0,
            "views": int(cards[1] or 0) if cards else 0,
            "mastered": int(cards[2] or 0) if cards else 0,
        },
        "tests": [
            {
                "kind": kind,
                "submitted": int(count or 0),
                "total_score": round(float(total or 0.0), 2),
                "best_score": round(float(best or 0.0), 2),
                "avg_accuracy": round(float(avg_acc or 0.0), 1),
            }
            for kind, count, total, best, avg_acc in sessions
        ],
        "open_mistakes": (
            db.query(func.count(MistakeRegistry.id))
            .filter(MistakeRegistry.user_id == user.id,
                    MistakeRegistry.mastery_level < 3)
            .scalar() or 0
        ),
        "active_days": int(active_days),
    }
