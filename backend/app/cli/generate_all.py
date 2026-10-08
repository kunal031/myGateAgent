"""Generate concepts and cards for every topic the corpus can support.

Ingestion only fills the corpus; it does not create cards. This walks the
whole syllabus, skipping topics with too little source material and those
already done, so it can be re-run as ingestion progresses.

    ./venv/bin/python -m app.cli.generate_all
    ./venv/bin/python -m app.cli.generate_all --dry-run   # no API calls
"""

import argparse

from ..ai.rate_limit import DailyQuotaExceeded, generation_limiter
from ..core.database import SessionLocal
from ..models.concepts import Concept, StudyMode
from ..models.models import FeedCard, Subject, Topic
from ..services.generation.cards import generate_cards_for_topic
from ..services.generation.concepts import generate_concepts_for_topic
from ..services.generation.grounding import InsufficientContext, build_context
from ..services.retrieval.hybrid import search


def topic_is_ready(db, topic: Topic) -> bool:
    """Cheap keyword-only check, so a dry run costs no quota."""
    matches = search(db, topic.name, top_k=8,
                     subject_id=topic.subject_id, semantic=False)
    try:
        build_context(matches)
        return True
    except InsufficientContext:
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="report which topics are ready, make no API calls")
    parser.add_argument("--per-concept", type=int, default=3)
    parser.add_argument("--subject", help="limit to one subject slug")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        query = db.query(Topic).join(Subject, Topic.subject_id == Subject.id)
        if args.subject:
            query = query.filter(Subject.slug == args.subject)
        topics = query.order_by(Subject.weightage_marks.desc(), Topic.id).all()

        ready, thin, done, cards = [], [], 0, 0

        for topic in topics:
            if db.query(Concept).filter(Concept.topic_id == topic.id).count():
                done += 1
                continue
            (ready if topic_is_ready(db, topic) else thin).append(topic)

        print(f"{len(topics)} topics: {done} already generated, "
              f"{len(ready)} ready, {len(thin)} too thin\n")

        if args.dry_run:
            for topic in ready:
                print(f"  ready  {topic.name[:60]}")
            print(f"\nEstimated cost: ~{len(ready) * 7} API calls "
                  f"({generation_limiter.remaining_today()} remaining today)")
            return

        for topic in ready:
            print(f"\n{topic.name}")
            try:
                concepts = generate_concepts_for_topic(db, topic.id)
                print(f"   {len(concepts)} concepts")
                for mode in (StudyMode.BASIC, StudyMode.ADVANCED):
                    result = generate_cards_for_topic(
                        db, topic.id, mode, args.per_concept)
                    cards += result["cards_created"]
                    print(f"   {mode}: {result['cards_created']} cards")
            except DailyQuotaExceeded as exc:
                print(f"\nStopped: {exc}")
                break
            except InsufficientContext as exc:
                print(f"   skipped: {exc}")
            except Exception as exc:
                print(f"   failed: {type(exc).__name__}: {str(exc)[:90]}")

        print(f"\n{cards} cards created. "
              f"Feed now has {db.query(FeedCard).count()} cards.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
