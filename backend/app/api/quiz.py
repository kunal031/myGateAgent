import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
import json
from datetime import datetime
from ..core.auth import current_user
from ..core.database import get_db
from ..models.models import Question, Subject, Topic, Attempt, MistakeRegistry

from ..models.users import User
from ..services.activity import record

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/quiz", tags=["Quiz"])

class AnswerSubmission(BaseModel):
    question_id: int
    user_answer: str
    time_spent_seconds: int = 0
    mode: str = "quiz"

@router.get("")
def get_quiz_questions(
    subject_slug: Optional[str] = None,
    topic_slug: Optional[str] = None,
    question_type: Optional[str] = None,
    difficulty: Optional[str] = None,
    limit: int = Query(default=10, le=50),
    db: Session = Depends(get_db),
    _user: User = Depends(current_user),
):
    # Explicit ON clauses: a bare .join(Subject).join(Topic) makes SQLAlchemy
    # join topics to subjects (via Subject.topics) instead of to questions,
    # producing a cartesian product.
    query = (
        db.query(Question)
        .join(Subject, Question.subject_id == Subject.id)
        .join(Topic, Question.topic_id == Topic.id)
    )
    
    if subject_slug and subject_slug != "all":
        query = query.filter(Subject.slug == subject_slug)
    if topic_slug and topic_slug != "all":
        query = query.filter(Topic.slug == topic_slug)
    if question_type and question_type != "all":
        query = query.filter(Question.question_type == question_type)
    if difficulty and difficulty != "all":
        query = query.filter(Question.difficulty == difficulty)
        
    questions = query.limit(limit).all()
    
    result = []
    for q in questions:
        opts = json.loads(q.options) if q.options else None
        result.append({
            "id": q.id,
            "subject_name": q.subject.name,
            "subject_slug": q.subject.slug,
            # Chapter sits between subject and topic; practice shows the
            # full path so a question's place in the syllabus is visible.
            "chapter_name": q.topic.chapter.name if q.topic.chapter else None,
            "topic_name": q.topic.name,
            "topic_slug": q.topic.slug,
            "question_type": q.question_type,
            "marks": q.marks,
            "negative_marks": q.negative_marks,
            "content": q.content,
            "options": opts,
            "difficulty": q.difficulty,
            "source": q.source,
            "is_pyq": q.is_pyq,
            "exam_year": q.exam_year,
            "exam_set": q.exam_set,
        })
    return result

