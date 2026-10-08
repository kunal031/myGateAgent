"""Generate feed cards for a concept, grounded in the student's own sources.

Every card stores the chunk ids and citation it came from. A card whose
quoted support cannot be found in the retrieved context is dropped rather
than saved, so an unsupported claim never reaches the feed.
"""

import logging

from sqlalchemy.orm import Session

from ...ai import client as ai_client
from ...ai.prompts import cards as prompts
from ...models.concepts import Concept, StudyMode
from ...models.models import FeedCard, Subject, Topic
from ...services.retrieval.hybrid import search
from .grounding import (
    InsufficientContext, build_context, is_supported, parse_json_response,
)

logger = logging.getLogger(__name__)

VALID_TYPES = {"TRAP", "FORMULA", "CONCEPT", "SHORTCUT"}
BASIC_TYPES = {"CONCEPT", "FORMULA"}

TEMPLATES = {
    StudyMode.BASIC: prompts.BASIC_TEMPLATE,
    StudyMode.ADVANCED: prompts.ADVANCED_TEMPLATE,
}


def generate_cards_for_concept(
    db: Session,
    concept_id: int,
    mode: str = StudyMode.BASIC,
    count: int = 4,
) -> list[FeedCard]:
    """Create grounded cards for one concept in one mode."""
    concept = db.query(Concept).filter(Concept.id == concept_id).first()
    if concept is None:
        raise ValueError(f"No concept with id {concept_id}")

    template = TEMPLATES.get(mode)
    if template is None:
        raise ValueError(f"Cannot generate cards for mode {mode}")

    already = (
        db.query(FeedCard)
        .filter(FeedCard.concept_id == concept_id, FeedCard.mode == mode)
        .count()
    )
    if already:
        logger.info("Concept %s already has %d %s cards", concept.name, already, mode)
        return []

    topic = db.query(Topic).filter(Topic.id == concept.topic_id).first()
    subject = db.query(Subject).filter(Subject.id == concept.subject_id).first()

    # Search the concept in the context of its topic, scoped to the subject so
    # a same-word concept from another subject cannot leak in.
    matches = search(
        db,
        f"{concept.name} {topic.name}",
        top_k=8,
        subject_id=concept.subject_id,
    )
    context = build_context(matches)  # raises InsufficientContext

    raw = ai_client.generate_text(
        template.format(
            subject=subject.name,
            topic=topic.name,
            concept=concept.name,
            context=context.text,
            count=count,
        ),
        system_instruction=prompts.SYSTEM,
        response_mime_type="application/json",
        temperature=0.4,
    )

    payload = parse_json_response(raw)
    created: list[FeedCard] = []
    rejected = 0

    for index, item in enumerate(payload.get("cards", []), start=1):
        title = (item.get("title") or "").strip()
        content = (item.get("content") or "").strip()
        takeaway = (item.get("takeaway") or "").strip()
        if not (title and content and takeaway):
            continue

        # Drop anything whose claimed support is not actually in the context.
        if not is_supported(item.get("supported_by", ""), context.text):
            rejected += 1
            logger.warning("Rejected ungrounded card %r on %s", title, concept.name)
            continue

        card_type = (item.get("card_type") or "CONCEPT").upper()
        if card_type not in VALID_TYPES:
            card_type = "CONCEPT"
        if mode == StudyMode.BASIC and card_type not in BASIC_TYPES:
            card_type = "CONCEPT"

        db.add(FeedCard(
            subject_id=concept.subject_id,
            topic_id=concept.topic_id,
            concept_id=concept.id,
            mode=mode,
            sequence=int(item.get("sequence") or index),
            card_type=card_type,
            title=title[:200],
            content=content,
            takeaway=takeaway,
            difficulty="Standard GATE",
            base_weight=1,
            provenance=context.provenance[:2000],
            source_chunk_ids=",".join(str(c) for c in context.chunk_ids)[:200],
            review_status="pending",
        ))
        created.append(db.query(FeedCard).order_by(FeedCard.id.desc()).first())

    db.commit()
    logger.info(
        "Concept %s (%s): %d cards created, %d rejected as ungrounded",
        concept.name, mode, len(created), rejected,
    )
    return created


def generate_cards_for_topic(
    db: Session, topic_id: int, mode: str = StudyMode.BASIC, per_concept: int = 4
) -> dict:
    """Generate cards for every concept in a topic, in teaching order."""
    concepts = (
        db.query(Concept)
        .filter(Concept.topic_id == topic_id)
        .order_by(Concept.sequence)
        .all()
    )

    created, skipped = 0, 0
    for concept in concepts:
        try:
            created += len(generate_cards_for_concept(db, concept.id, mode, per_concept))
        except InsufficientContext as exc:
            logger.warning("Skipping concept %s: %s", concept.name, exc)
            skipped += 1
        except Exception:
            logger.exception("Failed on concept %s", concept.name)
            skipped += 1

    return {"concepts": len(concepts), "cards_created": created, "skipped": skipped}
