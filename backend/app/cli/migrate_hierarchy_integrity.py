"""Make the database refuse a row whose ancestors contradict each other.

Every content table stores shortcut columns: a question carries
`topic_id` *and* `subject_id`, though the subject is already implied by
the topic. The shortcuts exist so analytics can group by subject without
joining through four tables, and they are worth keeping -- but nothing
stopped them drifting apart.

Demonstrated before writing this: `UPDATE questions SET subject_id = 1`
on a question whose topic belongs to subject 9 was **accepted**. Nothing
failed. That question would simply have been counted under the wrong
subject in every analytics query from then on -- the silent kind of
failure this codebase keeps producing.

Composite foreign keys close it. `questions(topic_id, subject_id)`
referencing `topics(id, subject_id)` means Postgres checks the pair, so
a subject that disagrees with its topic is rejected outright. The
shortcut columns stay, the queries stay fast, and the contradiction
becomes impossible rather than merely absent.

**`activity_events` is deliberately excluded.** It records the hierarchy
as it was when the event happened, which is history: refiling a concept
into another chapter later must not rewrite what you did last month.
Constraining it would force old events to follow the current taxonomy
and silently falsify the day report.

Idempotent -- every step checks the catalogue first -- so a partial
failure can simply be re-run.

    python -m app.cli.migrate_hierarchy_integrity --check     # report only
    python -m app.cli.migrate_hierarchy_integrity
    python -m app.cli.migrate_hierarchy_integrity --target neon
"""

import argparse

from sqlalchemy import create_engine, text

from ..core.config import settings

#: Unique keys the composite foreign keys point at. A composite FK needs
#: a matching unique constraint on the parent; the primary key alone is
#: not enough, since it covers only `id`.
PARENT_KEYS = [
    ("topics", "uq_topics_id_subject", "(id, subject_id)"),
    ("topics", "uq_topics_id_chapter", "(id, chapter_id)"),
    ("concepts", "uq_concepts_id_topic", "(id, topic_id)"),
    ("syllabus_chapters", "uq_chapters_id_subject", "(id, subject_id)"),
]

#: (child table, constraint, child columns, parent table, parent columns).
#:
#: Each pairs a shortcut column with the real parent link beside it, so
#: the two can never disagree. Nullable pairs are still safe: a composite
#: foreign key with any NULL column is not checked, which is exactly
#: right for an optional concept or an unassigned chapter.
COMPOSITE_FKS = [
    # A topic's chapter must belong to the topic's subject.
    ("topics", "fk_topic_chapter_subject", "(chapter_id, subject_id)",
     "syllabus_chapters", "(id, subject_id)"),

    # A concept's subject must match its topic's subject.
    ("concepts", "fk_concept_topic_subject", "(topic_id, subject_id)",
     "topics", "(id, subject_id)"),

    # A question's subject must match its topic's, and its concept must
    # live under that same topic.
    ("questions", "fk_question_topic_subject", "(topic_id, subject_id)",
     "topics", "(id, subject_id)"),
    ("questions", "fk_question_concept_topic", "(concept_id, topic_id)",
     "concepts", "(id, topic_id)"),

    # Same for cards.
    ("feed_cards", "fk_card_topic_subject", "(topic_id, subject_id)",
     "topics", "(id, subject_id)"),
    ("feed_cards", "fk_card_concept_topic", "(concept_id, topic_id)",
     "concepts", "(id, topic_id)"),

    ("question_papers", "fk_paper_topic_subject", "(topic_id, subject_id)",
     "topics", "(id, subject_id)"),

    ("mistake_registry", "fk_mistake_topic_subject", "(topic_id, subject_id)",
     "topics", "(id, subject_id)"),

    # Nullable on both sides: an exam spanning many topics has neither,
    # and the constraint is simply not checked for those rows.
    ("exam_sessions", "fk_session_topic_subject", "(topic_id, subject_id)",
     "topics", "(id, subject_id)"),

    ("source_chunks", "fk_chunk_topic_subject", "(topic_id, subject_id)",
     "topics", "(id, subject_id)"),
]

