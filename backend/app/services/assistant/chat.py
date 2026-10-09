"""Answer a student's question from their own sources, or from the web.

The same retrieval the feed generator uses, so an explanation cites the
same books a card would. When the corpus does not actually answer the
question, the answer comes from grounded web search with URLs rather than
from memory -- and when the books cover it only partly, both are used.

The distinction that matters here is between retrieving text and answering
the question. With a corpus this size something loosely related comes back
for almost any query, so "did retrieval return anything" is not a usable
test; the material is graded instead.
"""

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from ...ai import client as ai_client
from ...ai.prompts import assistant as prompts
from ...models.assistant import LANGUAGE_NAMES, Language
from ...models.models import FeedCard, Subject
from ..generation.grading import grade_context
from ..generation.grounding import InsufficientContext, build_context
from ..retrieval.hybrid import search

logger = logging.getLogger(__name__)

# How much of the conversation to replay. Enough to follow a follow-up
# question, short enough to leave room for the retrieved material.
HISTORY_TURNS = 6

# Below this, the retrieved material does not answer the question well
# enough to rely on alone and the web is consulted as well. The grader's
# own threshold is lower because a card only has to be supported by its
# context; a tutor has to actually answer what was asked.
MIN_ANSWER_RELEVANCE = 0.55
MIN_ANSWER_SUFFICIENCY = 0.55


@dataclass
class Answer:
    text: str
    citations: list[str] = field(default_factory=list)
    source_type: str = "knowledge_base"


def _history_block(messages: list) -> str:
    if not messages:
        return ""
    recent = messages[-HISTORY_TURNS:]
    lines = [f"{m.role}: {m.content[:400]}" for m in recent]
    return "Conversation so far:\n" + "\n".join(lines) + "\n\n"


def _card_block(card: FeedCard | None) -> str:
    """The card the student clicked Explain on, if any."""
    if card is None:
        return ""
    return (
        "The student is looking at this card and wants it explained:\n"
        f"  {card.title}\n  {card.content[:800]}\n\n"
    )


def _subject_name(db: Session, subject_id: int | None) -> str:
    if subject_id is None:
        return "GATE CSE"
    name = db.query(Subject.name).filter(Subject.id == subject_id).scalar()
    return name or "GATE CSE"


def _web_lookup(query: str, *, card: FeedCard | None = None) -> tuple[str, list[str]]:
    """Grounded web search, returning (text, citations).

    Failures here are not fatal: the corpus half may still carry the answer,
    and a quota error should degrade the reply rather than break it.
    """
    focus = f"{card.title}: {query}" if card else query
    try:
        result = ai_client.generate_grounded(
            f"{focus}\n\nAnswer for a GATE CSE exam candidate. Be precise, "
            f"use the standard notation, and include a worked example where "
            f"one helps."
        )
    except Exception as exc:
        logger.warning("Web search failed (%s); answering from corpus", exc)
        return "", []

    citations = [
        f"{c.get('title') or 'web'} — {c.get('uri', '')}"
        for c in (result.get("citations") or [])
    ]
    return (result.get("text") or "").strip(), citations


def _merge_context(corpus_text: str, web_text: str) -> str:
    """Label each half so the model can prefer the student's own books."""
    if corpus_text and web_text:
        return (
            "From the student's own books and notes (prefer this where the "
            "two differ):\n---\n" + corpus_text +
            "\n---\n\nFrom a web search (use to fill what the books above "
            "do not cover):\n---\n" + web_text + "\n---"
        )
    return corpus_text or web_text


def answer(
    db: Session,
    query: str,
    *,
    language: str = Language.ENGLISH,
    subject_id: int | None = None,
    card: FeedCard | None = None,
    history: list | None = None,
) -> Answer:
    """Answer one question, grounded and cited."""
    # A card gives the search a much better query than the question alone,
    # which is often just "explain this".
    search_query = f"{card.title} {query}" if card else query
    scope = subject_id or (card.subject_id if card else None)

    matches = search(db, search_query, top_k=6, subject_id=scope)
    try:
        context = build_context(matches, min_chars=200)
        citations = context.citations
        context_text = context.text
    except InsufficientContext:
        context_text, citations = "", []

    # Grade what came back. Retrieval returning prose is not the same as the
    # corpus answering the question, and only the latter justifies skipping
    # the web.
    needs_web = not context_text
    if context_text:
        grade = grade_context(
            context_text, concept=query[:120], topic=query[:120],
            subject=_subject_name(db, scope), level="gate",
        )
        needs_web = (
            grade.verdict == "web"
            or grade.relevance < MIN_ANSWER_RELEVANCE
            or grade.sufficiency < MIN_ANSWER_SUFFICIENCY
        )
        if needs_web:
            logger.info(
                "Corpus weak for %r (relevance=%.2f sufficiency=%.2f); "
                "adding web search", query[:60], grade.relevance,
                grade.sufficiency,
            )

    web_text, web_citations = "", []
    if needs_web:
        web_text, web_citations = _web_lookup(query, card=card)

    if not context_text and not web_text:
        # Both halves failed, which is a genuine dead end rather than a
        # reason to answer from memory.
        return Answer(
            text="I could not find this in your books or on the web just "
                 "now. Try rephrasing it, or ask about a narrower piece.",
            citations=[],
            source_type="none",
        )

    if web_text and not context_text:
        source_type = "web"
    elif web_text:
        source_type = "hybrid"
    else:
        source_type = "knowledge_base"

    context_text = _merge_context(context_text, web_text)
    citations = citations + web_citations

    text = ai_client.generate_text(
        prompts.ANSWER_TEMPLATE.format(
            card_context=_card_block(card),
            context=context_text,
            history=_history_block(history or []),
            query=query,
        ),
        system_instruction=prompts.ANSWER_SYSTEM.format(
            language=LANGUAGE_NAMES.get(language, "English")
        ),
        temperature=0.3,
    )
    return Answer(text=text.strip(), citations=citations,
                  source_type=source_type)
