"""Answer a student's question from their own sources.

The same retrieval the feed generator uses, so an explanation cites the
same books a card would. When the corpus does not cover the question, the
answer comes from grounded web search with URLs rather than from memory.
"""

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from ...ai import client as ai_client
from ...ai.prompts import assistant as prompts
from ...models.assistant import LANGUAGE_NAMES, Language
from ...models.models import FeedCard, Subject
from ..generation.grounding import InsufficientContext, build_context
from ..retrieval.hybrid import search

logger = logging.getLogger(__name__)

# How much of the conversation to replay. Enough to follow a follow-up
# question, short enough to leave room for the retrieved material.
HISTORY_TURNS = 6


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
        source_type = "knowledge_base"
        context_text = context.text
    except InsufficientContext:
        # Nothing in the student's books covers this, so go to the web
        # rather than answering from memory.
        logger.info("No corpus coverage for %r; using grounded web search", query[:60])
        result = ai_client.generate_grounded(
            f"{query}\n\nAnswer for a GATE CSE exam candidate. Be precise."
        )
        return Answer(
            text=result.get("text", "").strip(),
            citations=[f"{c.get('title') or 'web'} — {c.get('uri', '')}"
                       for c in (result.get("citations") or [])],
            source_type="web",
        )

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
    return Answer(text=text.strip(), citations=citations, source_type=source_type)
