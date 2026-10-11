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


#: How much of the bank to score before laying out a page. Scoring is
#: in-process arithmetic over rows already fetched, so this is cheap; the
#: cap exists so the cost stays flat as the library grows.
SCORING_POOL = 400


def _ready_ordered_rows(db, query, *, offset: int, limit: int):
    """Score a pool of candidates, then lay out one page as a mix.

    Paging is applied after scoring rather than in SQL: the mix is a
    property of the page, and an OFFSET over a ranked list would cut
    through it.
    """
    from .ordering import build_page, score_cards

    pool = query.limit(SCORING_POOL + offset).all()
    if not pool:
        return []

    # FeedCard has no concept relationship, so the concepts are fetched in
    # one query and joined here. Reaching for card.concept would quietly
    # yield None for every card and switch readiness off without a word.
    concept_ids = {c.concept_id for c, *_ in pool if c.concept_id}
    concepts = {
        c.id: c
        for c in db.query(Concept).filter(Concept.id.in_(concept_ids)).all()
    } if concept_ids else {}

    scored = score_cards(
        db,
        [(card, subject, topic, concepts.get(card.concept_id), int(errors or 0))
         for card, subject, topic, errors, _weight in pool],
    )
    page = build_page(scored, offset + limit)[offset:offset + limit]

    chosen = {s.card.id for s in page}
    ordered = {s.card.id: i for i, s in enumerate(page)}
    rows = [r for r in pool if r[0].id in chosen]
    rows.sort(key=lambda r: ordered.get(r[0].id, 0))
    return rows


def get_feed_page(
    db: Session,
    *,
    subject_slug: str | None = None,
    card_type: str | None = None,
    mode: str | None = None,
    topic_slug: str | None = None,
    source_type: str | None = None,
    tag: str | None = None,
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
    if source_type and source_type != "all":
        query = query.filter(FeedCard.source_type == source_type)
    if tag:
        # Tags are stored comma-separated; the delimiters on both sides stop
        # "graph" from matching "graph-theory".
        query = query.filter(
            func.concat(",", FeedCard.tags, ",").contains(f",{tag},")
        )

    total = query.count()

    if mode == StudyMode.BASIC:
        # Teaching order: concept sequence, then card sequence within it.
        # BASIC is the one mode that should march in order, so it keeps the
        # strict walk rather than the mixed page below.
        ordering = (Concept.sequence.asc(), FeedCard.sequence.asc(), FeedCard.id.asc())
        rows = query.order_by(*ordering).offset(offset).limit(limit).all()
    else:
        # Everything else is ordered by readiness and laid out as a mix.
        # Sorting by weight put 654 of 659 cards at the same score, so the
        # feed fell back to id order -- the order they were generated in.
        rows = _ready_ordered_rows(db, query, offset=offset, limit=limit)

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
            # Lets the card show where it came from, and marks the ones the
            # student wrote themselves.
            "source_type": card.source_type or "knowledge_base",
            "tags": [t for t in (card.tags or "").split(",") if t],
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
