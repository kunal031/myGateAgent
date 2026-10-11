"""Turn a page or PDF of questions into structured rows.

The model does the structuring. A regex pass was tried against the layout
these pages use and is not worth keeping: question numbering restarts,
options appear as "A:", "(a)" or "a)" depending on the source, NAT answers
have no options at all, and code blocks inside a stem contain the same
punctuation the delimiters use. A model reads all of those correctly, and
the result is checked rather than trusted.

What is *not* left to the model is scoring. Question type decides negative
marking -- MCQ loses a third of a mark, MSQ and NAT lose nothing -- so a
type inferred wrongly silently mis-scores every attempt. Type is therefore
derived from the answer's own shape wherever that shape is unambiguous, and
the model's opinion is used only as a fallback.
"""

import json
import logging
import re

from ...ai import client as ai_client
from ...ai import models

logger = logging.getLogger(__name__)

#: One batch of page text per model call. Large enough for a whole topic
#: page, small enough to stay well inside the context window with room for
#: the reply.
BATCH_CHARS = 60_000

VALID_TYPES = {"MCQ", "MSQ", "NAT"}


def _response_schema():
    """Constrain the reply so the API guarantees well-formed JSON.

    Question stems carry C code, so replies routinely contain backslashes
    and newlines that have to survive JSON escaping. Repairing the text
    afterwards worked only sometimes -- the same page parsed on one call and
    failed on the next. A schema moves the problem to the API, which encodes
    the strings correctly in the first place.
    """
    from google.genai import types

    return types.Schema(
        type=types.Type.OBJECT,
        properties={
            "questions": types.Schema(
                type=types.Type.ARRAY,
                items=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "content": types.Schema(type=types.Type.STRING),
                        "options": types.Schema(
                            type=types.Type.ARRAY,
                            items=types.Schema(
                                type=types.Type.OBJECT,
                                properties={
                                    "id": types.Schema(type=types.Type.STRING),
                                    "text": types.Schema(type=types.Type.STRING),
                                },
                                required=["id", "text"],
                            ),
                        ),
                        "correct_answer": types.Schema(type=types.Type.STRING),
                        "question_type": types.Schema(type=types.Type.STRING),
                        "marks": types.Schema(type=types.Type.INTEGER),
                        "exam_year": types.Schema(type=types.Type.INTEGER),
                        "source_label": types.Schema(type=types.Type.STRING),
                    },
                    required=["content", "correct_answer", "question_type"],
                ),
            ),
        },
        required=["questions"],
    )

#: "A", "A,C", "B, D" -- the letters an option answer can take.
_LETTER_ANSWER = re.compile(r"^[A-D](\s*,\s*[A-D])*$", re.I)
#: "21", "-3.5", "0.75" -- a bare number, which only a NAT has.
_NUMERIC_ANSWER = re.compile(r"^-?\d+(\.\d+)?$")
#: "14 to 15" or "14.0 - 15.0" -- a NAT accepted over a range.
_RANGE_ANSWER = re.compile(
    r"^(-?\d+(?:\.\d+)?)\s*(?:to|-|–)\s*(-?\d+(?:\.\d+)?)$", re.I,
)

#: "Question 12:", "Q.7", "14." at the head of a stem. The page's own
#: numbering is not part of the question, and carrying it through means the
#: same question imported twice does not look the same.
_LEADING_NUMBER = re.compile(
    r"^\s*(?:Question|Ques|Q)\s*[.:]?\s*\d+\s*[.:)\]]?\s+"
    # A bare "14." only counts as numbering when whitespace follows, so a
    # stem opening with a decimal such as "12.5 kbps" keeps its number.
    r"|^\s*\d{1,3}\s*[.)]\s+",
    re.I,
)

_PROMPT = """Extract every exam question from the text below.

Return JSON: {{"questions": [...]}} where each question has:
  "content"      the full question text, including any code, as it appears
  "options"      [{{"id": "A", "text": "..."}}] or [] for numeric answers
  "correct_answer"  "A" or "A,C" for options; the number for numeric answers
  "question_type"   MCQ (one correct option), MSQ (several), NAT (numeric)
  "marks"        1 or 2 if stated, else 1
  "exam_year"    the year as an integer if shown, else null
  "source_label" the exam label as printed, e.g. "GATE CSE 2024 SET-2"

Rules:
- Copy question text verbatim. Keep code blocks, subscripts and symbols.
- Do not invent an answer. If the text does not give one, use "".
- Option ids are always uppercase letters starting at A.
- Ignore navigation, adverts, sign-up prompts and related-article lists.

TEXT:
{text}"""


