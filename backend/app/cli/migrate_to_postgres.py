"""Copy the SQLite database into PostgreSQL, then load the vectors.

Reversible until cut-over: SQLite is only read, never modified, so a failed
run costs nothing and the app keeps running on SQLite until DATABASE_URL
changes.

    ./venv/bin/python -m app.cli.migrate_to_postgres --dry-run
    ./venv/bin/python -m app.cli.migrate_to_postgres
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
TABLE_ORDER = [
    "subjects", "topics", "concepts",
    "chapters", "syllabus_topics", "subtopics", "syllabus_concepts",
    "sources", "source_chunks",
    "questions", "feed_cards",
    "attempts", "mistake_registry", "concept_progress",
    "exam_sessions", "exam_items",
]

# Postgres rejects a text value in a halfvec column, and the vectors are
# loaded separately from the .npy store in step 2.
SKIP_COLUMNS = {"source_chunks": {"embedding"}}

VECTOR_DIR = settings.DATA_DIR / "vectors"


def _safe(dsn: str) -> str:
    """Hide the password before printing a connection string."""
    import re
    return re.sub(r"://([^:/@]+):[^@]+@", r"://\1:***@", dsn)


def _engines(postgres_url: str):
    source = create_engine(settings.SQLITE_URL)
    target = create_engine(postgres_url)
    return source, target


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


def load_vectors(target_engine, *, dry_run: bool) -> int:
    """Move embeddings from the .npy store onto their chunk rows."""
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--postgres-url", default=None,
                        help="target DSN; defaults to POSTGRES_URL")
    parser.add_argument("--to-aiven", action="store_true",
                        help="target POSTGRESQL_AIVEN_URI instead")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.to_aiven:
        target_url = settings._normalise_dsn(settings.POSTGRESQL_AIVEN_URI)
        if not target_url:
            raise SystemExit(
                "POSTGRESQL_AIVEN_URI is not set in backend/.env"
            )
    else:
        target_url = args.postgres_url or settings.POSTGRES_URL

    source_engine, target_engine = _engines(target_url)

    # The vector extension must exist before create_all, or the halfvec
    # column has no type to resolve against.
    with target_engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=target_engine)

    print(f"source: {settings.SQLITE_URL}")
    print(f"target: {_safe(target_url)}\n")

    counts = copy_tables(source_engine, target_engine, dry_run=args.dry_run)
    for name, (read, written) in counts.items():
        if read:
            print(f"  {name:22s} {read:6,} rows"
                  f"{'' if args.dry_run else f' -> {written:,} copied'}")

    vectors = load_vectors(target_engine, dry_run=args.dry_run)
    print(f"\n  vectors {'to load' if args.dry_run else 'loaded'}: {vectors:,}")

    if args.dry_run:
        print("\nDry run only. Re-run without --dry-run to migrate.")
        return

    reset_sequences(target_engine)
    create_indexes(target_engine)
    print("\nSequences reset and indexes created.")


if __name__ == "__main__":
    main()
