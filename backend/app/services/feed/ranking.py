"""Feed ranking and pagination, computed in SQL.

The previous implementation loaded every card and every mistake row, ranked
them in Python, then sliced. That re-read the whole table on each request and
could not paginate meaningfully. Ranking now happens in the query, so the
database returns only the page asked for.

Ordering is deterministic (weight, then id) so that paging cannot show the
same card twice or skip one between requests.
"""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...models.models import FeedCard, MistakeRegistry, Subject, Topic

# A wrong answer lifts every card on that topic by this much per error.
MISTAKE_BOOST = 3

DEFAULT_PAGE_SIZE = 18
MAX_PAGE_SIZE = 30


@dataclass
class FeedPage:
    items: list[dict]
    next_offset: int | None
    total: int


def _mistake_weight_subquery():
    """Per-topic error totals, so ranking needs no second query."""
    return (
        select(
            MistakeRegistry.topic_id.label("topic_id"),
            func.coalesce(func.sum(MistakeRegistry.error_count), 0).label("errors"),
        )
        .group_by(MistakeRegistry.topic_id)
        .subquery()
    )


def get_feed_page(
    db: Session,
    *,
    subject_slug: str | None = None,
    card_type: str | None = None,
    offset: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
) -> FeedPage:
    limit = max(1, min(limit, MAX_PAGE_SIZE))
    mistakes = _mistake_weight_subquery()

    errors = func.coalesce(mistakes.c.errors, 0)
    weight = (FeedCard.base_weight + errors * MISTAKE_BOOST).label("weight")

    query = (
        db.query(FeedCard, Subject, Topic, errors.label("errors"), weight)
        .join(Subject, FeedCard.subject_id == Subject.id)
        .join(Topic, FeedCard.topic_id == Topic.id)
        .outerjoin(mistakes, mistakes.c.topic_id == FeedCard.topic_id)
    )

    if subject_slug and subject_slug != "all":
        query = query.filter(Subject.slug == subject_slug)
    if card_type and card_type != "all":
        query = query.filter(FeedCard.card_type == card_type)

    total = query.count()
    rows = (
        query.order_by(weight.desc(), FeedCard.id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = [
        {
            "id": card.id,
            "subject_name": subject.name,
            "subject_slug": subject.slug,
            "topic_name": topic.name,
            "topic_slug": topic.slug,
            "card_type": card.card_type,
            "title": card.title,
            "content": card.content,
            "takeaway": card.takeaway,
            "difficulty": card.difficulty,
            "effective_weight": int(card_weight),
            "is_remedial": int(error_count) > 0,
            "recent_mistakes_in_topic": int(error_count),
        }
        for card, subject, topic, error_count, card_weight in rows
    ]

    consumed = offset + len(items)
    return FeedPage(
        items=items,
        next_offset=consumed if consumed < total else None,
        total=total,
    )
