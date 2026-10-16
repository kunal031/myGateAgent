"""Parse RS Aggarwal's Quantitative Aptitude into questions.

The book is a scan, so its text comes from vision OCR, but the OCR is clean
and the layout is strictly regular: numbered questions with lettered
options, then a dense answer table at the end of each chapter. That is
enough structure to parse deterministically, with no model calls -- which
matters at this size, where ~2,200 answered questions would otherwise be
thousands of requests.

Numbering restarts at every chapter, so questions and answers are paired
within a chapter and never across. Pairing globally would silently attach
chapter 3's answers to chapter 2's questions, and every one of them would
look plausible.
"""

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

#: "**106.** " -- a question or an answer-table entry opens this way.
_NUMBER = re.compile(r"\*\*(\d{1,3})\.\*\*\s")

#: "**1.** (c)" -- an answer-table cell.
_ANSWER_CELL = re.compile(r"\*\*(\d{1,3})\.\*\*\s*\(([a-e])\)")

#: "*(a)* text" or "(a) text" up to the next option or the end.
_OPTION = re.compile(
    r"\*?\(([a-e])\)\*?\s*(.+?)(?=\s*\*?\([a-e]\)\*?|\Z)", re.S | re.I,
)

#: The running page header names the chapter: "Decimal Fractions  57".
_PAGE_HEADER = re.compile(
    r"^\s*(?:\d{1,3}\s+)?([A-Z][A-Za-z&.,'\-\s]{4,44}?)\s+\d{1,3}\s*$", re.M,
)

#: Exam attributions such as "(S.S.C. 2004)" or "*(Section Officers',
#: 2003)*" follow the stem or trail the last option. Either way they are
#: provenance, not part of the question.
_EXAM_TAG = re.compile(
    r"[*_]*\((?:[A-Z][A-Za-z.&'\s]*,?\s*)?\d{4}\)[*_]*",
)

#: A table of answers rather than prose: many cells, little else.
MIN_ANSWER_CELLS = 6

#: Below this a "question" is a fragment -- a header, a stray number.
MIN_STEM_CHARS = 15


@dataclass
class ParsedQuestion:
    number: int
    stem: str
    options: list[dict]
    page_number: int
    answer: str = ""


@dataclass
class Chapter:
    name: str
    start_page: int
    end_page: int
    questions: list[ParsedQuestion] = field(default_factory=list)
    answers: dict[int, str] = field(default_factory=dict)


def is_answer_table(text: str) -> bool:
    """Whether a chunk is an answer key rather than questions.

    Density, not a heading: the heading is "### ANSWERS" on some pages and
    absent on others, but a key is always many numbered cells in little
    text.
    """
    cells = _ANSWER_CELL.findall(text)
    if len(cells) < MIN_ANSWER_CELLS:
        return False
    return len(cells) / max(len(text) / 100, 1) >= 1.2


def chapter_of(text: str) -> str | None:
    """The chapter name from a page's running header, if it has one."""
    match = _PAGE_HEADER.search(text[:300])
    if match is None:
        return None
    name = " ".join(match.group(1).split())
    # "Quantitative Aptitude" is the book title, printed on left-hand pages.
    if name.lower() in {"quantitative aptitude", "contents", "answers"}:
        return None
    return name if 4 <= len(name) <= 44 else None


def split_options(body: str) -> tuple[str, list[dict]]:
    """Separate a question stem from its lettered options."""
    first = re.search(r"\*?\([a-e]\)\*?", body, re.I)
    if first is None:
        return body.strip(), []

    stem = _EXAM_TAG.sub("", body[:first.start()]).strip(" :\n")
    options = []
    for letter, text in _OPTION.findall(body[first.start():]):
        cleaned = _EXAM_TAG.sub("", text.replace("---", " "))
        cleaned = " ".join(cleaned.split())
        if cleaned:
            options.append({"id": letter.upper(), "text": cleaned[:300]})
    return stem, options


def parse_chapters(rows: list[tuple[int, str]]) -> list[Chapter]:
    """Group the book's chunks into chapters with their questions and keys.

    `rows` is [(page_number, content)] in reading order.
    """
    chapters: list[Chapter] = []
    current: Chapter | None = None

    for page_number, content in rows:
        name = chapter_of(content)
        if name and (current is None or name != current.name):
            current = Chapter(name=name, start_page=page_number,
                              end_page=page_number)
            chapters.append(current)
        if current is None:
            continue
        current.end_page = page_number

        if is_answer_table(content):
            for number, letter in _ANSWER_CELL.findall(content):
                # First key wins: a number repeated across a page break is
                # the same answer printed twice.
                current.answers.setdefault(int(number), letter.upper())
            continue

        marks = list(_NUMBER.finditer(content))
        for index, match in enumerate(marks):
            end = marks[index + 1].start() if index + 1 < len(marks) else len(content)
            stem, options = split_options(content[match.end():end])
            if len(stem) < MIN_STEM_CHARS or len(options) < 2:
                continue
            current.questions.append(ParsedQuestion(
                number=int(match.group(1)),
                stem=" ".join(stem.split()),
                options=options,
                page_number=page_number,
            ))

    return chapters


def pair_answers(chapters: list[Chapter]) -> int:
    """Attach each chapter's answers to its own questions.

    Returns how many were paired. A question whose number has no key is
    left unanswered and the caller drops it -- an unverifiable answer is
    worse than a missing question, because it is practised as if correct.
    """
    paired = 0
    for chapter in chapters:
        # The same number can appear twice in a chapter when a page repeats
        # in the chunk overlap; keep the first, which is the real one.
        seen: set[int] = set()
        for question in chapter.questions:
            if question.number in seen:
                continue
            seen.add(question.number)
            letter = chapter.answers.get(question.number)
            if not letter:
                continue
            # The key must name an option the question actually offers.
            if letter not in {o["id"] for o in question.options}:
                continue
            question.answer = letter
            paired += 1
    return paired
