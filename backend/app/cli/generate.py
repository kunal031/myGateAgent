"""Generate concepts and feed cards from the ingested corpus.

    # one topic, both modes
    ./venv/bin/python -m app.cli.generate --topic cpu-scheduling

    # a whole subject, BASIC only
    ./venv/bin/python -m app.cli.generate --subject operating-systems --mode BASIC

Idempotent: a topic that already has concepts, or a concept that already has
cards in the requested mode, is skipped. Re-run freely as more sources land.
"""

import argparse

from ..core.database import SessionLocal
from ..models.concepts import StudyMode
from ..models.models import Subject, Topic
from ..services.generation.cards import generate_cards_for_topic
from ..services.generation.concepts import generate_concepts_for_topic
from ..services.generation.grounding import InsufficientContext

MODES = [StudyMode.BASIC, StudyMode.ADVANCED]


def run_topic(db, topic: Topic, modes: list[str], per_concept: int) -> None:
    print(f"\n{topic.name}")
    try:
        created = generate_concepts_for_topic(db, topic.id)
        if created:
            for concept in created:
                print(f"   {concept.sequence}. [{concept.introduced_in}] {concept.name}")
    except InsufficientContext as exc:
        print(f"   skipped: {exc}")
        return

    for mode in modes:
        result = generate_cards_for_topic(db, topic.id, mode, per_concept)
        print(f"   {mode}: {result['cards_created']} cards "
              f"across {result['concepts']} concepts "
              f"({result['skipped']} skipped)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topic", help="topic slug")
    parser.add_argument("--subject", help="subject slug: every topic in it")
    parser.add_argument("--mode", choices=MODES, help="default: both")
    parser.add_argument("--per-concept", type=int, default=3)
    args = parser.parse_args()

    modes = [args.mode] if args.mode else MODES
    db = SessionLocal()
    try:
        if args.topic:
            topics = db.query(Topic).filter(Topic.slug == args.topic).all()
        elif args.subject:
            subject = db.query(Subject).filter(Subject.slug == args.subject).first()
            if subject is None:
                raise SystemExit(f"No subject with slug {args.subject!r}")
            topics = db.query(Topic).filter(Topic.subject_id == subject.id).all()
        else:
            raise SystemExit("Pass --topic or --subject")

        if not topics:
            raise SystemExit("No matching topics")

        for topic in topics:
            run_topic(db, topic, modes, args.per_concept)
    finally:
        db.close()


if __name__ == "__main__":
    main()
