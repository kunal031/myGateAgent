"""Import parsed PYQ-book questions into the quiz bank.

Answers and solutions come from the book's own tables, parsed
deterministically, so nothing here depends on a model reading the paper.
Each question records the page it came from, and its worked solution is
stored for post-attempt review rather than shown alongside the question.
"""

import json
import logging
import re

from sqlalchemy.orm import Session

from ...models import *  # noqa: F401,F403  (register all tables)
from ...models.models import Question, Subject, Topic
from .pyq_book import (
    BookQuestion, Chapter, group_into_chapters, load_book_chunks,
    pair_questions_with_answers, parse_answer_tables, parse_questions,
    parse_solutions,
)

logger = logging.getLogger(__name__)

NEGATIVE_MARKS = {1: 0.33, 2: 0.66}

# Option lines read "(a) Number of attributes ..." down to the next option.
_OPTION = re.compile(r"\(([a-dA-D])\)\s*(.+?)(?=\n\s*\([a-dA-D]\)|\Z)", re.S)

# Running headers repeat on every page and are not part of the question.
_NOISE = re.compile(
    r"GATE Wallah CS & IT Topic wise PYQs|Design of springs|"
    r"^\s*\d+\.\d+\s*$|C\s*H\s*A\s*P\s*T\s*E\s*R",
    re.M,
)


def clean(text: str) -> str:
    text = _NOISE.sub(" ", text)
    return re.sub(r"[ \t]*\n[ \t]*", "\n", re.sub(r"[ \t]{2,}", " ", text)).strip()


def split_stem_and_options(raw: str) -> tuple[str, list[dict]]:
    """Separate the question stem from its lettered options."""
    body = clean(raw)
    first = _OPTION.search(body)
    if first is None:
        return body, []

    stem = body[:first.start()].strip()
    options = [
        {"id": letter.upper(), "text": clean(text)}
        for letter, text in _OPTION.findall(body[first.start():])
    ]
    return stem, options


# Every page carries a running header whose second line names the subject,
# e.g. "Database Management System" or "Programming and Data Structures".
_PAGE_HEADER = re.compile(
    r"GATE Wallah CS & IT Topic wise PYQs\s*\n\s*(?P<name>[^\n]{4,60}?)\s*\n\s*\d+\.\d+"
)

# The header names a chapter or a subject; both map onto a syllabus subject.
_HEADER_TO_SUBJECT: list[tuple[str, tuple[str, ...]]] = [
    ("databases", ("database", "rdbms", "sql", "transaction", "normalization",
                   "relational", "file structure")),
    ("operating-systems", ("operating system", "process", "deadlock", "memory management",
                           "synchronization", "cpu scheduling", "file system")),
    ("computer-networks", ("computer network", "network layer", "transport layer",
                           "data link", "application layer", "ip address")),
    ("theory-of-computation", ("theory of computation", "finite automata", "regular",
                               "context free", "turing", "undecidab", "pushdown")),
    ("compiler-design", ("compiler", "parsing", "lexical", "syntax directed",
                         "intermediate code", "runtime environment")),
    ("digital-logic", ("digital logic", "boolean", "combinational", "sequential circuit",
                       "number system", "k-map")),
    ("computer-organization-architecture", ("computer organization", "architecture",
                                            "cache", "pipelin", "instruction",
                                            "addressing mode", "memory hierarchy",
                                            "input output", "i/o")),
    ("algorithms", ("algorithm", "asymptotic", "greedy", "dynamic programming",
                    "divide and conquer", "graph algorithm", "sorting", "searching")),
    ("programming-data-structures", ("programming and data structures", "data structure",
                                     "linked list", "tree", "heap", "stack", "queue",
                                     "array", "pointer", "recursion", "hashing", "graph")),
    ("engineering-mathematics", ("engineering mathematics", "discrete", "linear algebra",
                                 "calculus", "probability", "combinatorics", "set theory",
                                 "graph theory", "matrix", "propositional")),
    ("general-aptitude", ("aptitude", "verbal", "quantitative", "analytical",
                          "spatial", "reasoning")),
]


# The publisher's template leaves this on chapter-opening pages.
_TEMPLATE_ARTIFACT = "design of springs"


def _header_name(pages: dict[int, str], page: int) -> str:
    match = _PAGE_HEADER.search(pages.get(page, ""))
    if match is None:
        return ""
    name = match.group("name").strip().lower()
    return "" if name == _TEMPLATE_ARTIFACT else name


def chapter_name(pages: dict[int, str], chapter: Chapter) -> str:
    """The chapter's own name, from the header repeated across its pages.

    The book is laid out subject -> chapter -> questions, and a chapter maps
    onto a syllabus topic ("Process Synchronization", "Data Link Layer").
    The opening page carries a template artifact instead, so the most common
    header across the chapter is used.
    """
    from collections import Counter

    names = [
        _header_name(pages, page)
        for page in range(chapter.start_page, chapter.end_page + 1)
    ]
    names = [n for n in names if n]
    return Counter(names).most_common(1)[0][0] if names else ""


