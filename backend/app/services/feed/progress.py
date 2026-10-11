"""Track what has actually been learned, concept by concept.

Nothing else in the feed can work without this. The ordering needs to know
which concepts are behind the student and which are still ahead; the
readiness check needs to know whether a prerequisite is done. Both read
`concept_progress`, which existed as a table and a model and was never
written to -- so the feed had no memory and could only ever re-rank the
same material.

A concept advances on evidence, not on being shown:

    not_started -> learning   the first card of it is seen
    learning    -> learned    every card in it has been recalled once
    learned     -> revised    recalled again after the first spacing gap
    revised     -> mastered   survived the whole spacing ladder

Wrong answers push `escalation_level` up rather than demoting the status.
Forgetting one detail does not mean a concept was never learned, and the
escalation is what lifts its cards back up the feed.
"""

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from ...models.concepts import Concept, ConceptProgress, ConceptStatus
from ...models.models import FeedCard
from ...models.rotation import CardView

logger = logging.getLogger(__name__)

#: Mistakes needed to push a concept one escalation step. One slip is
#: noise; a pattern is a signal.
MISTAKES_PER_ESCALATION = 2

#: Escalation is capped so one stubborn concept cannot crowd out the feed.
MAX_ESCALATION = 3


def get_or_create(db: Session, concept_id: int) -> ConceptProgress:
    """The progress row for a concept, created on first contact."""
    row = (
        db.query(ConceptProgress)
        .filter(ConceptProgress.concept_id == concept_id)
        .first()
    )
    if row is None:
        row = ConceptProgress(
            concept_id=concept_id,
            status=ConceptStatus.NOT_STARTED,
            first_seen_at=datetime.utcnow(),
        )
        db.add(row)
        db.flush()
    return row


def _recalled_card_ids(db: Session, concept_id: int) -> set[int]:
    """Cards of this concept the student has successfully recalled."""
    rows = (
        db.query(CardView.card_id)
        .join(FeedCard, FeedCard.id == CardView.card_id)
        .filter(FeedCard.concept_id == concept_id, CardView.recall_count > 0)
        .all()
    )
    return {r[0] for r in rows}


def record_card_seen(db: Session, card: FeedCard) -> ConceptProgress | None:
    """A card was shown. Move the concept off not_started."""
    if card.concept_id is None:
        return None

    progress = get_or_create(db, card.concept_id)
    progress.cards_seen = (progress.cards_seen or 0) + 1
    progress.last_seen_at = datetime.utcnow()
    if progress.status == ConceptStatus.NOT_STARTED:
        progress.status = ConceptStatus.LEARNING
    return progress


def record_card_recalled(db: Session, card: FeedCard) -> ConceptProgress | None:
    """A card was marked known. Advance the concept if all of its cards are.

    "Learned" means every card in the concept has been recalled at least
    once, not that one card was clicked. The distinction matters: a concept
    with six cards is not learned because its easiest one was dismissed.
    """
    if card.concept_id is None:
        return None

    progress = get_or_create(db, card.concept_id)
    progress.last_seen_at = datetime.utcnow()

    total = (
        db.query(FeedCard.id)
        .filter(FeedCard.concept_id == card.concept_id)
        .count()
    )
    recalled = len(_recalled_card_ids(db, card.concept_id))

    if total and recalled >= total:
        if progress.status in (ConceptStatus.NOT_STARTED, ConceptStatus.LEARNING):
            progress.status = ConceptStatus.LEARNED
        elif progress.status == ConceptStatus.LEARNED:
            progress.status = ConceptStatus.REVISED
            progress.revision_count = (progress.revision_count or 0) + 1
            progress.last_revised_at = datetime.utcnow()
        elif progress.status == ConceptStatus.REVISED:
            # Mastered once every card has survived the full ladder, which
            # CardView.mastered already decides per card.
            if _all_cards_mastered(db, card.concept_id):
                progress.status = ConceptStatus.MASTERED
            else:
                progress.revision_count = (progress.revision_count or 0) + 1
                progress.last_revised_at = datetime.utcnow()
    elif progress.status == ConceptStatus.NOT_STARTED:
        progress.status = ConceptStatus.LEARNING

    return progress


def _all_cards_mastered(db: Session, concept_id: int) -> bool:
    rows = (
        db.query(CardView.mastered)
        .join(FeedCard, FeedCard.id == CardView.card_id)
        .filter(FeedCard.concept_id == concept_id)
        .all()
    )
    return bool(rows) and all(r[0] for r in rows)


def record_answer(
    db: Session, concept_id: int | None, *, correct: bool,
) -> ConceptProgress | None:
    """A quiz or drill answer. Feeds the escalation ladder."""
    if concept_id is None:
        return None

    progress = get_or_create(db, concept_id)
    if correct:
        progress.correct_count = (progress.correct_count or 0) + 1
    else:
        progress.wrong_count = (progress.wrong_count or 0) + 1
        # Status is not demoted: forgetting one detail does not undo
        # learning the concept. The escalation is what lifts its cards.
        progress.escalation_level = min(
            MAX_ESCALATION,
            (progress.wrong_count or 0) // MISTAKES_PER_ESCALATION,
        )
    if progress.status == ConceptStatus.NOT_STARTED:
        progress.status = ConceptStatus.LEARNING
    return progress


def learned_concept_ids(db: Session) -> set[int]:
    """Concepts the student is past, for the readiness check."""
    rows = (
        db.query(ConceptProgress.concept_id)
        .filter(ConceptProgress.status.in_((
            ConceptStatus.LEARNED, ConceptStatus.REVISED,
            ConceptStatus.MASTERED,
        )))
        .all()
    )
    return {r[0] for r in rows}


def progress_by_concept(db: Session) -> dict[int, ConceptProgress]:
    """Every progress row, keyed by concept, for one-query ordering."""
    return {
        row.concept_id: row
        for row in db.query(ConceptProgress).all()
    }


def backfill_from_card_views(db: Session) -> int:
    """Build progress rows from recall history already on disk.

    Card views predate this module, so without a backfill a student who has
    been using the feed would start from not_started on every concept.
    """
    seen: set[int] = set()
    rows = (
        db.query(FeedCard)
        .join(CardView, CardView.card_id == FeedCard.id)
        .filter(FeedCard.concept_id.isnot(None))
        .all()
    )
    for card in rows:
        if card.concept_id in seen:
            continue
        seen.add(card.concept_id)
        record_card_recalled(db, card)
    db.commit()
    return len(seen)
