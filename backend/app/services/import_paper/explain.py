"""Write a solution for a question that arrived without one.

Three tiers, tried in order, each tagged with where it came from:

    book  the student's own corpus, cited to a page
    web   grounded search, cited to a URL
    ai    the model alone, cited to nothing

The order is a trust order. A solution quoting a textbook page can be
checked against that page; one the model wrote from memory cannot be checked
at all, and deserves the scepticism its badge invites. The tag travels with
the solution so the UI can say which it is, rather than presenting all three
as equally authoritative.
"""

import logging

from sqlalchemy.orm import Session

from ...ai import client as ai_client
from ..generation.grading import grade_context
from ..generation.grounding import InsufficientContext, build_context
from ..retrieval.hybrid import search

logger = logging.getLogger(__name__)

#: Below this the corpus is not actually answering the question, whatever
#: it returned. Matches the assistant's threshold for the same judgement.
MIN_RELEVANCE = 0.55
MIN_SUFFICIENCY = 0.55

_BOOK_PROMPT = """A GATE exam question and the reference material that covers it.

Question:
{question}

Correct answer: {answer}

Reference material:
---
{context}
---

Write the worked solution. Show why the answer is right, step by step, using
only the reference material. Where it rules out a wrong option, say so. Use
LaTeX for mathematics ($...$ inline). Be concise: this is revision, not a
lecture."""

_WEB_PROMPT = """A GATE exam question.

{question}

Correct answer: {answer}

Write the worked solution for a GATE CSE candidate. Show why the answer is
right, step by step, and rule out the wrong options where that helps. Use
LaTeX for mathematics ($...$ inline). Be concise."""


def _from_books(db: Session, question: str, answer: str, subject_id: int | None) -> dict | None:
    """Tier one: the student's own books, cited to a page."""
    try:
        matches = search(db, question[:400], top_k=6, subject_id=subject_id)
        context = build_context(matches, min_chars=200)
    except InsufficientContext:
        return None
    except Exception as exc:
        logger.warning("Corpus lookup failed (%s)", exc)
        return None

    grade = grade_context(
        context.text, concept=question[:120], topic=question[:120],
        subject="GATE CSE", level="gate", interactive=True,
    )
    if (grade.relevance < MIN_RELEVANCE
            or grade.sufficiency < MIN_SUFFICIENCY):
        return None

    text = ai_client.generate_text(
        _BOOK_PROMPT.format(
            question=question[:2000], answer=answer, context=context.text,
        ),
        temperature=0.2,
        interactive=True,
    )
    return {
        "explanation": text.strip(),
        "solution_source": "book",
        "citations": context.citations,
    }


def _from_web(question: str, answer: str) -> dict | None:
    """Tier two: grounded search, cited to URLs."""
    try:
        result = ai_client.generate_grounded(
            _WEB_PROMPT.format(question=question[:2000], answer=answer),
            interactive=True,
        )
    except Exception as exc:
        logger.warning("Grounded search failed (%s)", exc)
        return None

    text = (result.get("text") or "").strip()
    if not text:
        return None
    return {
        "explanation": text,
        "solution_source": "web",
        "citations": [
            f"{c.get('title') or 'web'} — {c.get('uri', '')}"
            for c in (result.get("citations") or [])
        ],
    }


def _from_model(question: str, answer: str) -> dict:
    """Tier three: the model alone. Always succeeds, trusted least."""
    text = ai_client.generate_text(
        _WEB_PROMPT.format(question=question[:2000], answer=answer),
        temperature=0.2,
        interactive=True,
    )
    return {
        "explanation": text.strip(),
        "solution_source": "ai",
        "citations": [],
    }


def explain(
    db: Session, question: str, answer: str, *, subject_id: int | None = None,
) -> dict:
    """Return {"explanation", "solution_source", "citations"}.

    Never raises: a question without a solution is still a usable question,
    so a total failure returns an empty explanation rather than losing the
    import it belongs to.
    """
    if not answer:
        # Explaining an answer nobody knows produces a confident guess, and
        # a wrong solution is worse than none.
        return {"explanation": "", "solution_source": "", "citations": []}

    try:
        found = _from_books(db, question, answer, subject_id)
        if found:
            return found

        found = _from_web(question, answer)
        if found:
            return found

        return _from_model(question, answer)
    except Exception as exc:
        logger.warning("Could not explain question (%s)", exc)
        return {"explanation": "", "solution_source": "", "citations": []}