def _match_topic(db: Session, subject: Subject, name: str) -> Topic | None:
    """Map a chapter name onto the best syllabus topic in that subject.

    Scores on shared significant words. Without this every question in a
    subject lands on that subject's first topic, which makes topic filters
    and the per-topic mistake registry meaningless.
    """
    if not name:
        return None

    words = {w for w in re.split(r"[^a-z0-9]+", name.lower()) if len(w) > 3}
    if not words:
        return None

    best, best_score = None, 0
    for topic in db.query(Topic).filter(Topic.subject_id == subject.id).all():
        topic_words = {
            w for w in re.split(r"[^a-z0-9]+", topic.name.lower()) if len(w) > 3
        }
        score = len(words & topic_words)
        if score > best_score:
            best, best_score = topic, score

    return best


def _subject_for_chapter(db: Session, chapter: Chapter, chunks) -> Subject | None:
    """Infer a chapter's subject from the running page header.

    The header names the chapter ("Trees") or the subject ("Programming and
    Data Structures"), so both are mapped. Matching on the syllabus subject
    name alone misses most chapters, since the book rarely repeats it.
    """
    pages: dict[int, str] = {}
    for chunk in chunks:
        pages.setdefault(chunk.page_number, chunk.content)

    headers = " ".join(
        _header_name(pages, page)
        for page in range(chapter.start_page, min(chapter.end_page + 2,
                                                  chapter.start_page + 6))
    )
    if not headers.strip():
        return None

    best, best_score = None, 0
    for slug, hints in _HEADER_TO_SUBJECT:
        score = sum(len(h) for h in hints if h in headers)
        if score > best_score:
            best, best_score = slug, score

    return db.query(Subject).filter(Subject.slug == best).first() if best else None


def import_book_questions(db: Session, *, limit: int | None = None) -> dict:
    """Store every safely-paired question, with its solution if present."""
    source, chunks = load_book_chunks(db)
    if source is None:
        return {"error": "PYQ book not ingested"}

    chapters = group_into_chapters(parse_questions(chunks),
                                   parse_answer_tables(chunks))
    solutions = parse_solutions(chapters, chunks)
    pair_questions_with_answers(chapters)

    page_text: dict[int, str] = {}
    for chunk in chunks:
        page_text.setdefault(chunk.page_number, chunk.content)

    stored = skipped = 0

    for chapter_index, chapter in enumerate(chapters):
        subject = _subject_for_chapter(db, chapter, chunks)
        if subject is None:
            skipped += len(chapter.questions)
            continue
        name = chapter_name(page_text, chapter)
        topic = _match_topic(db, subject, name) or (
            db.query(Topic).filter(Topic.subject_id == subject.id)
              .order_by(Topic.id).first()
        )
        if topic is None:
            skipped += len(chapter.questions)
            continue

        for question in chapter.questions:
            if question.answer is None:
                skipped += 1
                continue
            if limit is not None and stored >= limit:
                break

            stem, options = split_stem_and_options(question.text)
            if len(stem) < 25:
                skipped += 1
                continue
            if question.question_type in {"MCQ", "MSQ"} and len(options) < 2:
                skipped += 1
                continue
            if db.query(Question).filter(Question.content == stem).first():
                skipped += 1
                continue

            bounds = question.answer.nat_bounds if question.question_type == "NAT" else None
            answer = (f"{bounds[0]}" if bounds and bounds[0] == bounds[1]
                      else question.answer.options)
            if question.question_type == "NAT" and bounds is None:
                skipped += 1
                continue

            solution = solutions.get((chapter_index, question.number), "")

            db.add(Question(
                subject_id=subject.id,
                topic_id=topic.id,
                question_type=question.question_type,
                marks=question.marks,
                negative_marks=(NEGATIVE_MARKS.get(question.marks, 0.33)
                                if question.question_type == "MCQ" else 0.0),
                content=stem,
                options=json.dumps(options) if options else None,
                correct_answer=answer,
                nat_min=bounds[0] if bounds else None,
                nat_max=bounds[1] if bounds else None,
                explanation=clean(solution) or "Solution not available for this question.",
                difficulty="Standard GATE",
                source=f"GATE {question.exam_year}",
                is_pyq=True,
                exam_year=question.exam_year,
                origin="PYQ",
                provenance=f"{source.citation} (p. {question.page_number})",
                source_chunk_ids=str(question.chunk_id),
                review_status="approved",
            ))
            stored += 1

        db.commit()

    return {"stored": stored, "skipped": skipped,
            "solutions_available": len(solutions)}
