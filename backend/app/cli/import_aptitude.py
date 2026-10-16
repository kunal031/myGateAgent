"""Pull General Aptitude questions out of the ingested GATE papers.

Every GATE paper opens with ten General Aptitude questions, and nine papers
are already in the corpus with their official answer keys beside them. That
is ninety real exam questions, correctly answered, sitting unused while the
section showed as empty.

    ./venv/bin/python -m app.cli.import_aptitude --dry-run
    ./venv/bin/python -m app.cli.import_aptitude

Topic assignment is by content, not by position: GATE does not label which
of its ten are verbal and which are quantitative, and the mix changes year
to year.
"""

import argparse
import json
import re

from sqlalchemy import text

from ..core.database import SessionLocal
from ..models.models import Question, Subject, Topic
from ..models.papers import ImportStatus, PaperSource, QuestionPaper
from ..services.import_paper.parse import parse_questions
from ..services.import_paper.store import dedupe_key, negative_for

#: The aptitude section always leads the paper and ends where the subject
#: questions begin. Both markers appear verbatim in every paper from 2019 on.
_GA_START = re.compile(r"General\s+Aptitude", re.I)
#: The technical section's opening. Matched on a line of its own, because
#: a bare "Q.11" also occurs inside answer tables and cross-references.
_GA_END = re.compile(
    r"^\s*(?:Q\.?\s*11\b|Computer\s+Science\s+and\s+Information\s+Technology)",
    re.I | re.M,
)

#: GATE's aptitude section is always ten questions. Anything past the tenth
#: belongs to another section, whatever the markers say.
_GA_QUESTION = re.compile(r"^\s*Q\.?\s*(\d{1,2})\b", re.M)
MAX_GA_QUESTIONS = 10

#: The four seeded topics a GA question can belong to.
_TOPIC_SLUGS = (
    "verbal-aptitude", "quantitative-aptitude",
    "analytical-reasoning", "spatial-aptitude",
)

#: Where a question lands when classification fails entirely.
_FALLBACK_TOPIC = "quantitative-aptitude"

_CLASSIFY_PROMPT = """Sort each GATE General Aptitude question into one topic.

verbal-aptitude        language: grammar, vocabulary, analogies, sentence
                       completion, reading comprehension
quantitative-aptitude  arithmetic and data: ratios, percentages, speed,
                       probability, geometry, data interpretation
analytical-reasoning   deduction: puzzles, syllogisms, who-did-what,
                       statements and conclusions, set membership
spatial-aptitude       shapes and space: figures, folding, rotation,
                       mirrors, dice, visual patterns

Return JSON: {{"topics": ["verbal-aptitude", ...]}} with one entry per
question, in the order given.

QUESTIONS:
{questions}"""


def classify_topics(contents: list[str]) -> list[str]:
    """Sort questions into GA topics.

    Keyword rules were tried and are not good enough: "A court is to a judge
    as ___ is to a teacher" is an analogy with no vocabulary word in it, and
    a reasoning puzzle about four criminals reads as quantitative because it
    counts people. The model reads the question instead, and anything it
    cannot place falls back rather than failing the import.
    """
    from ..ai import client as ai_client
    from ..ai import models

    listing = "\n\n".join(
        f"{i + 1}. {c[:400]}" for i, c in enumerate(contents)
    )
    try:
        raw = ai_client.generate_text(
            _CLASSIFY_PROMPT.format(questions=listing),
            model=models.LIGHT,
            response_mime_type="application/json",
            temperature=0.0,
            interactive=True,
        )
        picked = json.loads(raw).get("topics") or []
    except Exception:
        picked = []

    out = []
    for i in range(len(contents)):
        slug = picked[i] if i < len(picked) else ""
        out.append(slug if slug in _TOPIC_SLUGS else _FALLBACK_TOPIC)
    return out


