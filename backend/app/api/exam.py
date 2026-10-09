"""Mock test endpoints: configure, sit, submit, and review."""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.exams import ExamSession, ExamStatus
from ..models.models import Subject, Topic
from ..services.exam import patterns as pattern_defs
from ..services.exam.session import (
    NotEnoughQuestions, create_session, save_answer, submit_session, visit_item,
)

router = APIRouter(prefix="/api/exam", tags=["Mock Test"])


class StartRequest(BaseModel):
    pattern: str = "full"                  # full, subject, custom, topic
    subject_slug: str | None = None
    subject_slugs: list[str] | None = None
    topic_slug: str | None = None
    question_type: str | None = None       # MCQ, MSQ, NAT, all
    difficulty: str | None = None
    questions: int = 20
    duration_minutes: int = 45
    name: str | None = None
    kind: str = "test"                     # test or quiz


class AnswerRequest(BaseModel):
    answer: str | None = None
    marked: bool | None = None
    time_spent_seconds: int | None = None


@router.get("/patterns")
def list_patterns(db: Session = Depends(get_db)):
    """Presets and the subjects available, for the pattern setter."""
    from ..models.models import Question

    subjects = []
    for subject in db.query(Subject).order_by(Subject.weightage_marks.desc()).all():
        count = db.query(Question).filter(Question.subject_id == subject.id).count()
        subjects.append({
            "slug": subject.slug,
            "name": subject.name,
            "weightage_marks": subject.weightage_marks,
            "question_count": count,
        })

    return {
        "presets": [
            {
                "key": p.key,
                "name": p.name,
                "total_questions": p.total_questions,
                "total_marks": p.total_marks,
                "duration_minutes": p.duration_minutes,
            }
            for p in pattern_defs.PRESETS.values()
        ],
        "subjects": subjects,
        "total_questions_available": db.query(Question).count(),
    }


@router.post("/start")
def start_exam(payload: StartRequest, db: Session = Depends(get_db)):
    """Assemble a paper and open a session (quiz or test)."""
    subject_id = None
    topic_id = None

    if payload.pattern == "full":
        pattern = pattern_defs.FULL_GATE
    elif payload.pattern == "topic":
        if not payload.topic_slug:
            raise HTTPException(400, "topic_slug is required for a topic drill")
        topic = db.query(Topic).filter(Topic.slug == payload.topic_slug).first()
        if topic is None:
            raise HTTPException(404, f"No topic {payload.topic_slug!r}")
        topic_id = topic.id
        subject_id = topic.subject_id
        subject = db.query(Subject).filter(Subject.id == subject_id).first()
        pattern = pattern_defs.topic_drill(
            subject.slug, payload.questions, payload.duration_minutes)
    elif payload.pattern == "subject":
        if not payload.subject_slug:
            raise HTTPException(400, "subject_slug is required for a subject sprint")
        subject = db.query(Subject).filter(Subject.slug == payload.subject_slug).first()
        if subject is None:
            raise HTTPException(404, f"No subject {payload.subject_slug!r}")
        subject_id = subject.id
        pattern = pattern_defs.subject_sprint(
            payload.subject_slug, payload.questions, payload.duration_minutes)
    else:
        slugs = payload.subject_slugs or []
        pattern = pattern_defs.custom_mix(
            slugs, payload.questions, payload.duration_minutes)

    try:
        session = create_session(
            db, pattern, name=payload.name, subject_id=subject_id,
            topic_id=topic_id, kind=payload.kind,
            question_type=payload.question_type, difficulty=payload.difficulty,
        )
    except NotEnoughQuestions as exc:
        raise HTTPException(409, str(exc)) from exc

    return _session_summary(session)


@router.get("/{session_id}")
def get_exam(session_id: int, db: Session = Depends(get_db)):
    """The full paper plus palette state, for rendering the exam screen.

    Correct answers are deliberately absent: the client never holds the key
    while the session is open.
    """
    session = _require_session(db, session_id)

    questions = []
    for item in session.items:
        question = item.question
        questions.append({
            "position": item.position,
            "question_id": question.id,
            "question_type": question.question_type,
            "marks": question.marks,
            "negative_marks": question.negative_marks,
            "content": question.content,
            "options": json.loads(question.options) if question.options else None,
            "subject_name": question.subject.name if question.subject else "",
            "state": item.state,
            "user_answer": item.user_answer or "",
            "time_spent_seconds": item.time_spent_seconds,
        })

    summary = _session_summary(session)
    summary["questions"] = questions
    return summary


@router.post("/{session_id}/visit/{position}")
def visit(session_id: int, position: int, db: Session = Depends(get_db)):
    _require_session(db, session_id)
    item = visit_item(db, session_id, position)
    if item is None:
        raise HTTPException(404, "No such question in this session")
    return {"position": item.position, "state": item.state}


