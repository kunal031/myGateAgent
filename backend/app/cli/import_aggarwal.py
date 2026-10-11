"""Import RS Aggarwal's answered questions into the quiz bank.

The book holds roughly 2,000 parseable questions, about half of which have
a verified answer in a chapter's key table. Only those are imported: an
answer that cannot be checked against the book is worse than a missing
question, because it is practised as if it were right.

Everything files under General Aptitude -> Quantitative Aptitude, since
that is what the book is. Each chapter becomes its own QuestionPaper, so
"Profit and Loss" can be drilled on its own from the paper picker without
fragmenting the four GA topics that mirror the real exam.

    ./venv/bin/python -m app.cli.import_aggarwal --dry-run
    ./venv/bin/python -m app.cli.import_aggarwal
    ./venv/bin/python -m app.cli.import_aggarwal --chapter "Percentage"
"""

import argparse
import json

from sqlalchemy import text

from ..core.database import SessionLocal
from ..models.models import Question, Subject, Topic
from ..models.papers import ImportStatus, PaperSource, QuestionPaper
from ..services.import_paper.aggarwal import pair_answers, parse_chapters
from ..services.import_paper.store import dedupe_key, negative_for

SOURCE_MATCH = "%agarwal%"
TOPIC_SLUG = "quantitative-aptitude"

#: A chapter with fewer answered questions than this is a parsing artefact
#: -- a stray running header that looked like a chapter name.
MIN_CHAPTER_QUESTIONS = 5


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--chapter", help="only this chapter, by name")
    parser.add_argument("--limit-per-chapter", type=int, default=None,
                        help="cap questions taken from each chapter")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        source = db.execute(text(
            "SELECT id, file_name FROM sources WHERE file_name ILIKE :m"
        ), {"m": SOURCE_MATCH}).first()
        if source is None:
            raise SystemExit("RS Aggarwal is not ingested; run app.cli.ingest first.")

        subject = db.query(Subject).filter(
            Subject.slug == "general-aptitude").first()
        topic = db.query(Topic).filter(
            Topic.slug == TOPIC_SLUG, Topic.subject_id == subject.id).first()
        if subject is None or topic is None:
            raise SystemExit("General Aptitude / Quantitative Aptitude is missing.")

        rows = db.execute(text(
            "SELECT page_number, content FROM source_chunks "
            "WHERE source_id = :s ORDER BY page_number, chunk_index"
        ), {"s": source.id}).fetchall()

        chapters = parse_chapters([(r[0], r[1]) for r in rows])
        pair_answers(chapters)

        if args.chapter:
            wanted = args.chapter.lower()
            chapters = [c for c in chapters if wanted in c.name.lower()]

        # Everything already filed under this subject, so a rerun adds only
        # what is new.
        seen = {
            dedupe_key(c) for (c,) in
            db.query(Question.content)
            .filter(Question.subject_id == subject.id).all()
        }

        stored = skipped = 0
        for chapter in chapters:
            answered = [q for q in chapter.questions if q.answer]
            if len(answered) < MIN_CHAPTER_QUESTIONS:
                continue
            if args.limit_per_chapter:
                answered = answered[:args.limit_per_chapter]

            fresh = []
            for q in answered:
                key = dedupe_key(q.stem)
                if key in seen:
                    skipped += 1
                    continue
                seen.add(key)
                fresh.append(q)

            print(f"  {chapter.name[:34]:36} {len(answered):4} answered, "
                  f"{len(fresh):4} new")
            if args.dry_run or not fresh:
                continue

            paper = QuestionPaper(
                name=f"RS Aggarwal — {chapter.name}",
                subject_id=subject.id,
                topic_id=topic.id,
                source_kind=PaperSource.PDF,
                file_name=source.file_name,
                source_label=f"RS Aggarwal: {chapter.name}"[:120],
                import_status=ImportStatus.COMPLETE,
                question_count=len(fresh),
            )
            db.add(paper)
            db.flush()

            for q in fresh:
                db.add(Question(
                    subject_id=subject.id,
                    topic_id=topic.id,
                    paper_id=paper.id,
                    question_type="MCQ",
                    marks=1,
                    negative_marks=negative_for("MCQ", 1),
                    content=q.stem,
                    options=json.dumps(q.options),
                    correct_answer=q.answer,
                    explanation="",
                    origin="PYQ",
                    source=f"RS Aggarwal: {chapter.name}"[:100],
                    is_pyq=False,
                    provenance=f"{source.file_name} — {chapter.name} "
                               f"(p. {q.page_number}, Q{q.number})",
                    review_status="pending",
                ))
                stored += 1

            db.commit()

        print(f"\n{stored} stored, {skipped} already present."
              + (" (dry run)" if args.dry_run else ""))
    finally:
        db.close()


if __name__ == "__main__":
    main()
