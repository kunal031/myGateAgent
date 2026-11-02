"""Create the chapter level and attach every topic to one.

Adds `syllabus_chapters`, plus `topics.chapter_id` and `topics.sequence`,
then fills them from `data/chapters.py`.

Nothing is destroyed and no id changes. 1,953 questions, 1,294 cards, 282
concepts, 27 papers and 11 mistake rows point at `topics.id`; they are
untouched, which is the whole reason this adds a parent rather than
renaming the levels. A migration that moved those ids would fail silently
-- a question detached from its topic still renders, it just stops
counting towards anything.

Idempotent: re-running updates the mapping in place rather than inserting
duplicate chapters, so a partial failure can simply be re-run.

    python -m app.cli.migrate_chapters --dry-run     # show, change nothing
    python -m app.cli.migrate_chapters
    python -m app.cli.migrate_chapters --target aiven
"""

import argparse

from sqlalchemy import create_engine, text

from ..core.config import settings
from ..data.chapters import CHAPTER_MAP, topic_to_chapter, validate_unique

DDL = [
    (
        "create syllabus_chapters",
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_name='syllabus_chapters'",
        """CREATE TABLE syllabus_chapters (
               id          SERIAL PRIMARY KEY,
               subject_id  INTEGER NOT NULL REFERENCES subjects(id),
               name        VARCHAR(200) NOT NULL,
               slug        VARCHAR(200) NOT NULL,
               summary     TEXT DEFAULT '',
               sequence    INTEGER DEFAULT 0,
               exam_weight DOUBLE PRECISION DEFAULT 1.0,
               created_at  TIMESTAMP DEFAULT now()
           )""",
    ),
    (
        # The predicate names the table as well as the index. An earlier
        # version checked the index name alone, which collided with an
        # identically named index on the unused `chapters` table: the step
        # reported "already done" and the constraint was never created, so
        # duplicate chapters were silently accepted.
        "unique index on (subject_id, slug)",
        "SELECT 1 FROM pg_indexes WHERE tablename='syllabus_chapters' "
        "AND indexname='ix_syllabus_chapter_subject_slug'",
        "CREATE UNIQUE INDEX ix_syllabus_chapter_subject_slug "
        "ON syllabus_chapters (subject_id, slug)",
    ),
    (
        "add topics.chapter_id",
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name='topics' AND column_name='chapter_id'",
        "ALTER TABLE topics ADD COLUMN chapter_id INTEGER "
        "REFERENCES syllabus_chapters(id)",
    ),
    (
        "index topics.chapter_id",
        "SELECT 1 FROM pg_indexes WHERE indexname='ix_topics_chapter_id'",
        "CREATE INDEX ix_topics_chapter_id ON topics (chapter_id)",
    ),
    (
        "add topics.sequence",
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name='topics' AND column_name='sequence'",
        "ALTER TABLE topics ADD COLUMN sequence INTEGER DEFAULT 0",
    ),
]


def _engine(target: str):
    dsn = settings._normalise_dsn(
        settings.POSTGRESQL_AIVEN_URI if target == "aiven" else settings.POSTGRES_URL
    )
    if not dsn:
        raise SystemExit(f"No connection string configured for {target!r}")
    return create_engine(dsn, connect_args={"connect_timeout": 30})


def migrate(target: str = "local", *, dry_run: bool = False) -> None:
    # The mapping is checked before anything is written. A topic slug that
    # does not resolve would otherwise leave that topic chapterless, and a
    # silently unmapped topic is how a subject's questions go missing from
    # the breakdown.
    problems = validate_unique()
    if problems:
        raise SystemExit("Mapping is inconsistent:\n  " + "\n  ".join(problems))

    engine = _engine(target)
    mapping = topic_to_chapter()

    with engine.begin() as conn:
        subjects = {
            slug: sid
            for sid, slug in conn.execute(text("SELECT id, slug FROM subjects"))
        }
        db_topics = {
            slug: (tid, subj)
            for tid, slug, subj in conn.execute(text(
                "SELECT t.id, t.slug, s.slug FROM topics t "
                "JOIN subjects s ON s.id = t.subject_id"
            ))
        }

        unmapped = sorted(set(db_topics) - set(mapping))
        unknown = sorted(set(mapping) - set(db_topics))
        if unknown:
            raise SystemExit(
                "These mapped topics do not exist in the database:\n  "
                + "\n  ".join(unknown)
            )

        print(f"[{target}] {len(db_topics)} topics, "
              f"{sum(len(c) for c in CHAPTER_MAP.values())} chapters to create")
        if unmapped:
            # Not fatal: chapter_id is nullable and these show as
            # "Unassigned". Reported so the gap is visible.
            print(f"[{target}] WARNING: {len(unmapped)} topic(s) unmapped, "
                  f"will show as Unassigned: {', '.join(unmapped)}")

        if dry_run:
            print(f"\n[{target}] --dry-run: no changes written\n")
            for subject, chapters in CHAPTER_MAP.items():
                print(f"  {subject}")
                for seq, (slug, name, topics) in enumerate(chapters):
                    print(f"    {seq}. {name}  ({slug})")
                    for t in topics:
                        mark = "" if t in db_topics else "  <-- NOT IN DB"
                        print(f"         - {t}{mark}")
            return

        for label, predicate, statement in DDL:
            if conn.execute(text(predicate)).first():
                print(f"[{target}] already done: {label}")
            else:
                conn.execute(text(statement))
                print(f"[{target}] applied:    {label}")

        created = updated = attached = 0
        for subject_slug, chapters in CHAPTER_MAP.items():
            subject_id = subjects.get(subject_slug)
            if subject_id is None:
                print(f"[{target}] skipping unknown subject {subject_slug!r}")
                continue

            for chapter_seq, (chap_slug, chap_name, topic_slugs) in enumerate(chapters):
                existing = conn.execute(text(
                    "SELECT id FROM syllabus_chapters "
                    "WHERE subject_id=:s AND slug=:c"
                ), {"s": subject_id, "c": chap_slug}).first()

                if existing:
                    chapter_id = existing[0]
                    conn.execute(text(
                        "UPDATE syllabus_chapters SET name=:n, sequence=:q "
                        "WHERE id=:i"
                    ), {"n": chap_name, "q": chapter_seq, "i": chapter_id})
                    updated += 1
                else:
                    chapter_id = conn.execute(text(
                        "INSERT INTO syllabus_chapters "
                        "(subject_id, name, slug, sequence) "
                        "VALUES (:s, :n, :c, :q) RETURNING id"
                    ), {"s": subject_id, "n": chap_name,
                        "c": chap_slug, "q": chapter_seq}).scalar()
                    created += 1

                for topic_seq, topic_slug in enumerate(topic_slugs):
                    entry = db_topics.get(topic_slug)
                    if entry is None:
                        continue
                    conn.execute(text(
                        "UPDATE topics SET chapter_id=:c, sequence=:q WHERE id=:i"
                    ), {"c": chapter_id, "q": topic_seq, "i": entry[0]})
                    attached += 1

        print(f"\n[{target}] {created} chapter(s) created, "
              f"{updated} updated, {attached} topic(s) attached")

        still = conn.execute(text(
            "SELECT count(*) FROM topics WHERE chapter_id IS NULL"
        )).scalar()
        print(f"[{target}] topics without a chapter: {still}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default="local", choices=["local", "aiven"])
    parser.add_argument("--dry-run", action="store_true",
                        help="print the mapping and exit without writing")
    args = parser.parse_args()
    migrate(args.target, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
