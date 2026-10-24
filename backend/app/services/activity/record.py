"""Write study events to the activity log.

One function per kind of event, each taking the object that was acted on
and resolving the four taxonomy levels from it. Callers pass what they
already have in hand and nothing else.

**Recording never breaks the action it records.** Every function swallows
its own exceptions and logs them. Answering a question must not fail
because the activity log did -- the attempt is the thing the student
cares about, and a lost log line is recoverable where a lost answer is
not. This is the one place in the codebase where a silent failure is the
correct behaviour, so it is also the one place that logs loudly enough to
notice.

Flushing is the caller's job. These add to the session and do not commit,
so the event lands in the same transaction as the thing it describes:
either both are recorded or neither is, and the log cannot claim an
attempt that was rolled back.
"""

import logging

from sqlalchemy.orm import Session

from ...models.activity import ActivityEvent, ActivityKind
from ...models.concepts import Concept
from ...models.models import FeedCard, Question, Topic

logger = logging.getLogger(__name__)

#: Day report rows show a label; anything longer is noise in a list.
MAX_LABEL = 300


def _hierarchy_from_topic(db: Session, topic_id: int | None) -> dict:
    """Resolve subject and chapter from a topic, for events that have one."""
    if topic_id is None:
        return {}
    topic = db.get(Topic, topic_id)
    if topic is None:
        return {}
    return {
        "topic_id": topic.id,
        "chapter_id": topic.chapter_id,
        "subject_id": topic.subject_id,
    }


def _add(db: Session, **fields) -> ActivityEvent | None:
    try:
        label = (fields.pop("label", "") or "")[:MAX_LABEL]
        event = ActivityEvent(label=label, **fields)
        db.add(event)
        return event
    except Exception:
        # See the module docstring: the action must survive a failure here.
        logger.exception("Failed to record activity event: %s", fields)
        return None


def record_attempt(db: Session, *, user_id: int, question: Question,
                   is_correct: bool, marks: float = 0.0,
                   seconds: int = 0, mode: str = "quiz") -> None:
    """A question was answered."""
    _add(
        db,
        user_id=user_id,
        kind=ActivityKind.ATTEMPT,
        object_type="question",
        object_id=question.id,
        label=(question.content or "")[:MAX_LABEL],
        correct=1 if is_correct else 0,
        marks=float(marks or 0.0),
        seconds=int(seconds or 0),
        detail=mode,
        concept_id=getattr(question, "concept_id", None),
        **_hierarchy_from_topic(db, question.topic_id),
    )


def record_card_view(db: Session, *, user_id: int, card: FeedCard) -> None:
    """A feed card was read.

    This is the event that could not be reconstructed before: `card_views`
    keeps one row per card with `last_seen_at`, so a card read on three
    days showed only the most recent, and a day spent reading rather than
    answering looked empty.
    """
    _add(
        db,
        user_id=user_id,
        kind=ActivityKind.CARD_VIEW,
        object_type="feed_card",
        object_id=card.id,
        label=card.title or "",
        detail=card.card_type or "",
        concept_id=card.concept_id,
        **_hierarchy_from_topic(db, card.topic_id),
    )


def record_card_review(db: Session, *, user_id: int, card: FeedCard,
                       recalled: bool) -> None:
    """A card was marked recalled or forgotten."""
    _add(
        db,
        user_id=user_id,
        kind=ActivityKind.CARD_REVIEW,
        object_type="feed_card",
        object_id=card.id,
        label=card.title or "",
        correct=1 if recalled else 0,
        detail="recalled" if recalled else "forgotten",
        concept_id=card.concept_id,
        **_hierarchy_from_topic(db, card.topic_id),
    )


def record_concept_progress(db: Session, *, user_id: int, concept: Concept,
                            status: str) -> None:
    """A concept changed status."""
    _add(
        db,
        user_id=user_id,
        kind=ActivityKind.CONCEPT_PROGRESS,
        object_type="concept",
        object_id=concept.id,
        label=concept.name or "",
        detail=status,
        concept_id=concept.id,
        **_hierarchy_from_topic(db, concept.topic_id),
    )


def record_exam(db: Session, *, user_id: int, session_id: int, name: str,
                submitted: bool, score: float | None = None,
                seconds: int | None = None,
                subject_id: int | None = None,
                topic_id: int | None = None) -> None:
    """A timed paper was started or submitted.

    Both are recorded, but only submission counts as study -- starting a
    paper and abandoning it should not keep a streak alive.
    """
    _add(
        db,
        user_id=user_id,
        kind=ActivityKind.EXAM_SUBMIT if submitted else ActivityKind.EXAM_START,
        object_type="exam_session",
        object_id=session_id,
        label=name or "",
        marks=float(score) if score is not None else None,
        seconds=int(seconds) if seconds is not None else None,
        # Chapter resolved from the topic, so an exam event files beside
        # the attempts it produced rather than under "Unassigned".
        **({**_hierarchy_from_topic(db, topic_id)}
           if topic_id is not None else {"subject_id": subject_id}),
    )


def record_assistant_ask(db: Session, *, user_id: int, question: str,
                         subject_id: int | None = None,
                         concept_id: int | None = None,
                         topic_id: int | None = None) -> None:
    """The assistant was asked something."""
    fields = {
        "user_id": user_id,
        "kind": ActivityKind.ASSISTANT_ASK,
        "object_type": "assistant",
        "label": question or "",
        "concept_id": concept_id,
    }
    if topic_id is not None:
        fields.update(_hierarchy_from_topic(db, topic_id))
    elif subject_id is not None:
        fields["subject_id"] = subject_id
    _add(db, **fields)
