"""Build the quiz question bank.

Two sources, in order of value:

  extract_pyq_questions  real GATE questions parsed from the PYQ compilation
  generate_questions     written from the student's notes, for gaps

Real exam questions are strictly better practice than generated ones, so
extraction runs first and generation only fills what it misses.
"""

import json
import logging

from sqlalchemy.orm import Session

from ...ai import client as ai_client
from ...ai.prompts import questions as prompts
from ...models import *  # noqa: F401,F403  (register all tables)
from ...models.concepts import Concept
from ...models.models import Question, Subject, Topic
from ...models.sources import Source, SourceChunk
from ...services.retrieval.hybrid import search
from .grounding import (
    InsufficientContext, build_context, is_supported, parse_json_response,
)

logger = logging.getLogger(__name__)

VALID_TYPES = {"MCQ", "MSQ", "NAT"}

# Official GATE negative marking: MCQ only, proportional to marks.
NEGATIVE_MARKS = {1: 0.33, 2: 0.66}


def _negative_for(question_type: str, marks: int) -> float:
    if question_type != "MCQ":
        return 0.0
    return NEGATIVE_MARKS.get(marks, 0.33)


def _store_question(
    db: Session, item: dict, *, subject_id: int, topic_id: int,
    concept_id: int | None, origin: str, provenance: str, chunk_ids: str,
) -> Question | None:
    """Validate one parsed question and persist it. Returns None if unusable."""
    content = (item.get("content") or "").strip()
    answer = (item.get("correct_answer") or "").strip()
    qtype = (item.get("question_type") or "MCQ").upper()

    if not content or not answer or qtype not in VALID_TYPES:
        return None

    options = item.get("options") or []
    if qtype in {"MCQ", "MSQ"} and len(options) < 2:
        return None

    # Skip exact duplicates: the same question often appears in several
    # chunks because of the overlap between them.
    if db.query(Question).filter(Question.content == content).first():
        return None

    marks = int(item.get("marks") or 1)
    question = Question(
        subject_id=subject_id,
        topic_id=topic_id,
        concept_id=concept_id,
        question_type=qtype,
        marks=marks,
        negative_marks=_negative_for(qtype, marks),
        content=content,
        options=json.dumps(options) if options else None,
        correct_answer=answer,
        nat_min=item.get("nat_min"),
        nat_max=item.get("nat_max"),
        explanation=(item.get("explanation") or "").strip() or "No explanation given.",
        difficulty="Standard GATE",
        source="GATE PYQ" if origin == "PYQ" else "Generated",
        is_pyq=(origin == "PYQ"),
        exam_year=item.get("exam_year"),
        origin=origin,
        provenance=provenance[:2000],
        source_chunk_ids=chunk_ids[:200],
        review_status="pending",
    )
    db.add(question)
    return question


def extract_pyq_questions(
    db: Session, *, limit_chunks: int | None = None, subject_slug: str | None = None,
) -> dict:
    """Parse real GATE questions out of the ingested PYQ compilation."""
    source = db.query(Source).filter(Source.kind == "PYQ_TOPICWISE").first()
    if source is None:
        return {"error": "No PYQ compilation ingested"}

    query = (
        db.query(SourceChunk)
        .filter(SourceChunk.source_id == source.id)
        .filter(SourceChunk.content.like("%[GATE%"))
        .order_by(SourceChunk.page_number)
    )
    chunks = query.limit(limit_chunks).all() if limit_chunks else query.all()

    subjects = {s.slug: s for s in db.query(Subject).all()}
    extracted, skipped = 0, 0

    for chunk in chunks:
        subject = _guess_subject(chunk.content, subjects)
        if subject is None or (subject_slug and subject.slug != subject_slug):
            skipped += 1
            continue

        topic = (
            db.query(Topic).filter(Topic.subject_id == subject.id)
            .order_by(Topic.id).first()
        )
        if topic is None:
            skipped += 1
            continue

        try:
            raw = ai_client.generate_text(
                prompts.EXTRACT_TEMPLATE.format(
                    subject=subject.name, context=chunk.content),
                system_instruction=prompts.EXTRACT_SYSTEM,
                response_mime_type="application/json",
                temperature=0.0,  # transcription, not invention
            )
            payload = parse_json_response(raw)
        except Exception:
            logger.warning("Could not parse chunk %s", chunk.id)
            skipped += 1
            continue

        for item in payload.get("questions", []):
            stored = _store_question(
                db, item,
                subject_id=subject.id, topic_id=topic.id, concept_id=None,
                origin="PYQ",
                provenance=f"{source.citation} (p. {chunk.page_number})",
                chunk_ids=str(chunk.id),
            )
            if stored is not None:
                extracted += 1
        db.commit()

    return {"chunks_read": len(chunks), "extracted": extracted, "skipped": skipped}


