"""Report which database the app is using, and what is in it.

    ./venv/bin/python -m app.cli.db_status
    DB_TARGET=aiven ./venv/bin/python -m app.cli.db_status
"""

import re

from sqlalchemy import inspect, text

from ..core.config import settings
from ..core.database import DATABASE_URL, IS_SQLITE, SessionLocal, engine

COUNTED = [
    "subjects", "chapters", "syllabus_topics", "subtopics", "syllabus_concepts",
    "sources", "source_chunks", "feed_cards", "questions",
    "attempts", "exam_sessions",
]


def safe_dsn(dsn: str) -> str:
    """Hide the password before printing a connection string."""
    return re.sub(r"://([^:/@]+):[^@]+@", r"://\1:***@", dsn)


def main() -> None:
    print(f"  target : {settings.database_target}")
    print(f"  dsn    : {safe_dsn(DATABASE_URL)}")

    try:
        with engine.connect() as conn:
            if not IS_SQLITE:
                version = conn.execute(text("SHOW server_version")).scalar()
                print(f"  server : PostgreSQL {version}")
                vector = conn.execute(text(
                    "SELECT extversion FROM pg_extension WHERE extname='vector'"
                )).scalar()
                print(f"  pgvector: {vector or 'NOT INSTALLED'}")
    except Exception as exc:
        print(f"\n  CANNOT CONNECT: {type(exc).__name__}: {str(exc)[:160]}")
        return

    existing = set(inspect(engine).get_table_names())
    print()
    db = SessionLocal()
    try:
        for table in COUNTED:
            if table not in existing:
                continue
            count = db.execute(text(f"SELECT count(*) FROM {table}")).scalar()
            if count:
                print(f"  {table:20s} {count:>7,}")

        if not IS_SQLITE and "source_chunks" in existing:
            embedded = db.execute(text(
                "SELECT count(*) FROM source_chunks WHERE embedding IS NOT NULL"
            )).scalar()
            print(f"\n  embeddings stored    {embedded:>7,}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
