from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..models.models import Subject, Topic, Question
from ..services.feed.tagging import slugify

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


class TopicInput(BaseModel):
    subject_slug: str
    name: str
    importance: str = "High"


@router.post("/topics", status_code=201)
def create_topic(payload: TopicInput, db: Session = Depends(get_db)):
    """Add a topic to a subject.

    Topics were seed-only, which made the syllabus a fixed list: importing a
    paper on a topic the seeds never named had nowhere to put it, and the
    one existing importer worked around that by falling back to the
    subject's first topic -- which is how 51 Operating Systems questions all
    ended up filed under Process Synchronization.
    """
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "A topic needs a name")

    subject = db.query(Subject).filter(Subject.slug == payload.subject_slug).first()
    if subject is None:
        raise HTTPException(404, f"No subject {payload.subject_slug!r}")

    slug = slugify(name)
    if not slug:
        raise HTTPException(400, "That name has no usable characters")

    existing = (
        db.query(Topic)
        .filter(Topic.subject_id == subject.id, Topic.slug == slug)
        .first()
    )
    if existing is not None:
        # Returned rather than refused: the caller wants a topic to file
        # against, and one already exists under that name.
        return {
            "id": existing.id, "name": existing.name, "slug": existing.slug,
            "importance": existing.importance, "created": False,
        }

    topic = Topic(
        subject_id=subject.id, name=name[:150], slug=slug,
        importance=payload.importance,
    )
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return {
        "id": topic.id, "name": topic.name, "slug": topic.slug,
        "importance": topic.importance, "created": True,
    }
