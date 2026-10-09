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
]

INDEXES: list[tuple[str, str]] = [
    ("ix_feed_cards_concept_id", "feed_cards(concept_id)"),
    ("ix_feed_cards_mode", "feed_cards(mode)"),
    ("ix_feed_cards_review_status", "feed_cards(review_status)"),
    ("ix_questions_concept_id", "questions(concept_id)"),
    ("ix_questions_exam_year", "questions(exam_year)"),
    ("ix_questions_origin", "questions(origin)"),
]


def existing_columns(db, table: str) -> set[str]:
    return {row[1] for row in db.execute(text(f"PRAGMA table_info({table})"))}


def migrate() -> dict:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    added, skipped = [], []
    try:
        for table, column, ddl in ADDITIVE_COLUMNS:
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
