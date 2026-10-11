"""Additive schema migrations for SQLite.

create_all() creates missing tables but never alters existing ones, so new
columns on a table that already has rows need an explicit ALTER. Each entry
is additive and idempotent: re-running is safe, and no data is rewritten.

    ./venv/bin/python -m app.cli.migrate
"""

from sqlalchemy import text

from ..core.database import Base, SessionLocal, engine
from ..models import concepts, exams, models, sources  # noqa: F401  (register tables)

# (table, column, SQL type + default)
ADDITIVE_COLUMNS: list[tuple[str, str, str]] = [
    ("feed_cards", "concept_id", "INTEGER"),
    ("feed_cards", "mode", "VARCHAR(20) DEFAULT 'ADVANCED'"),
    ("feed_cards", "sequence", "INTEGER DEFAULT 0"),
    ("feed_cards", "provenance", "TEXT DEFAULT ''"),
    ("feed_cards", "source_chunk_ids", "VARCHAR(200) DEFAULT ''"),
    ("feed_cards", "review_status", "VARCHAR(20) DEFAULT 'approved'"),
    # Questions carry the same provenance guarantees as cards.
    ("questions", "concept_id", "INTEGER"),
    ("questions", "exam_year", "INTEGER"),
    ("questions", "provenance", "TEXT DEFAULT ''"),
    ("questions", "source_chunk_ids", "VARCHAR(200) DEFAULT ''"),
    ("questions", "review_status", "VARCHAR(20) DEFAULT 'approved'"),
    ("questions", "origin", "VARCHAR(20) DEFAULT 'SEED'"),
    ("exam_sessions", "shortfall_note", "TEXT DEFAULT ''"),
    ("exam_sessions", "kind", "VARCHAR(10) DEFAULT 'test'"),
    ("exam_sessions", "topic_id", "INTEGER"),
    ("sources", "ingest_status", "VARCHAR(20) DEFAULT 'complete'"),
    ("sources", "ingest_error", "TEXT DEFAULT ''"),
    ("feed_cards", "source_type", "VARCHAR(20) DEFAULT 'knowledge_base'"),
    ("feed_cards", "tags", "VARCHAR(400) DEFAULT ''"),
    ("questions", "paper_id", "INTEGER"),
    ("questions", "solution_source", "VARCHAR(10) DEFAULT ''"),
    ("question_papers", "progress_done", "INTEGER DEFAULT 0"),
    ("question_papers", "progress_total", "INTEGER DEFAULT 0"),
    ("question_papers", "progress_note", "VARCHAR(120) DEFAULT ''"),
]

INDEXES: list[tuple[str, str]] = [
    ("ix_feed_cards_concept_id", "feed_cards(concept_id)"),
    ("ix_feed_cards_mode", "feed_cards(mode)"),
    ("ix_feed_cards_review_status", "feed_cards(review_status)"),
    ("ix_feed_cards_source_type", "feed_cards(source_type)"),
    ("ix_feed_cards_tags", "feed_cards(tags)"),
    ("ix_questions_paper_id", "questions(paper_id)"),
    ("ix_questions_solution_source", "questions(solution_source)"),
    ("ix_questions_concept_id", "questions(concept_id)"),
    ("ix_questions_exam_year", "questions(exam_year)"),
    ("ix_questions_origin", "questions(origin)"),
    ("ix_exam_sessions_kind", "exam_sessions(kind)"),
]


def _tables(db) -> set[str]:
    from sqlalchemy import inspect
    from ..core.database import engine as bound_engine
    return set(inspect(bound_engine).get_table_names())


def existing_columns(db, table: str) -> set[str]:
    """Columns on a table, on either backend.

    SQLite answers with PRAGMA; Postgres rejects it outright, so the
    portable information_schema query is used there.
    """
    from ..core.database import IS_SQLITE

    if IS_SQLITE:
        return {row[1] for row in db.execute(text(f"PRAGMA table_info({table})"))}
    rows = db.execute(
        text("SELECT column_name FROM information_schema.columns "
             "WHERE table_name = :t"),
        {"t": table},
    )
    return {row[0] for row in rows}


def migrate() -> dict:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    added, skipped = [], []
    try:
        existing_tables = _tables(db)
        for table, column, ddl in ADDITIVE_COLUMNS:
            if table not in existing_tables:
                skipped.append(f"{table}.{column} (no such table)")
                continue
            if column in existing_columns(db, table):
                skipped.append(f"{table}.{column}")
                continue
            db.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
            added.append(f"{table}.{column}")

        for name, target in INDEXES:
            db.execute(text(f"CREATE INDEX IF NOT EXISTS {name} ON {target}"))

        db.commit()
        return {"added": added, "already_present": skipped}
    finally:
        db.close()


def main() -> None:
    result = migrate()
    for col in result["added"]:
        print(f"  added   {col}")
    for col in result["already_present"]:
        print(f"  present {col}")
    print(f"\n{len(result['added'])} column(s) added, "
          f"{len(result['already_present'])} already present.")


if __name__ == "__main__":
    main()
