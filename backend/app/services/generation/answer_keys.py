"""Parse official GATE answer keys.

The keys are published as a table of
    Q.No | Type | Section | Key | Marks
which parses deterministically, so answers come from the official document
rather than from a model's reading of it. That matters: a wrong answer in a
quiz is worse than no quiz.
"""

import logging
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ...models.sources import Source, SourceChunk

logger = logging.getLogger(__name__)

# Rows survive PDF extraction as one field per line, but the published
# layouts differ between years: some papers put a session number on the same
# line as the question type ("1 MCQ"), others do not. One pattern covers both.
_ROW = re.compile(
    r"(?P<num>\d{1,3})\s*\n"
    # Session number, which appears inline ("1 MCQ") or on its own line.
    r"(?:\d+[ \t]*\n?[ \t]*)?"
    r"(?P<type>MCQ|MSQ|NAT)\s*\n"
    # Section is GA or CS, sometimes suffixed with the paper set (CS-1).
    r"(?P<section>GA|CS)(?:-\d)?\s*\n"
    r"(?P<key>[^\n]+?)\s*\n"
    r"(?P<marks>[12])\b",
    re.I,
)

# "MTA" means marks to all: the question was dropped, so it has no answer.
_NO_ANSWER = {"MTA", "MARKS TO ALL", "-"}

_YEAR = re.compile(r"\b(20\d{2})\b")
_SET = re.compile(r"Set[-\s]*(\d)", re.I)


@dataclass(frozen=True)
class AnswerKey:
    number: int
    question_type: str
    section: str      # GA or CS
    answer: str
    marks: int

    @property
    def is_range(self) -> bool:
        """NAT answers are often published as a tolerance range."""
        return self.question_type == "NAT" and (
            " to " in self.answer or ":" in self.answer or "-" in self.answer[1:]
        )

    def nat_bounds(self) -> tuple[float, float] | None:
        if self.question_type != "NAT":
            return None
        nums = re.findall(r"-?\d+(?:\.\d+)?", self.answer)
        if not nums:
            return None
        values = [float(n) for n in nums]
        return (min(values), max(values))


def parse_answer_key(text: str) -> list[AnswerKey]:
    keys: list[AnswerKey] = []
    for match in _ROW.finditer(text):
        answer = match.group("key").strip()
        if not answer or answer.upper() in _NO_ANSWER:
            continue
        if answer.lower() in {"key", "marks", "key/range (ky)"}:
            continue
        keys.append(AnswerKey(
            number=int(match.group("num")),
            question_type=match.group("type").upper(),
            section=match.group("section").upper(),
            answer=answer,
            marks=int(match.group("marks")),
        ))
    return keys


def paper_identity(file_name: str) -> tuple[int | None, int]:
    """Return (exam_year, set_number) parsed from a file name."""
    year = _YEAR.search(file_name)
    set_match = _SET.search(file_name)
    return (int(year.group(1)) if year else None,
            int(set_match.group(1)) if set_match else 1)


def load_keys_for_papers(db: Session) -> dict[tuple[int, int, str], AnswerKey]:
    """Build {(year, set, 'CS-12'): AnswerKey} across every ingested key."""
    index: dict[tuple[int, int, str], AnswerKey] = {}

    for source in db.query(Source).filter(Source.kind == "PYQ_ANSWER_KEY").all():
        year, set_no = paper_identity(source.file_name)
        if year is None:
            continue

        text = "\n".join(
            c.content for c in
            db.query(SourceChunk)
              .filter(SourceChunk.source_id == source.id)
              .order_by(SourceChunk.page_number, SourceChunk.chunk_index)
        )
        keys = parse_answer_key(text)
        for key in keys:
            index[(year, set_no, f"{key.section}-{key.number}")] = key

        logger.info("%s: %d keys", source.file_name, len(keys))

    return index
