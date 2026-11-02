"""Copy one database into another, carrying the embeddings across.

Originally a one-way SQLite -> Postgres migration. Now also the way local
Postgres is pushed to Aiven, so the source is selectable: SQLite is a stale
pre-ingestion backup (2,590 chunks) and reading from it would silently
overwrite a full corpus with a snapshot.

The source is only read, never modified, so a failed run costs nothing.

    ./venv/bin/python -m app.cli.migrate_to_postgres --dry-run
    ./venv/bin/python -m app.cli.migrate_to_postgres --from-local --to-aiven
"""

import argparse
import json

import numpy as np
from sqlalchemy import create_engine, insert, inspect, select, text
from sqlalchemy.orm import sessionmaker

from ..core.config import settings
from ..core.database import Base
from .. import models  # noqa: F401  (register every table)

# Parents before children, so foreign keys resolve as rows land.
# Parent before child throughout: every table here is inserted in this
# order, so a foreign key always finds its target already present.
#
# Checked against the live schema by `audit_tables()` before any copy
# runs. An earlier version of this list was four tables short -- users,
# syllabus_chapters, activity_events and pending_oauth -- and a copy made
# with it would have silently left the target with no accounts and no
# chapter layer, which is exactly the kind of loss that looks like a
# successful migration.
TABLE_ORDER = [
    # Accounts first: almost everything below carries user_id.
    "users",
    "subjects",
    # The chapter layer sits between subjects and topics.
    "syllabus_chapters", "topics", "concepts",
    # The older, unpopulated taxonomy. Copied for completeness; all empty.
    "chapters", "syllabus_topics", "subtopics", "syllabus_concepts",
    "sources", "source_chunks",
    # Papers precede questions: a question carries paper_id.
    "question_papers", "questions", "feed_cards",
    "concept_tags", "feed_card_tags",
    "attempts", "mistake_registry", "concept_progress",
    "card_views",
    "exam_sessions", "exam_items",
    "assistant_threads", "assistant_messages",
    "activity_events",
    # In-flight sign-ins. Copied so the list is exhaustive; rows are
    # short-lived and almost always zero.
    "pending_oauth",
    # One row per live refresh token. Carried so a migration does not
    # sign every device out: a token whose row is missing is treated as
    # pre-rotation and adopted, which works but loses the reuse
    # detection that row existed for.
    "refresh_sessions",
]

#: Never copied, and each for a reason.
#:
#: alembic_version is the TARGET's own record of which migrations it has
#: run. Copying the source's value would tell the target it is at a
#: revision it may never have applied -- the next `upgrade head` would
#: then skip real work and leave the schema short. The target is stamped
#: or upgraded by Alembic itself, not by this script.
EXCLUDED_TABLES = {"alembic_version"}

# Postgres rejects a text value in a halfvec column, so the embedding is
# never copied as an ordinary column. It is carried separately: from the
# source's own halfvec column when migrating Postgres -> Postgres, or from
# the .npy store when the source is SQLite.
SKIP_COLUMNS = {"source_chunks": {"embedding"}}

VECTOR_DIR = settings.DATA_DIR / "vectors"


def _safe(dsn: str) -> str:
    """Hide the password before printing a connection string."""
    import re
    return re.sub(r"://([^:/@]+):[^@]+@", r"://\1:***@", dsn)


def _engines(postgres_url: str, *, source_url: str | None = None):
    """Build (source, target). The source defaults to SQLite for the
    original migration path; --from-local points it at local Postgres."""
    source = create_engine(source_url or settings.SQLITE_URL)
    target = create_engine(postgres_url, connect_args={"connect_timeout": 30})
    return source, target