@router.post("/submit")
def submit_answer(payload: AnswerSubmission, db: Session = Depends(get_db),
                  user: User = Depends(current_user)):
    q = db.query(Question).filter(Question.id == payload.question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
        
    user_ans = payload.user_answer.strip()
    is_correct = False
    marks_awarded = 0.0
    
    if q.question_type == "MCQ":
        # Direct option matching (e.g. "A", "B", "C", "D")
        is_correct = (user_ans.upper() == q.correct_answer.strip().upper())
        if is_correct:
            marks_awarded = float(q.marks)
        else:
            marks_awarded = -float(q.negative_marks)
            
    elif q.question_type == "MSQ":
        # All correct options required. Compare sorted sets (e.g. "B,C,D")
        correct_tokens = sorted([t.strip().upper() for t in q.correct_answer.split(",") if t.strip()])
        user_tokens = sorted([t.strip().upper() for t in user_ans.split(",") if t.strip()])
        is_correct = (correct_tokens == user_tokens)
        if is_correct:
            marks_awarded = float(q.marks)
        else:
            marks_awarded = 0.0  # GATE has 0 negative marks for MSQ
            
    elif q.question_type == "NAT":
        # Numerical tolerance checking
        try:
            val = float(user_ans)
            if q.nat_min is not None and q.nat_max is not None:
                is_correct = (q.nat_min <= val <= q.nat_max)
            else:
                is_correct = (val == float(q.correct_answer))
        except ValueError:
            is_correct = False
            
        if is_correct:
            marks_awarded = float(q.marks)
        else:
            marks_awarded = 0.0  # GATE has 0 negative marks for NAT
            
    # Record attempt
    attempt = Attempt(
        question_id=q.id,
        user_id=user.id,
        user_answer=user_ans,
        is_correct=is_correct,
        marks_obtained=marks_awarded,
        time_spent_seconds=payload.time_spent_seconds,
        mode=payload.mode,
        created_at=datetime.utcnow()
    )
    db.add(attempt)

    # Same transaction as the attempt: either both land or neither does,
    # so the log cannot claim an answer that was rolled back.
    record.record_attempt(
        db, user_id=user.id, question=q, is_correct=is_correct,
        marks=marks_awarded, seconds=payload.time_spent_seconds,
        mode=payload.mode,
    )

    # Update MistakeRegistry
    if not is_correct:
        mistake = db.query(MistakeRegistry).filter(
            MistakeRegistry.question_id == q.id,
            MistakeRegistry.user_id == user.id,
        ).first()
        if mistake:
            mistake.error_count += 1
            mistake.last_user_answer = user_ans
            mistake.last_attempted_at = datetime.utcnow()
            mistake.mastery_level = max(0, mistake.mastery_level - 1)
        else:
            mistake = MistakeRegistry(
                question_id=q.id,
                user_id=user.id,
                topic_id=q.topic_id,
                subject_id=q.subject_id,
                error_count=1,
                last_user_answer=user_ans,
                mastery_level=0,
                last_attempted_at=datetime.utcnow()
            )
            db.add(mistake)
    else:
        # If user gets it right now, improve mastery level
        mistake = db.query(MistakeRegistry).filter(
            MistakeRegistry.question_id == q.id,
            MistakeRegistry.user_id == user.id,
        ).first()
        if mistake:
            mistake.mastery_level = min(5, mistake.mastery_level + 1)
            
    db.commit()
    
    return {
        "is_correct": is_correct,
        "marks_awarded": marks_awarded,
        "correct_answer": q.correct_answer,
        "explanation": q.explanation,
        "question_type": q.question_type,
        "source": q.source
    }


@router.get("/{question_id}/solution")
def get_solution(question_id: int, db: Session = Depends(get_db),
                 user: User = Depends(current_user)):
    """The worked solution for a question, once it has been attempted.

    Solutions are review material: seeing one before answering turns a drill
    into reading. The endpoint therefore refuses until an attempt exists,
    which is also what the UI keys the "Show solution" control off.
    """
    question = db.query(Question).filter(Question.id == question_id).first()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    attempts = (
        db.query(Attempt)
        .filter(Attempt.question_id == question_id,
                Attempt.user_id == user.id)
        .order_by(Attempt.created_at.desc())
        .all()
    )
    if not attempts:
        raise HTTPException(
            status_code=409,
            detail="Attempt this question before viewing its solution.",
        )

    return {
        "question_id": question.id,
        "question_type": question.question_type,
        "correct_answer": question.correct_answer,
        "solution": question.explanation,
        "has_worked_solution": "not available" not in question.explanation.lower(),
        "source": question.source,
        "exam_year": question.exam_year,
        "provenance": question.provenance or "",
        "attempts": [
            {
                "user_answer": a.user_answer,
                "is_correct": a.is_correct,
                "marks_obtained": a.marks_obtained,
                "time_spent_seconds": a.time_spent_seconds,
                "mode": a.mode,
                "attempted_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in attempts
        ],
    }


@router.get("/review/mistakes")
def review_mistakes(
    limit: int = Query(default=20, le=100),
    subject_slug: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Questions answered wrong, newest first, for post-quiz analysis.

    This is the list the analytics page drills into: every entry already has
    an attempt, so its solution is viewable.
    """
    query = (
        db.query(MistakeRegistry, Question, Subject, Topic)
        .filter(MistakeRegistry.user_id == user.id)
        .join(Question, MistakeRegistry.question_id == Question.id)
        .join(Subject, Question.subject_id == Subject.id)
        .join(Topic, Question.topic_id == Topic.id)
    )
    if subject_slug and subject_slug != "all":
        query = query.filter(Subject.slug == subject_slug)

    rows = query.order_by(MistakeRegistry.last_attempted_at.desc()).limit(limit).all()

    return [
        {
            "question_id": question.id,
            "content": question.content,
            "question_type": question.question_type,
            "marks": question.marks,
            "subject_name": subject.name,
            "topic_name": topic.name,
            "exam_year": question.exam_year,
            "correct_answer": question.correct_answer,
            "last_user_answer": mistake.last_user_answer,
            "error_count": mistake.error_count,
            "mastery_level": mistake.mastery_level,
            "has_worked_solution": "not available" not in question.explanation.lower(),
        }
        for mistake, question, subject, topic in rows
    ]


class GenerateSolutionRequest(BaseModel):
    """Nothing to send; the question id is in the path."""


@router.post("/{question_id}/solution/generate")
def generate_solution(question_id: int, db: Session = Depends(get_db),
                      user: User = Depends(current_user)):
    """Write a solution for a question that has none.

    Only 753 of 1,953 questions carry an explanation, so "no solution
    recorded" is the common case and the student is told so plainly. This
    is the opt-in escape: they ask, and one is generated.

    Deliberately routed to the fallback provider rather than Gemini. The
    free Gemini key is the one that returns 429 and that the feed, the
    assistant and card generation all depend on; spending it on a
    solution the student asked for mid-practice would starve the paths
    they did not ask about. The fallback answers in about a second and
    has its own budget.

    Refuses before an attempt exists, for the same reason the solution
    endpoint does: reading the answer first turns practice into reading.
    """
    question = db.query(Question).filter(Question.id == question_id).first()
    if question is None:
        raise HTTPException(404, "Question not found")

    attempted = (
        db.query(Attempt.id)
        .filter(Attempt.question_id == question_id,
                Attempt.user_id == user.id)
        .first()
    )
    if not attempted:
        raise HTTPException(
            409, "Attempt this question before generating its solution.")

    if (question.explanation or "").strip():
        # Already has one; hand it back rather than spending a call to
        # produce a second opinion.
        return {
            "question_id": question_id,
            "explanation": question.explanation,
            "solution_source": question.solution_source or "book",
            "generated": False,
        }

    from ..ai import fallback

    if not fallback.configured():
        raise HTTPException(
            503,
            "No solution is recorded for this question, and no fallback "
            "model is configured to generate one.",
        )

    options = ""
    if question.options:
        try:
            parsed = json.loads(question.options)
            options = "\n".join(
                f"{o.get('id')}. {o.get('text')}" for o in parsed
            )
        except (ValueError, TypeError, AttributeError):
            options = ""

    prompt = (
        f"GATE CSE question on {question.subject.name} / "
        f"{question.topic.name}.\n\n"
        f"{question.content}\n\n{options}\n\n"
        f"The correct answer is: {question.correct_answer}\n\n"
        "Explain why, in under 150 words. Show the reasoning or working "
        "that leads to it. Do not restate the question."
    )

    try:
        text_out = fallback.generate_text(
            prompt,
            system_instruction=(
                "You are a GATE CSE tutor. Be precise and brief. State the "
                "reasoning, not encouragement."
            ),
        )
    except Exception as exc:
        logger.warning("Solution generation failed for %s: %s",
                       question_id, exc)
        raise HTTPException(
            502, "Could not generate a solution just now.") from exc

    question.explanation = text_out
    question.solution_source = "ai"
    db.commit()

    return {
        "question_id": question_id,
        "explanation": text_out,
        "solution_source": "ai",
        "generated": True,
    }
