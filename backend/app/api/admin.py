"""Who is using this instance, and how.

Admin-only. Every route here reads another account's data, so the guard
is admin_user rather than current_user -- the distinction the rest of
the API makes between "signed in" and "allowed to see everyone" matters
most here.

The per-user analytics reuse services/analytics wholesale rather than
writing admin copies of the same queries. Those functions already take a
user_id and are already scoped by it; a second implementation would be
one more place for the scoping to drift.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.auth import admin_user
from ..core.database import get_db
from ..models.models import Attempt, FeedCard
from ..models.users import User

router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.get("/users")
def list_users(db: Session = Depends(get_db), _admin: User = Depends(admin_user)):
    """Every account, with enough activity to tell them apart.

    The counts are three grouped queries rather than per-user lookups:
    one row per user in the list meant N+1 on a page whose whole purpose
    is to show all of them at once.
    """
    users = db.query(User).order_by(User.created_at.desc()).all()
    if not users:
        return {"items": [], "total": 0}

    attempts = dict(
        db.query(Attempt.user_id, func.count(Attempt.id))
        .group_by(Attempt.user_id).all()
    )
    correct = dict(
        db.query(Attempt.user_id, func.count(Attempt.id))
        .filter(Attempt.is_correct.is_(True))
        .group_by(Attempt.user_id).all()
    )
    cards = dict(
        db.query(FeedCard.user_id, func.count(FeedCard.id))
        .filter(FeedCard.user_id.isnot(None))
        .group_by(FeedCard.user_id).all()
    )

    week_ago = datetime.utcnow() - timedelta(days=7)
    recent = dict(
        db.query(Attempt.user_id, func.count(Attempt.id))
        .filter(Attempt.created_at >= week_ago)
        .group_by(Attempt.user_id).all()
    )

    items = []
    for u in users:
        total = attempts.get(u.id, 0)
        right = correct.get(u.id, 0)
        items.append({
            "id": u.id,
            "email": u.email,
            "display_name": u.display_name or "",
            "role": u.role,
            "is_active": u.is_active,
            "avatar_url": u.avatar_url or None,
            # How they sign in, which is the first thing to check when
            # someone cannot get in.
            "has_password": bool(u.password_hash),
            "google_linked": bool(u.google_sub),
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_login_at": (
                u.last_login_at.isoformat() if u.last_login_at else None
            ),
            "attempts": total,
            "correct": right,
            # None rather than 0 for an account that has answered
            # nothing: 0% reads as "got everything wrong".
            "accuracy": round(right / total * 100, 1) if total else None,
            "cards_written": cards.get(u.id, 0),
            "attempts_last_7d": recent.get(u.id, 0),
        })

    return {"items": items, "total": len(items)}


@router.get("/users/{user_id}")
def user_detail(user_id: int, db: Session = Depends(get_db),
                _admin: User = Depends(admin_user)):
    """One account's analytics, for the drill-down on a row.

    Built from the same services the student's own analytics page uses,
    so the numbers an admin sees are by construction the numbers that
    student sees.
    """
    from ..services.analytics import performance as perf

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(404, "No such user")

    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name or "",
            "role": user.role,
            "is_active": user.is_active,
            "avatar_url": user.avatar_url or None,
            "has_password": bool(user.password_hash),
            "google_linked": bool(user.google_sub),
            "created_at": (
                user.created_at.isoformat() if user.created_at else None
            ),
            "last_login_at": (
                user.last_login_at.isoformat() if user.last_login_at else None
            ),
        },
        "coverage": perf.coverage(db, user_id),
        "readiness": perf.exam_readiness(db, user_id),
        "by_question_type": perf.accuracy_by_question_type(db, user_id),
        "weak_topics": perf.weak_topics(db, user_id, limit=8),
        "retention": perf.retention(db, user_id),
        "daily_activity": perf.daily_activity(db, user_id, days=30),
    }
