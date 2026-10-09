"""Revision feed: ranked, paginated cards, and what has been seen."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.models import FeedCard
from ..models.rotation import CardView
from ..services.feed.ranking import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, get_feed_page

router = APIRouter(prefix="/api/feed", tags=["Feed"])


@router.get("")
def get_feed(
    subject_slug: str | None = None,
    topic_slug: str | None = None,
    card_type: str | None = None,
    mode: str | None = None,
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
