"""Derive an ordered concept list for a topic from the student's sources."""

import logging

from sqlalchemy.orm import Session

from ...ai import client as ai_client
from ...ai.prompts import concepts as prompts
from ...models.concepts import Concept, StudyMode
from ...models.models import Subject, Topic
from ...services.retrieval.hybrid import search
from .grounding import InsufficientContext, build_context, parse_json_response

logger = logging.getLogger(__name__)

VALID_MODES = {StudyMode.BASIC, StudyMode.ADVANCED}


def generate_concepts_for_topic(
    db: Session, topic_id: int, *, extend: bool = False,
) -> list[Concept]:
    """Create the ordered Concept rows for one topic.

    Idempotent by default: a topic that already has concepts is left alone,
    so this can be re-run as more sources are ingested without duplicating
    work.

    That default has a cost worth knowing. A topic whose concepts were
    drawn from a thin corpus keeps them forever, even after the book that
    covers it is ingested -- Digital Logic's Number Representation had four
    concepts and no IEEE 754 or overflow detection, because they were
    written before Morris Mano existed in the corpus. `extend=True` asks
    again and keeps whatever is new, matching on slug so existing concepts
    and the cards hanging off them are untouched.
    """
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if topic is None:
        raise ValueError(f"No topic with id {topic_id}")

    present = {
        c.slug: c
        for c in db.query(Concept).filter(Concept.topic_id == topic_id).all()
    }
    if present and not extend:
        logger.info("Topic %s already has %d concepts; skipping",
                    topic.name, len(present))
        return []

    subject = db.query(Subject).filter(Subject.id == topic.subject_id).first()

    matches = search(db, topic.name, top_k=8, subject_id=topic.subject_id)
    context = build_context(matches)  # raises InsufficientContext

    raw = ai_client.generate_text(
        prompts.USER_TEMPLATE.format(
            subject=subject.name, topic=topic.name, context=context.text
        ),
        system_instruction=prompts.SYSTEM,
        response_mime_type="application/json",
        temperature=0.3,
    )

    payload = parse_json_response(raw)
    created: list[Concept] = []

    # Continue the sequence rather than restarting it, so an extended
    # topic keeps its existing teaching order.
    start = max((c.sequence or 0) for c in present.values()) + 1 if present else 1

    for index, item in enumerate(payload.get("concepts", []), start=start):
        name = (item.get("name") or "").strip()
        slug = (item.get("slug") or "").strip()
        if not name or not slug:
            continue
        if slug in present:
            continue  # already taught; its cards stay as they are

        mode = item.get("introduced_in", StudyMode.BASIC)
        concept = Concept(
            topic_id=topic.id,
            subject_id=topic.subject_id,
            name=name[:200],
            slug=slug[:200],
            summary=(item.get("summary") or "")[:1000],
            sequence=int(item.get("sequence") or index),
            prerequisite_slugs=",".join(item.get("prerequisite_slugs") or []),
            introduced_in=mode if mode in VALID_MODES else StudyMode.BASIC,
            exam_weight=float(item.get("exam_weight") or 1.0),
        )
        db.add(concept)
        created.append(concept)

    db.commit()
    logger.info("Topic %s: created %d concepts", topic.name, len(created))
    return created


def generate_all_concepts(db: Session, *, limit: int | None = None) -> dict:
    """Walk every topic that has no concepts yet."""
    topics = db.query(Topic).order_by(Topic.subject_id, Topic.id).all()
    done, skipped, failed = 0, 0, 0

    for topic in topics:
        if limit is not None and done >= limit:
            break
        if db.query(Concept).filter(Concept.topic_id == topic.id).count():
            skipped += 1
            continue
        try:
            created = generate_concepts_for_topic(db, topic.id)
            done += 1 if created else 0
        except InsufficientContext as exc:
            logger.warning("Skipping %s: %s", topic.name, exc)
            skipped += 1
        except Exception:
            logger.exception("Failed on topic %s", topic.name)
            failed += 1

    return {"topics_processed": done, "skipped": skipped, "failed": failed}
