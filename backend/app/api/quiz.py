from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
import json
from datetime import datetime
from ..core.database import get_db
from ..models.models import Question, Subject, Topic, Attempt, MistakeRegistry

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
    db: Session = Depends(get_db)
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
            "topic_name": q.topic.name,
            "topic_slug": q.topic.slug,
            "question_type": q.question_type,
            "marks": q.marks,
            "negative_marks": q.negative_marks,
            "content": q.content,
            "options": opts,
            "difficulty": q.difficulty,
            "source": q.source,
            "is_pyq": q.is_pyq
        })
    return result

@router.post("/submit")
def submit_answer(payload: AnswerSubmission, db: Session = Depends(get_db)):
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
        user_answer=user_ans,
        is_correct=is_correct,
        marks_obtained=marks_awarded,
        time_spent_seconds=payload.time_spent_seconds,
        mode=payload.mode,
        created_at=datetime.utcnow()
    )
    db.add(attempt)
    
    # Update MistakeRegistry
    if not is_correct:
        mistake = db.query(MistakeRegistry).filter(MistakeRegistry.question_id == q.id).first()
        if mistake:
            mistake.error_count += 1
            mistake.last_user_answer = user_ans
            mistake.last_attempted_at = datetime.utcnow()
            mistake.mastery_level = max(0, mistake.mastery_level - 1)
        else:
            mistake = MistakeRegistry(
                question_id=q.id,
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
        mistake = db.query(MistakeRegistry).filter(MistakeRegistry.question_id == q.id).first()
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