def add_missing_columns(target_engine, *, dry_run: bool) -> list[str]:
    """Add columns the models declare but an older target lacks.

    Base.metadata.create_all only creates missing tables; it never alters an
    existing one. A target seeded before a column was added therefore stays
    behind forever, and the mismatch surfaces only as an INSERT failing on
    an unknown column -- after a --replace has already emptied it.

    Only additive changes are made: a nullable column with no default, which
    is safe to apply to a populated table and cannot destroy data. Type
    changes and drops are deliberately not attempted.
    """
    from sqlalchemy.schema import CreateColumn

    inspector = inspect(target_engine)
    present_tables = set(inspector.get_table_names())
    added: list[str] = []

    for name in TABLE_ORDER:
        table = Base.metadata.tables.get(name)
        if table is None or name not in present_tables:
            continue
        existing = {c["name"] for c in inspector.get_columns(name)}
        for column in table.columns:
            if column.name in existing:
                continue
            ddl = str(CreateColumn(column).compile(dialect=target_engine.dialect))
            # Strip constraints that cannot be added to existing rows.
            ddl = ddl.replace(" NOT NULL", "")
            added.append(f"{name}.{column.name}")
            if not dry_run:
                with target_engine.begin() as conn:
                    conn.execute(text(
                        f"ALTER TABLE {name} ADD COLUMN IF NOT EXISTS {ddl}"
                    ))
    return added


def truncate_target(target_engine, *, dry_run: bool) -> None:
    """Empty the target's copied tables so a resync replaces rather than
    collides. Children first is unnecessary under one TRUNCATE ... CASCADE,
    but the explicit list keeps anything outside TABLE_ORDER untouched.
    """
    present = set(inspect(target_engine).get_table_names())
    targets = [n for n in TABLE_ORDER if n in present]
    if dry_run or not targets:
        return
    with target_engine.begin() as conn:
        conn.execute(text(
            f"TRUNCATE TABLE {', '.join(targets)} RESTART IDENTITY CASCADE"
        ))


def copy_tables(source_engine, target_engine, *, dry_run: bool) -> dict:
    counts: dict[str, tuple[int, int]] = {}
    source_tables = set(inspect(source_engine).get_table_names())

    with source_engine.connect() as src, target_engine.begin() as dst:
        for name in TABLE_ORDER:
            if name not in source_tables:
                continue
            table = Base.metadata.tables.get(name)
            if table is None:
                continue

            skip = SKIP_COLUMNS.get(name, set())
            columns = [c.name for c in table.columns if c.name not in skip]

            rows = src.execute(
                text(f"SELECT {', '.join(columns)} FROM {name}")
            ).mappings().all()

            if dry_run:
                counts[name] = (len(rows), 0)
                continue

            if rows:
                # Chunked so a large table does not build one giant statement.
                for start in range(0, len(rows), 500):
                    dst.execute(insert(table), [dict(r) for r in rows[start:start + 500]])

            counts[name] = (len(rows), len(rows))

    return counts


def reset_sequences(target_engine) -> None:
    """Point each identity sequence past the highest copied id.

    Rows are inserted with explicit ids, which leaves Postgres' sequences at
    1 -- the next insert would collide. SQLite has no equivalent step, so
    this is easy to forget and only fails later.
    """
    with target_engine.begin() as conn:
        for name in TABLE_ORDER:
            table = Base.metadata.tables.get(name)
            if table is None or "id" not in table.columns:
                continue
            conn.execute(text(
                f"SELECT setval(pg_get_serial_sequence('{name}', 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {name}), 1), true)"
            ))


def load_vectors_from_npy(target_engine, *, dry_run: bool) -> int:
    """Move embeddings from the .npy store onto their chunk rows.

    Used only when the source is SQLite. The store is a stale pre-ingestion
    snapshot, so this is not the path for refreshing a cloud copy.
    """
    vectors_path = VECTOR_DIR / "chunks.npy"
    ids_path = VECTOR_DIR / "chunk_ids.json"
    if not (vectors_path.exists() and ids_path.exists()):
        return 0

    matrix = np.load(vectors_path)
    chunk_ids = json.loads(ids_path.read_text())
    if len(chunk_ids) != matrix.shape[0]:
        raise RuntimeError(
            f"Vector store is inconsistent: {len(chunk_ids)} ids, "
            f"{matrix.shape[0]} rows"
        )
    if dry_run:
        return len(chunk_ids)

    Session = sessionmaker(bind=target_engine)
    with Session() as session:
        for start in range(0, len(chunk_ids), 500):
            batch_ids = chunk_ids[start:start + 500]
            batch = matrix[start:start + 500]
            session.execute(
                text("UPDATE source_chunks SET embedding = :e WHERE id = :i"),
                [{"i": int(i), "e": str(v.tolist())}
                 for i, v in zip(batch_ids, batch)],
            )
            session.commit()

    return len(chunk_ids)


