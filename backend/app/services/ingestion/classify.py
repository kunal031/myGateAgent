"""Classify an inbox file: what kind of source it is, and which subject.

Runs before any API call, so misfiled material is caught without spending
quota. Everything here is pattern matching on paths and names; the UI can
correct a wrong guess.
"""

import re
from pathlib import Path

from ...models.sources import SourceKind

# Subject slug <- filename keywords. Order matters: more specific first.
SUBJECT_PATTERNS: list[tuple[str, list[str]]] = [
    ("theory-of-computation", ["theory of computation", "toc", "automata"]),
    ("computer-organization-architecture", [
        "computer organization", "coa", "architecture"]),
    ("programming-data-structures", [
        "data structure", "c programming", "programming"]),
    ("engineering-mathematics", [
        "engineering mathematics", "discrete mathematics", "discrete math",
        "dm notes", "linear algebra", "probability"]),
    ("operating-systems", ["operating system", "operating systems", "os notes"]),
    ("computer-networks", ["computer network", "networks", "cn notes"]),
    ("databases", ["dbms", "database", "databases"]),
    ("compiler-design", ["compiler"]),
    ("digital-logic", ["digital logic", "digital design"]),
    ("algorithms", ["algorithm"]),
    ("general-aptitude", ["aptitude", "general aptitude"]),
]

# Files that are present but must never enter the knowledge base: mock-test
# score screenshots carry no study content and would only waste quota and
# dilute retrieval.
EXCLUDE_PATTERNS = [
    "test marks", "flt ", "aimt", "gate result", "ans_key_sheet",
]

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif"}
DOC_SUFFIXES = {".pdf", ".docx", ".pptx", ".txt", ".md"}

_YEAR = re.compile(r"\b(20\d{2})\b")


def _normalise(text: str) -> str:
    """Lowercase and flatten separators so '04_Digital_Logic' matches
    'digital logic'."""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def detect_subject_slug(path: Path) -> str | None:
    haystack = _normalise(f"{path.parent.name} {path.stem}")
    for slug, keywords in SUBJECT_PATTERNS:
        if any(_normalise(k) in haystack for k in keywords):
            return slug
    return None


def detect_exam_year(path: Path) -> int | None:
    match = _YEAR.search(path.stem)
    if match:
        year = int(match.group(1))
        if 1990 <= year <= 2030:
            return year
    return None


def classify(path: Path, inbox_root: Path) -> dict:
    """Return the metadata for one file, without opening it."""
    rel = path.relative_to(inbox_root)
    rel_str = str(rel).lower()
    stem = path.stem.lower()
    suffix = path.suffix.lower()

    if any(p in rel_str for p in EXCLUDE_PATTERNS):
        kind = SourceKind.EXCLUDED
    elif suffix in IMAGE_SUFFIXES:
        kind = SourceKind.CONCEPT_IMAGE
    elif "syllabus" in stem:
        kind = SourceKind.SYLLABUS
    elif "strategy" in stem:
        kind = SourceKind.STRATEGY
    elif "ans" in stem and ("key" in stem or stem.endswith(" ans")):
        kind = SourceKind.PYQ_ANSWER_KEY
    elif rel_str.startswith("pyq/topicwise") or "topicwise" in stem:
        kind = SourceKind.PYQ_TOPICWISE
    elif rel_str.startswith("pyq/") or detect_exam_year(path):
        kind = SourceKind.PYQ_PAPER
    elif rel_str.startswith("notes/"):
        kind = SourceKind.HANDWRITTEN_NOTES
    else:
        kind = SourceKind.TEXTBOOK

    # Attribution, so every derived card can credit the real author.
    author = ""
    origin = ""
    if "github-priyanshu" in rel_str:
        author = "Priyanshu, GATE 2024 AIR 379"
        origin = "https://github.com/Priyanshuu-2109/GATE-CSE-notes"
    elif "handwritten-air50" in rel_str:
        author = "AIR < 50 topper handwritten notes"
    elif "karan-suthar" in rel_str:
        author = "Karan Suthar"
    elif "karumanchi" in stem:
        author = "Narasimha Karumanchi"
    elif "gate wallah" in stem or "physics wallah" in stem:
        author = "GATE Wallah (Physics Wallah)"

    return {
        "kind": kind,
        "subject_slug": detect_subject_slug(path),
        "exam_year": detect_exam_year(path),
        "author_credit": author,
        "origin": origin,
        "file_type": suffix.lstrip("."),
        "relative_path": str(rel),
        "is_supported": suffix in DOC_SUFFIXES or suffix in IMAGE_SUFFIXES,
    }
