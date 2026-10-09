"""Parse the GATE Wallah topicwise PYQ book.

Each chapter is laid out in three parts, and all three are used:

  questions  "N. [MCQ] [GATE-2023: 1M]" followed by the stem and options
  answer key a compact table of "N. (b)" or "N. (511 to 511)" for NAT
  solutions  "N. (b)" followed by the full worked reasoning

The answer key and solutions are parsed deterministically rather than by a
model, so a quiz answer always comes from the book rather than from an
interpretation of it.
"""

import logging
import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from ...models.sources import Source, SourceChunk

logger = logging.getLogger(__name__)

# "12." then "(b)" or "(511 to 511)", possibly across a line break.
_ANSWER_ROW = re.compile(
    r"(?<!\d)(?P<num>\d{1,3})\.\s*\n?\s*\((?P<key>[a-dA-D](?:\s*,\s*[a-dA-D])*|[^)]{1,40}?)\)"
)

# A chapter heading carries the running subject name on each page.
_CHAPTER = re.compile(r"C\s*H\s*A\s*P\s*T\s*E\s*R\s*\n\s*(\d+)", re.I)

# Question header: number, type tag, then the GATE year and marks.
_Q_HEADER = re.compile(
    r"(?<!\d)(?P<num>\d{1,3})\.\s*\[(?P<type>MCQ|MSQ|NAT)\]\s*\n?\s*"
    r"\[GATE[-\s]*(?P<year>\d{4})\s*:?\s*(?P<marks>[12])\s*M\]",
    re.I,
)

_NAT_RANGE = re.compile(r"(-?\d+(?:\.\d+)?)\s*to\s*(-?\d+(?:\.\d+)?)", re.I)

# A chapter's answer table follows its questions within a few pages: the
# questions, then the key, then the solutions.
MAX_TABLE_DISTANCE_PAGES = 30


@dataclass
class BookAnswer:
    number: int
    raw: str

    @property
    def is_nat(self) -> bool:
        return bool(_NAT_RANGE.search(self.raw)) or self.raw.replace(".", "").isdigit()

    @property
    def nat_bounds(self) -> tuple[float, float] | None:
        match = _NAT_RANGE.search(self.raw)
        if match:
            return (float(match.group(1)), float(match.group(2)))
        try:
            value = float(self.raw)
            return (value, value)
        except ValueError:
            return None

    @property
    def options(self) -> str:
        """Option letters, upper-cased, comma-joined for MSQ."""
        letters = re.findall(r"[a-dA-D]", self.raw)
        return ",".join(sorted({l.upper() for l in letters}))


@dataclass
class BookQuestion:
    number: int
    question_type: str
    exam_year: int
    marks: int
    page_number: int
    chunk_id: int
    text: str = ""
    solution: str = ""
    answer: BookAnswer | None = None


def parse_answer_tables(chunks: list[SourceChunk]) -> dict[int, dict[int, BookAnswer]]:
    """Find compact answer tables and index them by page.

    A key table is dense: many "N. (x)" rows and little prose. Solution
    pages also start with "N. (x)" but are mostly explanation, so density
    separates the two reliably.
    """
    tables: dict[int, dict[int, BookAnswer]] = {}
    for chunk in chunks:
        rows = _ANSWER_ROW.findall(chunk.content)
        if len(rows) < 6:
            continue
        density = len(rows) / max(len(chunk.content) / 100, 1)
        if density < 1.5:
            continue
        tables[chunk.page_number] = {
            int(num): BookAnswer(int(num), key.strip())
            for num, key in rows
        }
    return tables


def parse_questions(chunks: list[SourceChunk]) -> list[BookQuestion]:
    """Extract every question header with its stem text.

    Chunks overlap, so the same question appears more than once. The first
    occurrence is kept, since it carries the fuller stem.
    """
    found: list[BookQuestion] = []
    seen: set[tuple[int, int, int]] = set()
    for chunk in chunks:
        matches = list(_Q_HEADER.finditer(chunk.content))
        for index, match in enumerate(matches):
            start = match.end()
            end = (matches[index + 1].start()
                   if index + 1 < len(matches) else len(chunk.content))
            identity = (int(match.group("num")), int(match.group("year")),
                        chunk.page_number)
            if identity in seen:
                continue
            seen.add(identity)
            found.append(BookQuestion(
                number=int(match.group("num")),
                question_type=match.group("type").upper(),
                exam_year=int(match.group("year")),
                marks=int(match.group("marks")),
                page_number=chunk.page_number,
                chunk_id=chunk.id,
                text=chunk.content[start:end].strip(),
            ))
    return found


def load_book_chunks(db: Session) -> tuple[Source | None, list[SourceChunk]]:
    source = db.query(Source).filter(Source.kind == "PYQ_TOPICWISE").first()
    if source is None:
        return None, []
    chunks = (
        db.query(SourceChunk)
        .filter(SourceChunk.source_id == source.id)
        .order_by(SourceChunk.page_number, SourceChunk.chunk_index)
        .all()
    )
    return source, chunks