def copy_vectors_between_pg(source_engine, target_engine, *,
                            dry_run: bool) -> int:
    """Carry embeddings from one Postgres halfvec column to another.

    Read back as text and re-cast on write: that round-trip needs no pgvector
    adapter registered on either side, and the literal is exactly what a
    halfvec cast accepts. Batched because 13k rows of 3,072 dimensions is
    too much to hold in one statement, and streamed so the whole corpus is
    never resident at once.
    """
    with source_engine.connect() as src:
        total = src.execute(text(
            "SELECT count(*) FROM source_chunks WHERE embedding IS NOT NULL"
        )).scalar() or 0
        if dry_run or not total:
            return total

        moved = 0
        Session = sessionmaker(bind=target_engine)
        with Session() as session:
            result = src.execution_options(stream_results=True, max_row_buffer=500).execute(
                text("SELECT id, embedding::text AS e FROM source_chunks "
                     "WHERE embedding IS NOT NULL ORDER BY id")
            )
            while True:
                rows = result.fetchmany(500)
                if not rows:
                    break
                session.execute(
                    text("UPDATE source_chunks "
                         "SET embedding = CAST(:e AS halfvec) WHERE id = :i"),
                    [{"i": int(r.id), "e": r.e} for r in rows],
                )
                session.commit()
                moved += len(rows)
                print(f"    vectors copied: {moved:,}/{total:,}", flush=True)

    return moved


def create_indexes(target_engine) -> None:
    """HNSW for vectors, GIN for keyword search.

    The extension is created first: a managed instance starts without it,
    and the halfvec column cannot be indexed until it exists.
    """
    with target_engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_chunk_embedding_hnsw "
            "ON source_chunks USING hnsw (embedding halfvec_cosine_ops) "
            "WITH (m = 16, ef_construction = 64)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_chunk_content_fts "
            "ON source_chunks USING gin (to_tsvector('english', content))"
        ))