def _batches(text: str) -> list[str]:
    """Split on blank lines so a question is never cut in half."""
    if len(text) <= BATCH_CHARS:
        return [text]

    chunks, current = [], ""
    for block in text.split("\n\n"):
        if len(current) + len(block) > BATCH_CHARS and current:
            chunks.append(current)
            current = block
        else:
            current = f"{current}\n\n{block}" if current else block
    if current:
        chunks.append(current)
    return chunks


def strip_numbering(content: str) -> str:
    """Drop a leading question number from a stem.

    The model sometimes keeps the page's numbering and sometimes does not,
    so the same question extracted twice differed only by a "Question 3: "
    prefix -- enough to slip past a content match and be stored twice.
    """
    return _LEADING_NUMBER.sub("", content, count=1).strip()


def infer_type(answer: str, options: list, model_guess: str) -> str:
    """Decide the question type, preferring evidence over the model.

    The answer's shape is decisive where it has one: a bare number cannot be
    an MCQ, and two letters cannot be anything but an MSQ. Only an ambiguous
    or missing answer falls back to what the model said.
    """
    answer = (answer or "").strip()
    guess = (model_guess or "").upper()

    if answer:
        if _NUMERIC_ANSWER.match(answer) or _RANGE_ANSWER.match(answer):
            return "NAT"
        if _LETTER_ANSWER.match(answer):
            letters = [p.strip() for p in answer.split(",") if p.strip()]
            return "MSQ" if len(letters) > 1 else "MCQ"

    if guess in VALID_TYPES:
        return guess
    # No answer and no usable hint: options mean a choice, absence means NAT.
    return "MCQ" if options else "NAT"


def normalise_answer(answer: str, qtype: str) -> tuple[str, float | None, float | None]:
    """Return (stored answer, nat_min, nat_max).

    A NAT given as a range keeps its bounds, because GATE accepts anything
    inside them; a single value becomes a zero-width range so scoring has
    one code path.
    """
    answer = (answer or "").strip()
    if qtype != "NAT":
        letters = [p.strip().upper() for p in answer.split(",") if p.strip()]
        return ",".join(sorted(set(letters))), None, None

    span = _RANGE_ANSWER.match(answer)
    if span:
        low, high = float(span.group(1)), float(span.group(2))
        if low > high:
            low, high = high, low
        return str(low), low, high
    if _NUMERIC_ANSWER.match(answer):
        value = float(answer)
        return answer, value, value
    return "", None, None


def _clean(item: dict) -> dict | None:
    """Validate and normalise one parsed question."""
    content = strip_numbering((item.get("content") or "").strip())
    # "Process is" and "Checkpointing a job" are real GATE stems whose
    # meaning lives in the options, so length alone cannot reject one.
    if not content:
        return None

    raw_options = item.get("options") or []
    options = []
    for option in raw_options:
        if not isinstance(option, dict):
            continue
        oid = str(option.get("id") or "").strip().upper()[:2]
        text = str(option.get("text") or "").strip()
        if oid and text:
            options.append({"id": oid, "text": text})

    qtype = infer_type(
        item.get("correct_answer", ""), options, item.get("question_type", ""),
    )
    answer, nat_min, nat_max = normalise_answer(
        item.get("correct_answer", ""), qtype,
    )

    # An option question needs options to be answerable at all.
    if qtype in {"MCQ", "MSQ"} and len(options) < 2:
        return None

    marks = item.get("marks")
    marks = marks if marks in (1, 2) else 1

    year = item.get("exam_year")
    year = year if isinstance(year, int) and 1980 < year < 2100 else None

    return {
        "content": content,
        "options": options,
        "correct_answer": answer,
        "question_type": qtype,
        "marks": marks,
        "nat_min": nat_min,
        "nat_max": nat_max,
        "exam_year": year,
        "source_label": str(item.get("source_label") or "").strip()[:120],
        # Flagged for the preview: these are the ones to ask the user about.
        "needs_answer": not answer,
    }


def parse_questions(text: str) -> list[dict]:
    """Structure raw page or PDF text into question dicts."""
    found: list[dict] = []
    seen: set[str] = set()

    for batch in _batches(text):
        try:
            raw = ai_client.generate_text(
                _PROMPT.format(text=batch),
                model=models.PRIMARY,
                response_mime_type="application/json",
                response_schema=_response_schema(),
                temperature=0.0,
                interactive=True,
            )
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning("Unparseable extraction reply (%s); skipping batch", exc)
            continue
        except Exception as exc:
            logger.warning("Extraction failed (%s); skipping batch", exc)
            continue

        items = payload.get("questions") if isinstance(payload, dict) else payload
        for item in items or []:
            if not isinstance(item, dict):
                continue
            cleaned = _clean(item)
            if cleaned is None:
                continue
            # The same question can appear twice when batches overlap a
            # boundary, and a page sometimes repeats one in a summary list.
            key = cleaned["content"][:160].lower()
            if key in seen:
                continue
            seen.add(key)
            found.append(cleaned)

    return found