@dataclass
class Chapter:
    """One chapter: its questions, its answer table, and its solutions."""
    start_page: int
    end_page: int
    questions: list[BookQuestion] = field(default_factory=list)
    answers: dict[int, BookAnswer] = field(default_factory=dict)
    answer_page: int | None = None


def group_into_chapters(
    questions: list[BookQuestion],
    tables: dict[int, dict[int, BookAnswer]],
) -> list[Chapter]:
    """Split questions at each numbering reset, then attach the answer table.

    Question numbers restart at every chapter, and so do answer tables, so
    pairing has to be chapter-scoped. Matching globally would silently give
    questions the wrong answers, which is worse than having no answers.
    """
    chapters: list[Chapter] = []
    current: list[BookQuestion] = []
    previous_number = 0

    for question in questions:
        if question.number < previous_number and current:
            chapters.append(Chapter(current[0].page_number,
                                    current[-1].page_number, current))
            current = []
        current.append(question)
        previous_number = question.number

    if current:
        chapters.append(Chapter(current[0].page_number,
                                current[-1].page_number, current))

    # Match each chapter to its answer table by highest question number.
    #
    # Neither page order nor ordinal position works: there are more detected
    # chapters than tables (a chapter split across a page break looks like
    # two), and a chapter's table can be printed past the page where the next
    # chapter's questions begin. The highest number in a chapter and in its
    # table are the same value, which identifies the pair unambiguously, and
    # requiring the table to come after the questions prevents matching a
    # same-sized chapter earlier in the book.
    unused = dict(tables)
    for chapter in chapters:
        if not chapter.questions:
            continue
        highest = max(q.number for q in chapter.questions)
        for page in sorted(unused):
            table = unused[page]
            # A chapter's table is printed soon after its questions. Without
            # this bound, a short chapter can match a same-sized table from
            # a later chapter and inherit entirely wrong answers.
            if page - chapter.end_page > MAX_TABLE_DISTANCE_PAGES:
                break
            if page >= chapter.end_page and max(table) == highest:
                chapter.answer_page = page
                chapter.answers = table
                del unused[page]
                break

    return chapters


def pair_questions_with_answers(chapters: list[Chapter]) -> list[BookQuestion]:
    """Attach each question its answer, dropping unsafe pairings.

    A NAT question whose answer is an option letter (or the reverse) means
    the pairing slipped: the answer table and the questions are out of step,
    usually where a chapter boundary was misread. Those are dropped rather
    than stored, since a confidently wrong answer in a quiz is worse than a
    missing question.
    """
    paired: list[BookQuestion] = []
    for chapter in chapters:
        for question in chapter.questions:
            answer = chapter.answers.get(question.number)
            if answer is None:
                continue
            if (question.question_type == "NAT") != answer.is_nat:
                logger.debug("Dropping #%s: type/answer mismatch", question.number)
                continue
            if question.question_type != "NAT" and not answer.options:
                continue
            question.answer = answer
            paired.append(question)
    return paired


# A solution block starts "12. (a)" then runs until the next such marker.
_SOLUTION_START = re.compile(
    r"(?<!\d)(?P<num>\d{1,3})\.\s*\n?\s*\((?P<key>[a-dA-D](?:\s*,\s*[a-dA-D])*|[^)]{1,40}?)\)",
)


def parse_solutions(
    chapters: list[Chapter], chunks: list[SourceChunk]
) -> dict[tuple[int, int], str]:
    """Extract worked solutions, keyed by (chapter index, question number).

    Solutions are printed after the answer table and before the next
    chapter, so the page range is known once tables are matched. They are
    shown only when reviewing an attempt, never alongside the question.
    """
    by_page: dict[int, list[SourceChunk]] = {}
    for chunk in chunks:
        by_page.setdefault(chunk.page_number, []).append(chunk)

    solutions: dict[tuple[int, int], str] = {}

    for index, chapter in enumerate(chapters):
        if chapter.answer_page is None:
            continue
        next_start = (chapters[index + 1].start_page
                      if index + 1 < len(chapters) else 10**6)

        text = "\n".join(
            c.content
            for page in range(chapter.answer_page + 1, next_start)
            for c in by_page.get(page, [])
        )
        if not text.strip():
            continue

        markers = list(_SOLUTION_START.finditer(text))
        for position, match in enumerate(markers):
            number = int(match.group("num"))
            if number not in chapter.answers:
                continue
            start = match.end()
            end = (markers[position + 1].start()
                   if position + 1 < len(markers) else len(text))
            body = text[start:end].strip()
            # Keep the fullest version: chunk overlap repeats some blocks.
            if len(body) > len(solutions.get((index, number), "")):
                solutions[(index, number)] = body

    return solutions
