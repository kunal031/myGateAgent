from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..core.auth import admin_user, current_user
from ..core.cache import delete, get_or_set, key
from ..core.config import settings
from ..core.database import get_db
from ..models.models import Subject, Topic, Question
from ..models.users import User
from ..data.curriculum import sort_subjects, sort_topics
from ..services.feed.tagging import slugify

router = APIRouter(prefix="/api/syllabus", tags=["Syllabus"])

@router.get("")
def get_full_syllabus(db: Session = Depends(get_db),
                      _user: User = Depends(current_user)):
    """The syllabus tree, in study order.

    Everything that lists subjects or topics for a human reads this -- the
    feed filters, the quiz and test pickers, the paper importer -- so the
    order belongs here rather than in each caller. Database order is
    insertion order, which for several subjects ran close to backwards:
    Digital Logic opened on Boolean Algebra rather than Number Systems.
    """
    return get_or_set(
        SYLLABUS_KEY,
        lambda: _build_syllabus(db),
        ttl=settings.CACHE_TTL_SYLLABUS,
    )


#: One shared entry: the tree is identical for every account, so caching
#: it per user would multiply the memory and the misses for no benefit.
SYLLABUS_KEY = key("syllabus")


def _build_syllabus(db: Session) -> list[dict]:
    """Read the tree from the database.

    One query per table rather than per subject. This was 1 + 2N -- a
    topics query and a count query for each of the 11 subjects -- which
    is why it was the endpoint that degraded worst under concurrency.
    """
    subjects = sort_subjects(db.query(Subject).all())

    topics_by_subject: dict[int, list[Topic]] = {}
    for topic in db.query(Topic).all():
        topics_by_subject.setdefault(topic.subject_id, []).append(topic)

    counts = dict(
        db.query(Question.subject_id, func.count(Question.id))
        .group_by(Question.subject_id)
        .all()
    )

    result = []
    for s in subjects:
        topics = sort_topics(s.slug, topics_by_subject.get(s.id, []))
        q_count = counts.get(s.id, 0)
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
def create_topic(payload: TopicInput, db: Session = Depends(get_db),
                 _admin=Depends(admin_user)):
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

    # The cached tree no longer lists every topic. Dropped rather than
    # left to expire: the caller's next read is the paper importer looking
    # for the topic it just created, and an hour-stale tree would not
    # contain it.
    delete(SYLLABUS_KEY)

    return {
        "id": topic.id, "name": topic.name, "slug": topic.slug,
        "importance": topic.importance, "created": True,
    }