def audit_tables(source_engine) -> list[str]:
    """Tables present in the source but absent from TABLE_ORDER.

    Run before every copy. A table missing from the list is not an error
    the copy reports -- it simply never gets copied, and the target looks
    complete. That is how a previous resync lost the users table without
    anything failing.
    """
    with source_engine.connect() as conn:
        live = {
            row[0] for row in conn.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            ))
        }
    # EXCLUDED_TABLES are deliberately not copied, so their absence from
    # TABLE_ORDER is correct rather than an oversight.
    return sorted(live - set(TABLE_ORDER) - EXCLUDED_TABLES)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--postgres-url", default=None,
                        help="target DSN; defaults to POSTGRES_URL")
    parser.add_argument("--to-aiven", action="store_true",
                        help="target POSTGRESQL_AIVEN_URI instead")
    parser.add_argument("--to-neon", action="store_true",
                        help="target NEON_DATABASE_URL from .env. Preferred "
                             "over --to-url, which puts the password in the "
                             "process list where any local user can read it.")
    parser.add_argument("--to-url", default=None,
                        help="target any Postgres DSN. Note the DSN appears "
                             "in `ps` output for the life of the run, so "
                             "prefer --to-neon or an env var for anything "
                             "with a live password in it.")
    parser.add_argument("--from-local", action="store_true",
                        help="read local Postgres instead of SQLite; required "
                             "to resync a cloud copy, since the SQLite file "
                             "is a stale pre-ingestion backup")
    parser.add_argument("--from-aiven", action="store_true",
                        help="pull the cloud copy down into local Postgres; "
                             "the direction that matters before the trial "
                             "ends, since the deployed app writes there")
    parser.add_argument("--replace", action="store_true",
                        help="truncate the target's tables first, so a "
                             "populated target is replaced rather than hit "
                             "with primary-key collisions")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    aiven = settings._normalise_dsn(settings.POSTGRESQL_AIVEN_URI)
    local = settings._normalise_dsn(settings.POSTGRES_URL)

    if args.from_aiven and (args.to_aiven or args.to_url or args.to_neon):
        raise SystemExit(
            "Pick one direction: --to-aiven/--to-neon/--to-url or --from-aiven"
        )

    if args.to_neon:
        target_url = settings._normalise_dsn(settings.NEON_DATABASE_URL)
        if not target_url:
            raise SystemExit("NEON_DATABASE_URL is not set in backend/.env")
    elif args.to_url:
        target_url = settings._normalise_dsn(args.to_url)
    elif args.to_aiven:
        target_url = aiven
        if not target_url:
            raise SystemExit(
                "POSTGRESQL_AIVEN_URI is not set in backend/.env"
            )
    elif args.from_aiven:
        # Pulling the cloud copy home: the deployed app writes to Aiven, so
        # attempts and progress made there exist nowhere else.
        if not aiven:
            raise SystemExit("POSTGRESQL_AIVEN_URI is not set in backend/.env")
        if not local:
            raise SystemExit("POSTGRES_URL is not set in backend/.env")
        target_url = local
    else:
        target_url = args.postgres_url or settings.POSTGRES_URL

    source_url = None
    if args.from_aiven:
        source_url = aiven
    elif args.from_local:
        source_url = local
        if not source_url:
            raise SystemExit("POSTGRES_URL is not set in backend/.env")

    source_engine, target_engine = _engines(target_url, source_url=source_url)

    # The vector extension must exist before create_all, or the halfvec
    # column has no type to resolve against.
    with target_engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=target_engine)

    print(f"source: {_safe(source_url or settings.SQLITE_URL)}")
    print(f"target: {_safe(target_url)}\n")

    # Before anything is written. A table missing from TABLE_ORDER is not
    # reported by the copy -- it is simply skipped, and the target looks
    # complete. Refusing here is the difference between a loud stop and a
    # migration that quietly leaves the target without its users.
    if source_engine is not None:
        unlisted = audit_tables(source_engine)
        if unlisted:
            raise SystemExit(
                "These source tables are missing from TABLE_ORDER and would "
                "not be copied:\n  " + "\n  ".join(unlisted)
                + "\n\nAdd them (parent before child) and re-run."
            )

    added = add_missing_columns(target_engine, dry_run=args.dry_run)
    if added:
        verb = "would add" if args.dry_run else "added"
        print(f"  schema {verb}: {', '.join(added)}\n")

    if args.replace:
        truncate_target(target_engine, dry_run=args.dry_run)
        print("  target tables truncated\n" if not args.dry_run
              else "  [dry-run] would truncate target tables\n")

    counts = copy_tables(source_engine, target_engine, dry_run=args.dry_run)
    for name, (read, written) in counts.items():
        if read:
            print(f"  {name:22s} {read:6,} rows"
                  f"{'' if args.dry_run else f' -> {written:,} copied'}")

    if args.from_local or args.from_aiven:
        vectors = copy_vectors_between_pg(
            source_engine, target_engine, dry_run=args.dry_run)
    else:
        vectors = load_vectors_from_npy(target_engine, dry_run=args.dry_run)
    print(f"\n  vectors {'to load' if args.dry_run else 'loaded'}: {vectors:,}")

    if args.dry_run:
        print("\nDry run only. Re-run without --dry-run to migrate.")
        return

    reset_sequences(target_engine)
    create_indexes(target_engine)
    print("\nSequences reset and indexes created.")


if __name__ == "__main__":
    main()
