from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..core.database import get_db
from ..models.models import Attempt, MistakeRegistry, Subject, Topic, Question

router = APIRouter(prefix="/api/stats", tags=["Stats"])

@router.get("/summary")
def get_stats_summary(db: Session = Depends(get_db)):
    total_attempts = db.query(Attempt).count()
    correct_attempts = db.query(Attempt).filter(Attempt.is_correct == True).count()
    accuracy = (correct_attempts / total_attempts * 100) if total_attempts > 0 else 0.0
    
    total_marks_earned = db.query(func.sum(Attempt.marks_obtained)).scalar() or 0.0
    active_mistakes_count = db.query(MistakeRegistry).filter(MistakeRegistry.mastery_level < 3).count()
    
    # Subject breakdown
    subjects = db.query(Subject).all()
    subject_stats = []
    
    for s in subjects:
        sub_attempts = db.query(Attempt).join(Question).filter(Question.subject_id == s.id).all()
        sub_total = len(sub_attempts)
        sub_correct = sum(1 for a in sub_attempts if a.is_correct)
        sub_acc = (sub_correct / sub_total * 100) if sub_total > 0 else 0.0
        sub_marks = sum(a.marks_obtained for a in sub_attempts)
        
        # Count unresolved mistakes in this subject
        sub_mistakes = db.query(MistakeRegistry).filter(
            MistakeRegistry.subject_id == s.id,
            MistakeRegistry.mastery_level < 3
        ).count()
        
        subject_stats.append({
            "subject_id": s.id,
            "subject_name": s.name,
            "subject_slug": s.slug,
            "weightage_marks": s.weightage_marks,
            "attempts": sub_total,
            "accuracy": round(sub_acc, 1),
            "marks_earned": round(sub_marks, 2),
            "unresolved_mistakes": sub_mistakes
        })
        
    return {
        "total_attempts": total_attempts,
        "correct_attempts": correct_attempts,
        "accuracy": round(accuracy, 1),
        "total_marks_earned": round(total_marks_earned, 2),
        "active_mistakes_count": active_mistakes_count,
        "subject_stats": subject_stats
    }