#: Run before adding anything: a constraint cannot be created while a row
#: violates it, and the error Postgres gives names the constraint rather
#: than the offending rows.
DRIFT_CHECKS = [
    ("questions with a subject that is not their topic's",
     """SELECT count(*) FROM questions q JOIN topics t ON t.id = q.topic_id
        WHERE q.subject_id <> t.subject_id"""),
    ("questions whose concept belongs to another topic",
     """SELECT count(*) FROM questions q JOIN concepts c ON c.id = q.concept_id
        WHERE q.topic_id <> c.topic_id"""),
    ("concepts with a subject that is not their topic's",
     """SELECT count(*) FROM concepts c JOIN topics t ON t.id = c.topic_id
        WHERE c.subject_id <> t.subject_id"""),
    ("cards with a subject that is not their topic's",
     """SELECT count(*) FROM feed_cards f JOIN topics t ON t.id = f.topic_id
        WHERE f.subject_id <> t.subject_id"""),
    ("cards whose concept belongs to another topic",
     """SELECT count(*) FROM feed_cards f JOIN concepts c ON c.id = f.concept_id
        WHERE f.topic_id <> c.topic_id"""),
    ("topics whose chapter belongs to another subject",
     """SELECT count(*) FROM topics t
        JOIN syllabus_chapters ch ON ch.id = t.chapter_id
        WHERE t.subject_id <> ch.subject_id"""),
    ("papers with a subject that is not their topic's",
     """SELECT count(*) FROM question_papers p JOIN topics t ON t.id = p.topic_id
        WHERE p.subject_id <> t.subject_id"""),
    ("mistakes with a subject that is not their topic's",
     """SELECT count(*) FROM mistake_registry m JOIN topics t ON t.id = m.topic_id
        WHERE m.subject_id <> t.subject_id"""),
]


def _engine(target: str):
    dsn = settings._normalise_dsn({
        "aiven": settings.POSTGRESQL_AIVEN_URI,
        "neon": settings.NEON_DATABASE_URL,
    }.get(target, settings.POSTGRES_URL))
    if not dsn:
        raise SystemExit(f"No connection string configured for {target!r}")
    return create_engine(dsn, connect_args={"connect_timeout": 30})


def check_drift(conn) -> int:
    """Report rows that already contradict themselves."""
    total = 0
    for label, query in DRIFT_CHECKS:
        count = conn.execute(text(query)).scalar() or 0
        total += count
        flag = "  " if count == 0 else "<-"
        print(f"  {flag} {count:>4}  {label}")
    return total


def migrate(target: str = "local", *, check_only: bool = False) -> None:
    engine = _engine(target)

    with engine.begin() as conn:
        print(f"[{target}] existing contradictions:\n")
        drift = check_drift(conn)
        print()

        if drift:
            raise SystemExit(
                f"{drift} row(s) already contradict themselves. The "
                "constraints cannot be added until those are corrected, "
                "because Postgres validates against existing rows.\n"
                "Fix them first -- the queries above identify each set."
            )

        if check_only:
            print(f"[{target}] no contradictions. --check made no changes.")
            return

        added = 0
        for table, name, columns in PARENT_KEYS:
            exists = conn.execute(text(
                "SELECT 1 FROM pg_constraint WHERE conname = :n"
            ), {"n": name}).first()
            if exists:
                print(f"[{target}] already present: {name}")
                continue
            conn.execute(text(
                f"ALTER TABLE {table} ADD CONSTRAINT {name} UNIQUE {columns}"
            ))
            print(f"[{target}] added unique:  {name} on {table} {columns}")
            added += 1

        for child, name, child_cols, parent, parent_cols in COMPOSITE_FKS:
            exists = conn.execute(text(
                "SELECT 1 FROM pg_constraint WHERE conname = :n"
            ), {"n": name}).first()
            if exists:
                print(f"[{target}] already present: {name}")
                continue
            conn.execute(text(
                f"ALTER TABLE {child} ADD CONSTRAINT {name} "
                f"FOREIGN KEY {child_cols} REFERENCES {parent} {parent_cols}"
            ))
            print(f"[{target}] added FK:      {name} "
                  f"{child}{child_cols} -> {parent}{parent_cols}")
            added += 1

        print(f"\n[{target}] {added} constraint(s) added.")
        print("A write that contradicts the hierarchy now raises "
              "IntegrityError instead of being accepted.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default="local",
                        choices=["local", "aiven", "neon"])
    parser.add_argument("--check", action="store_true",
                        help="report contradictions without changing anything")
    args = parser.parse_args()
    migrate(args.target, check_only=args.check)


if __name__ == "__main__":
    main()
