"""Database engine and session factory.

SQLite defaults to journal_mode=delete, which takes a whole-database lock
for every write. Ingestion and generation both write while the API reads, so
that default produced "database is locked" failures the moment two jobs ran
together. WAL lets one writer proceed alongside readers, and a long
busy_timeout makes the remaining writer-writer contention wait instead of
failing.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={
        "check_same_thread": False,
        # Wait up to 30s for a lock rather than raising immediately. A vision
        # transcription batch can hold a write open for a few seconds.
        "timeout": 30.0,
    },
)


@event.listens_for(engine, "connect")
def _configure_sqlite(dbapi_connection, _record):
    cursor = dbapi_connection.cursor()
    # WAL: readers never block the writer, and it survives restarts.
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    # NORMAL is the recommended durability level under WAL: safe against
    # application crashes, and far fewer fsyncs than FULL.
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