def aptitude_text(db, source_id: int) -> str:
    """The General Aptitude section of one paper, as text."""
    rows = db.execute(
        text("SELECT content FROM source_chunks WHERE source_id = :s "
             "ORDER BY page_number, chunk_index"),
        {"s": source_id},
    ).fetchall()
    whole = "\n".join(r[0] for r in rows)

    start = _GA_START.search(whole)
    if start is None:
        return ""
    tail = whole[start.start():]

    # Cut at the technical section if its heading is there.
    end = _GA_END.search(tail)
    if end is not None:
        tail = tail[:end.start()]

    # Then cut where the numbering stops being this section's. Markers
    # alone proved unreliable: one paper's heading matched a stray "Q.1"
    # and truncated to a single question, while another ran on into a
    # different discipline and offered soil-mechanics questions as
    # aptitude. These files concatenate several papers, so the numbering
    # restarts rather than passing ten -- the cut is the first number that
    # goes backwards, or the first above ten.
    highest = 0
    for match in _GA_QUESTION.finditer(tail):
        number = int(match.group(1))
        if number > MAX_GA_QUESTIONS or (highest and number < highest):
            tail = tail[:match.start()]
            break
        highest = max(highest, number)

    # A section with only one or two questions found is a boundary failure,
    # not a short paper; importing it would file a fragment.
    found = sum(1 for m in _GA_QUESTION.finditer(tail)
                if int(m.group(1)) <= MAX_GA_QUESTIONS)
    if found < 3:
        return ""

    return tail


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None,
                        help="only process this many papers")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        subject = db.query(Subject).filter(
            Subject.slug == "general-aptitude").first()
        if subject is None:
            raise SystemExit("No general-aptitude subject; seed the syllabus first.")

        topics = {
            t.slug: t for t in
            db.query(Topic).filter(Topic.subject_id == subject.id).all()
        }
        missing = set(_TOPIC_SLUGS) - set(topics)
        if missing:
            raise SystemExit(f"Missing topics: {sorted(missing)}")

        papers = db.execute(text(
            "SELECT id, file_name FROM sources "
            "WHERE file_name ILIKE 'GATE 20%' AND file_name NOT ILIKE '%ANS%' "
            "ORDER BY file_name"
        )).fetchall()
        if args.limit:
            papers = papers[:args.limit]

        seen = {
            dedupe_key(c) for (c,) in
            db.query(Question.content)
            .filter(Question.subject_id == subject.id).all()
        }

        stored = skipped = 0
        for source_id, file_name in papers:
            section = aptitude_text(db, source_id)
            if not section:
                print(f"  {file_name[:40]:42} no aptitude section found")
                continue

            parsed = parse_questions(section)
            year = re.search(r"(20\d{2})", file_name)
            year = int(year.group(1)) if year else None

            by_topic: dict[str, int] = {}
            candidates = []
            for item in parsed:
                key = dedupe_key(item["content"])
                if key in seen:
                    skipped += 1
                    continue
                seen.add(key)
                candidates.append(item)

            slugs = classify_topics([c["content"] for c in candidates]) \
                if candidates else []
            fresh = []
            for item, slug in zip(candidates, slugs):
                by_topic[slug] = by_topic.get(slug, 0) + 1
                fresh.append((slug, item))

            summary = " ".join(f"{s.split('-')[0]}={n}" for s, n in sorted(by_topic.items()))
            print(f"  {file_name[:40]:42} {len(parsed):3} parsed, "
                  f"{len(fresh):3} new  {summary}")

            if args.dry_run or not fresh:
                continue

            paper = QuestionPaper(
                name=f"{file_name.replace('.pdf', '')} — General Aptitude",
                subject_id=subject.id,
                topic_id=topics[_FALLBACK_TOPIC].id,
                source_kind=PaperSource.PDF,
                file_name=file_name,
                exam_year=year,
                source_label=f"GATE {year}" if year else "",
                import_status=ImportStatus.COMPLETE,
            )
            db.add(paper)
            db.flush()

            for slug, item in fresh:
                marks = item.get("marks") if item.get("marks") in (1, 2) else 1
                qtype = item["question_type"]
                db.add(Question(
                    subject_id=subject.id,
                    topic_id=topics[slug].id,
                    paper_id=paper.id,
                    question_type=qtype,
                    marks=marks,
                    negative_marks=negative_for(qtype, marks),
                    content=item["content"],
                    options=json.dumps(item["options"]) if item["options"] else None,
                    correct_answer=item["correct_answer"],
                    nat_min=item.get("nat_min"),
                    nat_max=item.get("nat_max"),
                    explanation="",
                    origin="PYQ",
                    exam_year=year,
                    source=f"GATE {year} General Aptitude" if year else "GATE GA",
                    is_pyq=True,
                    provenance=f"{file_name} (General Aptitude section)",
                    review_status="pending",
                ))
                stored += 1

            paper.question_count = len([f for f in fresh])
            db.commit()

        print(f"\n{stored} stored, {skipped} already present."
              + (" (dry run)" if args.dry_run else ""))
    finally:
        db.close()


if __name__ == "__main__":
    main()
