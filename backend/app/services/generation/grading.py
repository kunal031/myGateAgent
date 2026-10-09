"""Corrective and self-checking stages of the content pipeline.

Two judgements sit either side of generation:

  grade_context  before writing -- is the retrieved material good enough?
  check_card     after writing  -- is the card worth saving?

Both run on the light model. They are classification tasks, and running
them on the primary model would roughly triple the cost of every card.

Both fail open: a grader that errors returns "use"/"accept" rather than
blocking the pipeline. A judgement layer that silently halts generation is
worse than one that occasionally lets a weak card through, because the
card is reviewable and a stalled pipeline is invisible.
"""

import logging
from dataclasses import dataclass

from ...ai import client as ai_client
from ...ai import models
from ...ai.prompts import grading as prompts
from .grounding import parse_json_response

logger = logging.getLogger(__name__)

# Below this on any axis, the context is not worth writing from.
MIN_RELEVANCE = 0.5
MIN_SUFFICIENCY = 0.5
MIN_ON_LEVEL = 0.35      # looser: level is the easiest axis to misjudge

# Keep the judgement prompt small; the grader needs a sample, not everything.
GRADE_CONTEXT_CHARS = 4000


@dataclass
class ContextGrade:
    relevance: float
    sufficiency: float
    on_level: float
    verdict: str          # use | retry | web
    missing: str = ""

    @property
    def usable(self) -> bool:
        return (
            self.verdict == "use"
            and self.relevance >= MIN_RELEVANCE
            and self.sufficiency >= MIN_SUFFICIENCY
            and self.on_level >= MIN_ON_LEVEL
        )


@dataclass
class CardVerdict:
    grounded: bool
    useful: bool
    gate_fit: bool
    level_fit: bool
    verdict: str          # accept | reject
    reason: str = ""

    @property
    def accepted(self) -> bool:
        return self.verdict == "accept" and all(
            (self.grounded, self.useful, self.gate_fit, self.level_fit)
        )


def _as_float(value, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def grade_context(
    context: str, *, concept: str, topic: str, subject: str, level: str,
) -> ContextGrade:
    """Judge retrieved material before generating from it.

    This is the corrective stage: a poor grade routes to a retry with a
    different query, or to the web, instead of producing a weak card from
    material that never covered the concept.
    """
    try:
        raw = ai_client.generate_text(
            prompts.GRADE_CONTEXT_TEMPLATE.format(
                concept=concept, topic=topic, subject=subject, level=level,
                context=context[:GRADE_CONTEXT_CHARS],
            ),
            model=models.LIGHT,
            system_instruction=prompts.GRADE_CONTEXT_SYSTEM,
            response_mime_type="application/json",
            temperature=0.0,
        )
        data = parse_json_response(raw)
    except Exception as exc:
        logger.warning("Context grading failed (%s); proceeding ungraded", exc)
        return ContextGrade(1.0, 1.0, 1.0, "use")

    verdict = str(data.get("verdict", "use")).lower()
    return ContextGrade(
        relevance=_as_float(data.get("relevance"), 1.0),
        sufficiency=_as_float(data.get("sufficiency"), 1.0),
        on_level=_as_float(data.get("on_level"), 1.0),
        verdict=verdict if verdict in {"use", "retry", "web"} else "use",
        missing=str(data.get("missing", ""))[:200],
    )


def check_card(
    card: dict, context: str, *, concept: str, level: str, mode: str,
) -> CardVerdict:
    """Judge a generated card before saving it.

    This is the self-checking stage. The quote test in grounding.py catches
    a fabricated citation; this catches the subtler failures -- a card that
    is accurate but teaches nothing, or is pitched at the wrong level.
    """
    try:
        raw = ai_client.generate_text(
            prompts.CHECK_CARD_TEMPLATE.format(
                concept=concept, level=level, mode=mode,
                context=context[:GRADE_CONTEXT_CHARS],
                card_type=card.get("card_type", ""),
                title=card.get("title", ""),
                content=card.get("content", "")[:1500],
                takeaway=card.get("takeaway", ""),
            ),
            model=models.LIGHT,
            system_instruction=prompts.CHECK_CARD_SYSTEM,
            response_mime_type="application/json",
            temperature=0.0,
        )
        data = parse_json_response(raw)
    except Exception as exc:
        logger.warning("Card check failed (%s); accepting unchecked", exc)
        return CardVerdict(True, True, True, True, "accept")

    verdict = str(data.get("verdict", "accept")).lower()
    return CardVerdict(
        grounded=bool(data.get("grounded", True)),
        useful=bool(data.get("useful", True)),
        gate_fit=bool(data.get("gate_fit", True)),
        level_fit=bool(data.get("level_fit", True)),
        verdict=verdict if verdict in {"accept", "reject"} else "accept",
        reason=str(data.get("reason", ""))[:200],
    )
