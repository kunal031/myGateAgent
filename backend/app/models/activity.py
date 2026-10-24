"""An append-only record of what the student did, and when.

The calendar and the day report need to answer "what did I do on 12
October" down to the concept. Most of that could not be answered before,
because the existing tables keep *current state*, not history:

* `card_views` holds one row per (user, card) with `last_seen_at`. A card
  read on three different days shows only the most recent, so a past day's
  reading is unrecoverable.
* `concept_progress` is the same shape -- `last_seen_at` overwrites.
* Only `attempts` and `exam_sessions` are already append-only.

So reconstructing a day from those tables would silently under-report:
the day you read forty cards and answered nothing would look empty, which
is precisely the day a streak-based nudge must not punish. This table
records each event as it happens and never updates a row.

Deliberately denormalised. `subject_id`, `chapter_id`, `topic_id` and
`concept_id` are all stored on the event, rather than joined back through
the card or question at read time. Two reasons: a day report groups by
all four levels and would otherwise need a four-table join per row, and
more importantly the taxonomy moves -- a concept refiled into another
chapter later would silently rewrite what you did last month. An event is
history, so it keeps the hierarchy it happened under.

Nullable throughout below `subject_id`, because not every event has every
level: an assistant question may be about a subject with no concept, and a
timed paper spans many topics.
"""

from datetime import datetime

from sqlalchemy import (
    Column, DateTime, Float, ForeignKey, Index, Integer, String, Text,
)

from ..core.database import Base


class ActivityKind:
    """What the student did.

    Kept as plain strings rather than a database enum: adding a kind is
    then a code change, not a migration, and an unrecognised kind renders
    as itself instead of raising.
    """

    #: Answered a question, in a quiz, test or the feed.
    ATTEMPT = "attempt"
    #: Read a feed card.
    CARD_VIEW = "card_view"
    #: Marked a card recalled or forgotten during review.
    CARD_REVIEW = "card_review"
    #: A concept moved status (learning -> learned, and so on).
    CONCEPT_PROGRESS = "concept_progress"
    #: Started or submitted a timed paper.
    EXAM_START = "exam_start"
    EXAM_SUBMIT = "exam_submit"
    #: Asked the assistant something.
    ASSISTANT_ASK = "assistant_ask"

    ALL = (
        ATTEMPT, CARD_VIEW, CARD_REVIEW, CONCEPT_PROGRESS,
        EXAM_START, EXAM_SUBMIT, ASSISTANT_ASK,
    )

    #: Kinds that count as studying for streak purposes. Starting a paper
    #: and abandoning it is not study; reading a card is.
    COUNTS_AS_STUDY = (
        ATTEMPT, CARD_VIEW, CARD_REVIEW, CONCEPT_PROGRESS, EXAM_SUBMIT,
    )


class ActivityEvent(Base):
    __tablename__ = "activity_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    kind = Column(String(30), nullable=False, index=True)

    # The hierarchy this happened under, captured at the time. See the
    # module docstring: refiling a concept later must not rewrite history.
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=True,
                        index=True)
    chapter_id = Column(Integer, ForeignKey("syllabus_chapters.id"),
                        nullable=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=True,
                      index=True)
    concept_id = Column(Integer, ForeignKey("concepts.id"), nullable=True,
                        index=True)

    # What was acted on. No foreign key: the event must survive the row it
    # refers to being deleted, or pruning a question would erase the fact
    # that it was once answered.
    object_type = Column(String(30), default="")
    object_id = Column(Integer, nullable=True)

    #: Shown in the day report, e.g. a question stem or a card title. Held
    #: here so the report reads correctly even after the source is edited.
    label = Column(Text, default="")

    # Outcome, where the kind has one. `correct` is null for a card view.
    correct = Column(Integer, nullable=True)      # 1, 0 or null
    marks = Column(Float, nullable=True)
    seconds = Column(Integer, nullable=True)

    #: Free-form extra, e.g. the status a concept moved to.
    detail = Column(String(120), default="")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False,
                        index=True)

    __table_args__ = (
        # The calendar's query: one user's events within a date window.
        Index("ix_activity_user_created", "user_id", "created_at"),
        # The day report groups by subject within a day.
        Index("ix_activity_user_subject", "user_id", "subject_id"),
    )
