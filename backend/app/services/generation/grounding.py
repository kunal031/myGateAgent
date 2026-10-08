"""Shared grounding helpers for all generated content.

The rule this file enforces: nothing reaches the database without a citation
to a real source chunk. That is checked structurally here rather than hoped
for in a prompt.
"""

import json
import logging
import re
from dataclasses import dataclass

from ...services.retrieval.hybrid import Match

logger = logging.getLogger(__name__)

# Enough context to write from, short enough to stay well inside the model's
# useful attention and the free-tier token budget.
MAX_CONTEXT_CHARS = 9000


class InsufficientContext(RuntimeError):
    """Raised when retrieval found too little material to generate from."""


@dataclass
class GroundedContext:
    text: str
    chunk_ids: list[int]
    citations: list[str]

    @property
    def provenance(self) -> str:
        """All sources in the context. Used only when a card names none."""
        return " | ".join(self.citations)

    def cite(self, source_number: int | None) -> tuple[str, str]:
        """Resolve a 1-based source number to (citation, chunk_id).

        A card that names the one source it used gets a citation the student
        can actually open. Listing every retrieved page, as the first version
        did, is not a citation -- it is a disclaimer.
        """
        if source_number and 1 <= source_number <= len(self.citations):
            index = source_number - 1
            return self.citations[index], str(self.chunk_ids[index])
        return self.provenance, ",".join(str(c) for c in self.chunk_ids)


def build_context(matches: list[Match], *, min_chars: int = 400) -> GroundedContext:
    """Assemble retrieved chunks into a prompt context block.

    Raises InsufficientContext when there is too little to write from, so a
    thin topic produces no cards rather than invented ones.
    """
    if not matches:
        raise InsufficientContext("No source material retrieved")

    parts, chunk_ids, citations, used = [], [], [], 0
    for match in matches:
        body = match.content.strip()
        if not body:
            continue
        if used + len(body) > MAX_CONTEXT_CHARS:
            break
        parts.append(f"[Source {len(parts) + 1} — {match.citation}]\n{body}")
        chunk_ids.append(match.chunk_id)
        citations.append(match.citation)
        used += len(body)

    if used < min_chars:
        raise InsufficientContext(
            f"Only {used} characters of source material; need at least {min_chars}"
        )

    return GroundedContext(
        text="\n\n".join(parts), chunk_ids=chunk_ids, citations=citations
    )


_JSON_BLOCK = re.compile(r"\{.*\}", re.S)

# Backslash sequences JSON actually defines. Anything else -- \log, \Theta,
# \frac and the rest of LaTeX -- is an invalid escape that makes the whole
# reply unparseable, losing every card in the batch.
_VALID_JSON_ESCAPE = re.compile(r'\\(["\\\\/bfnrtu])')
_LONE_BACKSLASH = re.compile(r'\\(?!["\\\\/bfnrtu])')


def _escape_latex_backslashes(text: str) -> str:
    """Double any backslash that is not a valid JSON escape.

    Cards are full of LaTeX, so the model routinely emits `$O(n \log n)$`
    inside a JSON string. That is invalid JSON. Doubling the lone
    backslashes makes it parseable and leaves the LaTeX intact once decoded.
    """
    return _LONE_BACKSLASH.sub(r"\\\\", text)


def parse_json_response(raw: str) -> dict:
    """Parse a model JSON reply, tolerating code fences, prose and LaTeX."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)

    for candidate in (text, _escape_latex_backslashes(text)):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    match = _JSON_BLOCK.search(text)
    if not match:
        raise json.JSONDecodeError("No JSON object in reply", text, 0)

    block = match.group(0)
    try:
        return json.loads(block)
    except json.JSONDecodeError:
        return json.loads(_escape_latex_backslashes(block))


def is_supported(claim: str, context: str, *, min_overlap: float = 0.45) -> bool:
    """Cheap check that a card's quoted support really appears in the context.

    The model is asked to quote the line it relied on. Comparing word overlap
    catches the case where it quotes something that was never in the sources,
    which is the signature of a fabricated card. This is a guard rail, not
    proof -- the citation stored on the card is what makes a claim auditable.
    """
    if not claim:
        return False
    words = {w for w in re.findall(r"[a-z0-9]+", claim.lower()) if len(w) > 3}
    if not words:
        return False
    haystack = set(re.findall(r"[a-z0-9]+", context.lower()))
    return len(words & haystack) / len(words) >= min_overlap
