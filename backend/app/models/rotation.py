"""What the student has seen, and when it should come back.

Without this the feed cannot tell a card already read from one never
shown, so there is no revision mode and no way to stop repeating the same
cards.
"""

from datetime import datetime, timedelta

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Index, Integer, String,
)
from sqlalchemy.orm import relationship

from ..core.database import Base
from .models import FeedCard  # noqa: F401  (register FK target)

# Days until a card is due again, by how many times it has been recalled.
# Expanding intervals: each successful recall buys more time before the
# next one, which is what makes revision cheap as the library grows.
REVIEW_INTERVALS_DAYS = [1, 3, 7, 21, 60]


class CardView(Base):
    """One student's history with one card."""

    __tablename__ = "card_views"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    card_id = Column(Integer, ForeignKey("feed_cards.id"),
                     nullable=False, index=True)

    seen_count = Column(Integer, default=0)
    # Marked "got it": counts toward the next interval.
    recall_count = Column(Integer, default=0)
    # Answered a question on this concept wrongly: resets the interval.
    lapse_count = Column(Integer, default=0)

    mastered = Column(Boolean, default=False, index=True)

    first_seen_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)
    due_at = Column(DateTime, nullable=True, index=True)

    card = relationship("FeedCard")

    __table_args__ = (Index("ix_card_view_card", "card_id", unique=True),)

    def schedule_next(self) -> None:
        """Set the next due date from the recall count."""
        # Column defaults are applied by the database on insert, so these
        # are None on an instance that has not been flushed yet.
        self.recall_count = self.recall_count or 0
        index = min(self.recall_count, len(REVIEW_INTERVALS_DAYS) - 1)
        days = REVIEW_INTERVALS_DAYS[index]
        self.due_at = datetime.utcnow() + timedelta(days=days)

    def record_recall(self) -> None:
        """Marked "got it": count it and push the next review out."""
        self.recall_count = (self.recall_count or 0) + 1
        self.seen_count = (self.seen_count or 0) + 1
        self.last_seen_at = datetime.utcnow()
        self.mastered = self.recall_count >= len(REVIEW_INTERVALS_DAYS)
        self.schedule_next()

    def lapse(self) -> None:
        """A wrong answer sends the card back to the shortest interval.

        Recall count drops rather than resetting to zero: the student has
        still seen it, and starting from scratch over-corrects.
        """
        self.lapse_count = (self.lapse_count or 0) + 1
        self.recall_count = max(0, (self.recall_count or 0) - 2)
        self.mastered = False
        self.due_at = datetime.utcnow() + timedelta(
            days=REVIEW_INTERVALS_DAYS[0]
        )
