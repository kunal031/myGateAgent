"""Persist a parsed paper into the question bank.

Nothing is written until the student confirms a preview. A parse that
guessed an answer wrongly is far more costly than one that asks: a wrong
answer in the bank is practised as if it were right, and only surfaces as
confusion weeks later.
"""

import json
import logging
import re

from sqlalchemy.orm import Session

from ...models.models import Question, Subject, Topic
from ...models.papers import ImportStatus, QuestionPaper

logger = logging.getLogger(__name__)

#: MCQ only. MSQ and NAT carry no negative marking in GATE.
NEGATIVE_MARKS = {1: 0.33, 2: 0.66}

_WHITESPACE = re.compile(r"\s+")


def dedupe_key(content: str) -> str:
    """A question's identity, for spotting one already in the bank.

    Exact content matching is too strict: the same question extracted twice
    differed by a "Question 3: " prefix and by how whitespace fell, so both
    copies were stored and a quiz could serve them together. Folding case
    and whitespace catches those without merging genuinely different stems.
    """
    return _WHITESPACE.sub(" ", content).strip().lower()[:300]


def negative_for(question_type: str, marks: int) -> float:
    return NEGATIVE_MARKS.get(marks, 0.33) if question_type == "MCQ" else 0.0


def resolve_target(db: Session, subject_slug: str, topic_slug: str) -> tuple[Subject, Topic]:
    """Find the subject and topic a paper files under.

    Both are required and neither is guessed. The existing book importer
    falls back to the subject's lowest-id topic when it cannot match one,
    which is how every Operating Systems question ended up under Process
    Synchronization. Refusing is the better failure.
    """
    subject = db.query(Subject).filter(Subject.slug == subject_slug).first()
    if subject is None:
        raise ValueError(f"No subject {subject_slug!r}")

    topic = (
        db.query(Topic)
        .filter(Topic.slug == topic_slug, Topic.subject_id == subject.id)
        .first()
    )
    if topic is None:
        raise ValueError(
            f"No topic {topic_slug!r} in {subject.name}. Create it first."
        )
    return subject, topic


def store_questions(
    db: Session,
    paper: QuestionPaper,
    parsed: list[dict],
    *,
    provenance: str,
) -> dict:
    """Write confirmed questions, skipping anything unusable.

    Returns counts rather than raising: one malformed question should not
    cost the other twenty-four.
    """
    stored = skipped = 0

    # Everything already in the bank for this topic, folded for comparison.
    seen = {
        dedupe_key(row[0])
        for row in db.query(Question.content)
        .filter(Question.topic_id == paper.topic_id).all()
    }

    for item in parsed:
        content = (item.get("content") or "").strip()
        answer = (item.get("correct_answer") or "").strip()
        qtype = (item.get("question_type") or "MCQ").upper()

        if not content or not answer or qtype not in {"MCQ", "MSQ", "NAT"}:
            skipped += 1
            continue

        options = item.get("options") or []
        if qtype in {"MCQ", "MSQ"} and len(options) < 2:
            skipped += 1
            continue

        # The same question appears on several pages, and a page can print
        # one twice. Matching on a folded key rather than exact content
        # keeps the bank free of repeats a student would meet twice in one
        # quiz, including ones that differ only by spacing.
        if dedupe_key(content) in seen:
            skipped += 1
            continue
        seen.add(dedupe_key(content))

        marks = item.get("marks") if item.get("marks") in (1, 2) else 1

        db.add(Question(
            subject_id=paper.subject_id,
            topic_id=paper.topic_id,
            paper_id=paper.id,
            question_type=qtype,
            marks=marks,
            negative_marks=negative_for(qtype, marks),
            content=content,
            options=json.dumps(options) if options else None,
            correct_answer=answer,
            nat_min=item.get("nat_min"),
            nat_max=item.get("nat_max"),
            explanation=(item.get("explanation") or "").strip(),
            solution_source=item.get("solution_source") or "",
            origin="WEB" if paper.origin_url else "PYQ",
            exam_year=item.get("exam_year") or paper.exam_year,
            source=(item.get("source_label") or paper.source_label
                    or "Imported")[:100],
            is_pyq=True,
            provenance=provenance[:2000],
            # Imported questions are worth a second look before they are
            # trusted in a timed run.
            review_status="pending",
        ))
        stored += 1

    paper.question_count = stored
    paper.import_status = ImportStatus.COMPLETE
    db.commit()

    return {"stored": stored, "skipped": skipped}
