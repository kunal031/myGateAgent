"""Database engine and session factory.

Supports SQLite and PostgreSQL from the same code. The backend is chosen by
DATABASE_URL, so switching is a config change rather than a code change --
which keeps a rollback cheap during the migration.

SQLite needs WAL and a long busy timeout, because ingestion, generation and
the API all write concurrently and its default journal takes a
whole-database lock. Postgres needs none of that.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

DATABASE_URL = settings.resolved_database_url
IS_SQLITE = DATABASE_URL.startswith("sqlite")

if IS_SQLITE:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False, "timeout": 30.0},
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        # Recycle before Postgres' own idle timeout can close a pooled
        # connection underneath a long-running ingest.
        pool_pre_ping=True,
        pool_recycle=1800,
    )


if IS_SQLITE:
    @event.listens_for(engine, "connect")
    def _configure_sqlite(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