@router.post("/{session_id}/answer/{position}")
def answer(session_id: int, position: int, payload: AnswerRequest,
           db: Session = Depends(get_db)):
    """Save an answer and/or the review flag. An empty answer clears it."""
    session = _require_session(db, session_id)
    if not session.is_open:
        raise HTTPException(409, "This session has already been submitted")

    item = save_answer(
        db, session_id, position,
        answer=payload.answer, marked=payload.marked,
        time_spent_seconds=payload.time_spent_seconds,
    )
    if item is None:
        raise HTTPException(404, "No such question in this session")
    return {"position": item.position, "state": item.state,
            "user_answer": item.user_answer}


@router.post("/{session_id}/submit")
def submit(session_id: int, db: Session = Depends(get_db)):
    session = _require_session(db, session_id)
    if not session.is_open:
        return _session_summary(session)
    return _session_summary(submit_session(db, session_id))


@router.get("/{session_id}/result")
def result(session_id: int, db: Session = Depends(get_db)):
    """Per-question outcome for a submitted paper, for analysis."""
    session = _require_session(db, session_id)
    if session.is_open:
        raise HTTPException(409, "Submit the session before reviewing it")

    rows = []
    for item in session.items:
        question = item.question
        rows.append({
            "position": item.position,
            "question_id": question.id,
            "question_type": question.question_type,
            "marks": question.marks,
            "subject_name": question.subject.name if question.subject else "",
            "content": question.content,
            "user_answer": item.user_answer or "",
            "correct_answer": question.correct_answer,
            "is_correct": item.is_correct,
            "marks_obtained": item.marks_obtained,
            "time_spent_seconds": item.time_spent_seconds,
            "state": item.state,
            # The solution endpoint serves the worked explanation itself.
            "has_worked_solution": "not available" not in question.explanation.lower(),
        })

    summary = _session_summary(session)
    summary["questions"] = rows
    return summary


@router.get("")
def list_sessions(
    limit: int = Query(default=20, le=100),
    kind: str | None = None,
    subject_slug: str | None = None,
    since: str | None = Query(default=None, description="ISO date, inclusive"),
    db: Session = Depends(get_db),
):
    """Session history, newest first, filterable by kind, subject and date."""
    query = db.query(ExamSession)

    if kind in {"quiz", "test"}:
        query = query.filter(ExamSession.kind == kind)
    if subject_slug and subject_slug != "all":
        subject = db.query(Subject).filter(Subject.slug == subject_slug).first()
        if subject is None:
            return []
        query = query.filter(ExamSession.subject_id == subject.id)
    if since:
        try:
            query = query.filter(ExamSession.started_at >= datetime.fromisoformat(since))
        except ValueError:
            raise HTTPException(400, "since must be an ISO date") from None

    sessions = query.order_by(ExamSession.started_at.desc()).limit(limit).all()
    return [_session_summary(s) for s in sessions]


def _require_session(db: Session, session_id: int) -> ExamSession:
    session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
    if session is None:
        raise HTTPException(404, "No such session")
    return session


def _session_summary(session: ExamSession) -> dict:
    elapsed = 0
    if session.started_at:
        end = session.submitted_at or datetime.utcnow()
        elapsed = int((end - session.started_at).total_seconds())

    return {
        "id": session.id,
        "name": session.name,
        "pattern": session.pattern,
        "status": session.status,
        "total_questions": session.total_questions,
        "total_marks": session.total_marks,
        "duration_minutes": session.duration_minutes,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "submitted_at": (session.submitted_at.isoformat()
                         if session.submitted_at else None),
        "elapsed_seconds": elapsed,
        "remaining_seconds": max(0, session.duration_minutes * 60 - elapsed)
                             if session.is_open else 0,
        "score": session.score,
        "max_score": session.max_score,
        "correct_count": session.correct_count,
        "wrong_count": session.wrong_count,
        "unattempted_count": session.unattempted_count,
        "accuracy": session.accuracy,
        "shortfall_note": session.shortfall_note or "",
    }


@router.post("/{session_id}/check/{position}")
def check_answer(session_id: int, position: int, db: Session = Depends(get_db)):
    """Grade one question immediately. Quiz sessions only.

    This is the difference between the two modes: a quiz gives feedback as
    you go, so the explanation lands while the question is still in mind. A
    test reveals nothing until submission, so this refuses for them.
    """
    from ..models.exams import ExamItem, SessionKind
    from ..services.exam.scoring import score_item

    session = _require_session(db, session_id)
    if session.kind != SessionKind.QUIZ:
        raise HTTPException(409, "Immediate feedback is only available in a quiz")

    item = (
        db.query(ExamItem)
        .filter(ExamItem.session_id == session_id, ExamItem.position == position)
        .first()
    )
    if item is None:
        raise HTTPException(404, "No such question in this session")
    if not item.user_answer:
        raise HTTPException(409, "Answer the question first")

    question = item.question
    is_correct, marks = score_item(question, item.user_answer)

    return {
        "position": item.position,
        "is_correct": is_correct,
        "marks_obtained": marks,
        "correct_answer": question.correct_answer,
        "explanation": question.explanation,
        "provenance": question.provenance or "",
    }
