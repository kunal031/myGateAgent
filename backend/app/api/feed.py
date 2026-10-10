"""Revision feed: ranked, paginated cards, and what has been seen."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.concepts import Concept
from ..models.models import FeedCard, Subject, Topic
from ..models.rotation import CardView
from ..services.feed.ranking import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, get_feed_page

router = APIRouter(prefix="/api/feed", tags=["Feed"])


@router.get("")
def get_feed(
    subject_slug: str | None = None,
    topic_slug: str | None = None,
    card_type: str | None = None,
    mode: str | None = None,
    source_type: str | None = None,
    tag: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
):
    """One page of the feed, ranked by base weight plus a per-mistake boost.

    Returns next_offset for infinite scroll; null means the end. Ranking and
    slicing happen in SQL, so response size does not grow with the library.
    """
    page = get_feed_page(
        db,
        subject_slug=subject_slug,
        topic_slug=topic_slug,
        card_type=card_type,
        mode=mode,
        source_type=source_type,
        tag=tag,
        offset=offset,
        limit=limit,
    )
    return {
        "items": page.items,
        "next_offset": page.next_offset,
        "total": page.total,
    }


def _view_for(db: Session, card_id: int) -> CardView:
    view = db.query(CardView).filter(CardView.card_id == card_id).first()
    if view is None:
        view = CardView(card_id=card_id)
        db.add(view)
    return view


@router.post("/cards/{card_id}/seen")
def mark_seen(card_id: int, db: Session = Depends(get_db)):
    """Record that a card was shown, without claiming it was learned."""
    if db.query(FeedCard).filter(FeedCard.id == card_id).first() is None:
        raise HTTPException(404, "No such card")

    view = _view_for(db, card_id)
    view.seen_count = (view.seen_count or 0) + 1
    view.last_seen_at = datetime.utcnow()
    db.commit()
    return {"card_id": card_id, "seen_count": view.seen_count}


@router.post("/cards/{card_id}/recall")
def mark_recalled(card_id: int, db: Session = Depends(get_db)):
    """Marked "got it": schedule the next review further out."""
    if db.query(FeedCard).filter(FeedCard.id == card_id).first() is None:
        raise HTTPException(404, "No such card")

    view = _view_for(db, card_id)
    view.record_recall()
    db.commit()
    return {
        "card_id": card_id,
        "recall_count": view.recall_count,
        "mastered": view.mastered,
        "due_at": view.due_at.isoformat() if view.due_at else None,
    }


@router.get("/due")
def due_for_revision(
    limit: int = Query(default=DEFAULT_PAGE_SIZE, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
):
    """Cards whose review date has arrived, soonest-overdue first."""
    now = datetime.utcnow()
    rows = (
        db.query(CardView, FeedCard)
        .join(FeedCard, CardView.card_id == FeedCard.id)
        .filter(CardView.due_at.isnot(None), CardView.due_at <= now)
        .order_by(CardView.due_at.asc())
        .limit(limit).all()
    )
    return {
        "items": [
            {
                "id": card.id,
                "title": card.title,
                "content": card.content,
                "takeaway": card.takeaway,
                "card_type": card.card_type,
                "mode": card.mode,
                "provenance": card.provenance or "",
                "recall_count": view.recall_count,
                "due_at": view.due_at.isoformat() if view.due_at else None,
            }
            for view, card in rows
        ],
        "total": len(rows),
    }


class UserCardPayload(BaseModel):
    """A card the student writes themselves."""

    subject_slug: str
    topic_slug: str
    title: str
    content: str
    takeaway: str = ""
    card_type: str = "CONCEPT"
    mode: str = "ADVANCED"
    difficulty: str = "Standard"
    concept_id: int | None = None
    # Chapter name, related concepts, anything worth filtering by later.
    tags: list[str] = Field(default_factory=list)


def _clean_tags(tags: list[str]) -> str:
    """Normalise to a comma-separated string with no empties or commas.

    A comma inside a tag would split it into two on read, so it is stripped
    rather than escaped -- these are short labels, not prose.
    """
    seen: list[str] = []
    for raw in tags:
        tag = raw.replace(",", " ").strip()
        if tag and tag.lower() not in {t.lower() for t in seen}:
            seen.append(tag[:60])
    return ",".join(seen[:12])


def _card_response(card: FeedCard) -> dict:
    return {
        "id": card.id,
        "title": card.title,
        "content": card.content,
        "takeaway": card.takeaway,
        "card_type": card.card_type,
        "mode": card.mode,
        "difficulty": card.difficulty,
        "source_type": card.source_type,
        "tags": [t for t in (card.tags or "").split(",") if t],
        "subject_id": card.subject_id,
        "topic_id": card.topic_id,
        "concept_id": card.concept_id,
        "provenance": card.provenance or "",
    }


@router.post("", status_code=201)
def create_card(payload: UserCardPayload, db: Session = Depends(get_db)):
    """Add a card by hand.

    Marked source_type="user" so it is distinguishable everywhere from
    generated content, and so the feed can show only these when asked. It
    carries no provenance because there is no source chunk behind it -- the
    student is the source, which the card's own badge says.
    """
    title = payload.title.strip()
    content = payload.content.strip()
    if not title or not content:
        raise HTTPException(400, "A card needs a title and content")

    subject = db.query(Subject).filter(Subject.slug == payload.subject_slug).first()
    if subject is None:
        raise HTTPException(404, f"No subject {payload.subject_slug!r}")
    topic = (
        db.query(Topic)
        .filter(Topic.slug == payload.topic_slug,
                Topic.subject_id == subject.id)
        .first()
    )
    if topic is None:
        raise HTTPException(404, f"No topic {payload.topic_slug!r} in that subject")

    if payload.concept_id is not None:
        concept = db.query(Concept).filter(
            Concept.id == payload.concept_id,
            Concept.topic_id == topic.id,
        ).first()
        if concept is None:
            raise HTTPException(404, "That concept is not in this topic")

    card = FeedCard(
        subject_id=subject.id,
        topic_id=topic.id,
        concept_id=payload.concept_id,
        mode=payload.mode,
        card_type=payload.card_type,
        title=title[:200],
        content=content,
        takeaway=(payload.takeaway.strip() or title)[:2000],
        difficulty=payload.difficulty,
        source_type="user",
        tags=_clean_tags(payload.tags),
        provenance="",
        review_status="approved",
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return _card_response(card)


@router.patch("/{card_id}")
def update_card(card_id: int, payload: UserCardPayload,
                db: Session = Depends(get_db)):
    """Edit a card the student wrote.

    Generated cards are not editable here: they are reproducible from their
    source, and silently diverging from it would make the citation a lie.
    """
    card = db.query(FeedCard).filter(FeedCard.id == card_id).first()
    if card is None:
        raise HTTPException(404, "No such card")
    if card.source_type != "user":
        raise HTTPException(
            403, "Only cards you wrote can be edited; this one is generated"
        )

    title = payload.title.strip()
    content = payload.content.strip()
    if not title or not content:
        raise HTTPException(400, "A card needs a title and content")

    card.title = title[:200]
    card.content = content
    card.takeaway = (payload.takeaway.strip() or title)[:2000]
    card.card_type = payload.card_type
    card.mode = payload.mode
    card.difficulty = payload.difficulty
    card.tags = _clean_tags(payload.tags)
    db.commit()
    db.refresh(card)
    return _card_response(card)


@router.delete("/{card_id}", status_code=204)
def delete_card(card_id: int, db: Session = Depends(get_db)):
    """Remove a card the student wrote, and anything tracking it."""
    card = db.query(FeedCard).filter(FeedCard.id == card_id).first()
    if card is None:
        raise HTTPException(404, "No such card")
    if card.source_type != "user":
        raise HTTPException(
            403, "Only cards you wrote can be deleted; this one is generated"
        )
    # CardView has a foreign key to the card, so it goes first.
    db.query(CardView).filter(CardView.card_id == card_id).delete()
    db.delete(card)
    db.commit()
