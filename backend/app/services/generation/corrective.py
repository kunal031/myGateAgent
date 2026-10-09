"""Recovery when retrieval does not support the concept.

Three escalating attempts, cheapest first:

  1. retry   re-query with the concept phrased differently
  2. widen   drop the subject scope, in case the material sits elsewhere
  3. web     grounded search, with URL citations

Only after all three fail is the concept marked as needing a source, which
is the signal that a book is missing rather than that generation is broken.
"""

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ...ai import client as ai_client
from ...services.retrieval.hybrid import search
from .grading import ContextGrade, grade_context
from .grounding import GroundedContext, InsufficientContext, build_context

logger = logging.getLogger(__name__)

MAX_WEB_CHARS = 9000


@dataclass
class Recovery:
    context: GroundedContext | None
    grade: ContextGrade | None
    source_type: str          # knowledge_base | web | none
    attempts: list[str]

    @property
    def succeeded(self) -> bool:
        return self.context is not None


def _alternate_queries(concept: str, topic: str) -> list[str]:
    """Phrasings that surface different passages for the same idea.

    A textbook rarely uses the syllabus wording, so the concept name alone
    often misses the section that actually explains it.
    """
    return [
        f"{concept} definition explanation",
        f"{topic} {concept} example",
        f"how {concept} works step by step",
    ]


def _grade(context: GroundedContext, *, concept: str, topic: str,
           subject: str, level: str) -> ContextGrade:
    return grade_context(context.text, concept=concept, topic=topic,
                         subject=subject, level=level)


def recover(
    db: Session,
    *,
    concept: str,
    topic: str,
    subject: str,
    subject_id: int | None,
    level: str,
    allow_web: bool = True,
) -> Recovery:
    """Try progressively harder to find material that can teach a concept."""
    attempts: list[str] = []

    # 1. Re-query with alternate phrasings, still scoped to the subject.
    for query in _alternate_queries(concept, topic):
        attempts.append(f"retry:{query[:40]}")
        matches = search(db, query, top_k=8, subject_id=subject_id)
        try:
            context = build_context(matches)
        except InsufficientContext:
            continue
        grade = _grade(context, concept=concept, topic=topic,
                       subject=subject, level=level)
        if grade.usable:
            return Recovery(context, grade, "knowledge_base", attempts)

    # 2. Widen: the material may be filed under another subject, which is
    #    common for shared foundations like graph theory or probability.
    attempts.append("widen:all-subjects")
    matches = search(db, f"{concept} {topic}", top_k=10)
    try:
        context = build_context(matches)
        grade = _grade(context, concept=concept, topic=topic,
                       subject=subject, level=level)
        if grade.usable:
            return Recovery(context, grade, "knowledge_base", attempts)
    except InsufficientContext:
        pass

    # 3. Web, with citations. Last because it is the only source the
    #    student cannot check against a book they own.
    if allow_web:
        attempts.append("web:grounded")
        try:
            result = ai_client.generate_grounded(
                f"Explain {concept} in {topic} ({subject}) for the GATE CSE "
                f"exam, at {level} level. Be precise and include the standard "
                f"definitions and formulas."
            )
            text = (result.get("text") or "").strip()
            citations = result.get("citations") or []
            if text and citations:
                context = GroundedContext(
                    text=text[:MAX_WEB_CHARS],
                    chunk_ids=[],
                    citations=[
                        f"{c.get('title') or 'web'} — {c.get('uri', '')}"
                        for c in citations
                    ],
                )
                return Recovery(context, None, "web", attempts)
        except Exception as exc:
            logger.warning("Web recovery failed for %s: %s", concept, exc)

    return Recovery(None, None, "none", attempts)
