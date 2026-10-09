"""Work out what a request is asking for.

The assistant bar takes one box of free text and has to decide whether the
student wants cards in their feed or a conversation. Getting that wrong is
jarring, so it is classified explicitly rather than guessed from keywords.
"""

import logging
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ...ai import client as ai_client
from ...ai import models
from ...ai.prompts import assistant as prompts
from ...models.assistant import Language
from ...models.models import Subject
from ..generation.grounding import parse_json_response

logger = logging.getLogger(__name__)

VALID_LANGUAGES = {Language.ENGLISH, Language.HINDI, Language.HINGLISH}
VALID_LEVELS = {"foundational", "core", "advanced"}
VALID_CARD_TYPES = {"TRAP", "FORMULA", "CONCEPT", "SHORTCUT"}

# Devanagari, so a Hindi request is detected without an API call.
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")

# Phrases that clearly ask for material rather than an explanation.
_FEED_HINTS = re.compile(
    r"\b(give me|show me|cards?|feed|list|more on|traps? (in|on)|"
    r"formulas? (for|on)|practice)\b", re.I
)


@dataclass
class Intent:
    output: str = "chat"            # feed | chat
    subject_slug: str | None = None
    topic: str | None = None
    level: str | None = None
    card_type: str | None = None
    language: str = Language.ENGLISH
    clean_query: str = ""


def _fallback(query: str) -> Intent:
    """Classify without the model, for when the call fails."""
    return Intent(
        output="feed" if _FEED_HINTS.search(query) else "chat",
        language=Language.HINDI if _DEVANAGARI.search(query) else Language.ENGLISH,
        clean_query=query.strip(),
    )


def parse_intent(db: Session, query: str) -> Intent:
    subjects = db.query(Subject).all()
    listing = ", ".join(f"{s.slug} ({s.name})" for s in subjects)

    try:
        raw = ai_client.generate_text(
            prompts.INTENT_TEMPLATE.format(subjects=listing, query=query),
            model=models.LIGHT,
            system_instruction=prompts.INTENT_SYSTEM,
            response_mime_type="application/json",
            temperature=0.0,
        )
        data = parse_json_response(raw)
    except Exception as exc:
        logger.warning("Intent parsing failed (%s); using keyword fallback", exc)
        return _fallback(query)

    slugs = {s.slug for s in subjects}
    subject_slug = data.get("subject_slug")
    level = (data.get("level") or "").lower() or None
    card_type = (data.get("card_type") or "").upper() or None
    language = (data.get("language") or Language.ENGLISH).lower()

    return Intent(
        output="feed" if data.get("output") == "feed" else "chat",
        subject_slug=subject_slug if subject_slug in slugs else None,
        topic=(data.get("topic") or None),
        level=level if level in VALID_LEVELS else None,
        card_type=card_type if card_type in VALID_CARD_TYPES else None,
        language=language if language in VALID_LANGUAGES else Language.ENGLISH,
        clean_query=(data.get("clean_query") or query).strip(),
    )
