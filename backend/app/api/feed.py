"""Revision feed: ranked, paginated cards."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.database import get_db
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
