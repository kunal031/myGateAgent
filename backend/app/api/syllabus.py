from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..models.models import Subject, Topic, Question

router = APIRouter(prefix="/api/syllabus", tags=["Syllabus"])

@router.get("")
def get_full_syllabus(db: Session = Depends(get_db)):
    subjects = db.query(Subject).all()
    result = []
    for s in subjects:
        topics = db.query(Topic).filter(Topic.subject_id == s.id).all()
        q_count = db.query(Question).filter(Question.subject_id == s.id).count()
        result.append({
            "id": s.id,
            "name": s.name,
            "slug": s.slug,
            "icon": s.icon,
            "description": s.description,
            "weightage_marks": s.weightage_marks,
            "question_count": q_count,
            "topics": [
                {
                    "id": t.id,
                    "name": t.name,
                    "slug": t.slug,
                    "importance": t.importance
                }
                for t in topics
            ]
        })
    return result
