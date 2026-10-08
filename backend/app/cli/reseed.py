"""Rewrite seeded content from app/data/ into the database.

Needed because seed text was persisted with literal backslash-n instead of
real newlines; fixing the source alone leaves the bad rows in place.

Only regenerates authored seed content (feed cards, questions). Never touches
attempts, the mistake registry, or anything else recording your actual study
history.

    ./venv/bin/python -m app.cli.reseed
"""

import argparse

from ..core.database import SessionLocal, engine, Base
from ..models.models import FeedCard, Question, Subject, Topic
from ..data.seeds import SEED_FEED_CARDS, SEED_QUESTIONS


def _lookup_maps(db):
    subjects = {s.slug: s.id for s in db.query(Subject).all()}
    topics = {
        f"{s_slug}:{t.slug}": t.id
        for s_slug, s_id in subjects.items()
        for t in db.query(Topic).filter(Topic.subject_id == s_id).all()
    }
    return subjects, topics


def reseed_content(dry_run: bool = False) -> dict:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    counts = {"feed_cards": 0, "questions": 0, "skipped": 0}

    try:
        subject_map, topic_map = _lookup_maps(db)
        if not subject_map:
            raise RuntimeError(
                "No subjects found. Start the API once to seed the syllabus first."
            )

        if dry_run:
            print(f"[dry-run] would replace "
                  f"{db.query(FeedCard).count()} feed cards and "
                  f"{db.query(Question).count()} questions")
            return counts

        # Questions first: FeedCard has no FK to Question, but attempts
        # reference questions, so preserve ids by updating in place where possible.
        db.query(FeedCard).delete()

        for fc in SEED_FEED_CARDS:
            sub_id = subject_map.get(fc["subject_slug"])
            top_id = topic_map.get(f"{fc['subject_slug']}:{fc['topic_slug']}")
            if not (sub_id and top_id):
                counts["skipped"] += 1
                continue
            db.add(FeedCard(
                subject_id=sub_id,
                topic_id=top_id,
                card_type=fc["card_type"],
                title=fc["title"],
                content=fc["content"],
                takeaway=fc["takeaway"],
                difficulty=fc["difficulty"],
                base_weight=fc.get("base_weight", 1),
            ))
            counts["feed_cards"] += 1

        # Update question text in place so existing attempts stay valid.
        for q in SEED_QUESTIONS:
            sub_id = subject_map.get(q["subject_slug"])
            top_id = topic_map.get(f"{q['subject_slug']}:{q['topic_slug']}")
            if not (sub_id and top_id):
                counts["skipped"] += 1
                continue

            existing = (
                db.query(Question)
                .filter(Question.content == q["content"])
                .first()
            ) or (
                db.query(Question)
                .filter(
                    Question.topic_id == top_id,
                    Question.question_type == q["question_type"],
                )
                .first()
            )

            target = existing or Question()
            target.subject_id = sub_id
            target.topic_id = top_id
            target.question_type = q["question_type"]
            target.marks = q["marks"]
            target.negative_marks = q["negative_marks"]
            target.content = q["content"]
            target.options = q["options"]
            target.correct_answer = q["correct_answer"]
            target.nat_min = q["nat_min"]
            target.nat_max = q["nat_max"]
            target.explanation = q["explanation"]
            target.difficulty = q["difficulty"]
            target.source = q.get("source", "GATE CSE")
            target.is_pyq = q.get("is_pyq", False)

            if existing is None:
                db.add(target)
            counts["questions"] += 1

        db.commit()
        return counts
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would change without writing")
    args = parser.parse_args()

    counts = reseed_content(dry_run=args.dry_run)
    if not args.dry_run:
        print(f"Reseeded {counts['feed_cards']} feed cards, "
              f"{counts['questions']} questions "
              f"({counts['skipped']} skipped: unknown subject/topic slug)")


if __name__ == "__main__":
    main()
