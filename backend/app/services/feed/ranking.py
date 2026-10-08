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

from ...models.concepts import Concept, StudyMode
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
    mode: str | None = None,
    topic_slug: str | None = None,
    offset: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
) -> FeedPage:
    """One ranked page of the feed.

    In BASIC mode the order is pedagogical, not by rank: concepts are walked
    in their teaching sequence so a chapter is met from the beginning. In
    ADVANCED and unfiltered views, mistake-weighted ranking takes over, which
    is what surfaces weak topics first.
    """
    limit = max(1, min(limit, MAX_PAGE_SIZE))
    mistakes = _mistake_weight_subquery()

    errors = func.coalesce(mistakes.c.errors, 0)
    weight = (FeedCard.base_weight + errors * MISTAKE_BOOST).label("weight")

    query = (
        db.query(FeedCard, Subject, Topic, errors.label("errors"), weight)
        .join(Subject, FeedCard.subject_id == Subject.id)
        .join(Topic, FeedCard.topic_id == Topic.id)
        .outerjoin(mistakes, mistakes.c.topic_id == FeedCard.topic_id)
        .outerjoin(Concept, FeedCard.concept_id == Concept.id)
    )

    if subject_slug and subject_slug != "all":
        query = query.filter(Subject.slug == subject_slug)
    if topic_slug and topic_slug != "all":
        query = query.filter(Topic.slug == topic_slug)
    if card_type and card_type != "all":
        query = query.filter(FeedCard.card_type == card_type)
    if mode and mode != "all":
        query = query.filter(FeedCard.mode == mode)

    total = query.count()

    if mode == StudyMode.BASIC:
        # Teaching order: concept sequence, then card sequence within it.
        ordering = (Concept.sequence.asc(), FeedCard.sequence.asc(), FeedCard.id.asc())
    else:
        ordering = (weight.desc(), FeedCard.id.asc())

    rows = query.order_by(*ordering).offset(offset).limit(limit).all()

    items = [
        {
            "id": card.id,
            "subject_name": subject.name,
            "subject_slug": subject.slug,
            "topic_name": topic.name,
            "topic_slug": topic.slug,
            "card_type": card.card_type,
            "mode": card.mode,
            "concept_id": card.concept_id,
            "provenance": card.provenance or "",
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