# Chapter headings in the PYQ book name the subject; match on distinctive words.
_SUBJECT_HINTS: list[tuple[str, tuple[str, ...]]] = [
    ("databases", ("RDBMS", "SQL", "Normalization", "Transaction", "B+ Tree")),
    ("operating-systems", ("Process", "Deadlock", "Paging", "Scheduling", "Semaphore")),
    ("computer-networks", ("TCP", "IP Address", "Routing", "Subnet", "Ethernet")),
    ("theory-of-computation", ("Automata", "Turing", "Regular Language", "Grammar")),
    ("compiler-design", ("Parser", "Lexical", "Syntax Directed", "LR(", "LL(")),
    ("digital-logic", ("Boolean", "K-Map", "Flip-Flop", "Multiplexer", "Counter")),
    ("computer-organization-architecture", ("Cache", "Pipelin", "Addressing Mode", "Instruction Set")),
    ("algorithms", ("Asymptotic", "Greedy", "Dynamic Programming", "Shortest Path", "Recurrence")),
    ("programming-data-structures", ("Linked List", "Binary Tree", "Heap", "Pointer", "Stack")),
    ("engineering-mathematics", ("Matrix", "Eigen", "Probability", "Graph Theory", "Set Theory")),
    ("general-aptitude", ("Aptitude", "Percentage", "Ratio", "Syllogism")),
]


def _guess_subject(text: str, subjects: dict) -> Subject | None:
    """Infer the subject from chapter headings inside the chunk."""
    head = text[:600]
    best, best_hits = None, 0
    for slug, hints in _SUBJECT_HINTS:
        hits = sum(1 for h in hints if h.lower() in head.lower())
        if hits > best_hits:
            best, best_hits = slug, hits
    return subjects.get(best) if best_hits else None


def generate_questions_for_concept(
    db: Session, concept_id: int, count: int = 3,
) -> list[Question]:
    """Write GATE-style questions for one concept, grounded in its sources."""
    concept = db.query(Concept).filter(Concept.id == concept_id).first()
    if concept is None:
        raise ValueError(f"No concept with id {concept_id}")

    if db.query(Question).filter(Question.concept_id == concept_id).count():
        return []

    topic = db.query(Topic).filter(Topic.id == concept.topic_id).first()
    subject = db.query(Subject).filter(Subject.id == concept.subject_id).first()

    matches = search(db, f"{concept.name} {topic.name}", top_k=8,
                     subject_id=concept.subject_id)
    context = build_context(matches)  # raises InsufficientContext

    raw = ai_client.generate_text(
        prompts.GENERATE_TEMPLATE.format(
            subject=subject.name, topic=topic.name, concept=concept.name,
            context=context.text, count=count),
        system_instruction=prompts.GENERATE_SYSTEM,
        response_mime_type="application/json",
        temperature=0.4,
    )

    try:
        payload = parse_json_response(raw)
    except json.JSONDecodeError:
        logger.warning("Unparseable question reply for %s", concept.name)
        return []

    created = []
    for item in payload.get("questions", []):
        if not is_supported(item.get("supported_by", ""), context.text):
            continue
        stored = _store_question(
            db, item,
            subject_id=concept.subject_id, topic_id=concept.topic_id,
            concept_id=concept.id, origin="GENERATED",
            provenance=context.provenance,
            chunk_ids=",".join(str(c) for c in context.chunk_ids),
        )
        if stored is not None:
            created.append(stored)

    db.commit()
    return created
