"""Database engine and session factory.

Supports SQLite and PostgreSQL from the same code. The backend is chosen by
DATABASE_URL, so switching is a config change rather than a code change --
which keeps a rollback cheap during the migration.

SQLite needs WAL and a long busy timeout, because ingestion, generation and
the API all write concurrently and its default journal takes a
whole-database lock. Postgres needs none of that.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

DATABASE_URL = settings.resolved_database_url
IS_SQLITE = DATABASE_URL.startswith("sqlite")

#: True when running inside AWS Lambda, which sets this itself.
IS_LAMBDA = bool(settings.AWS_LAMBDA_FUNCTION_NAME)

if IS_SQLITE:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False, "timeout": 30.0},
    )
elif IS_LAMBDA:
    # NullPool, deliberately, and it is the opposite of the usual advice.
    #
    # A pool is per-process, and Lambda gives every concurrent invocation
    # its own process. Pooling there does not share anything -- it just
    # means each frozen instance holds connections open that nobody can
    # use, and a hundred concurrent invocations become a hundred idle
    # pools. Neon's own guidance is the same: let the serverless function
    # open and close, and let PgBouncer on their side do the pooling.
    #
    # This pairs with the "-pooler" hostname; without that, connections
    # go direct and the compute's max_connections is the ceiling.
    engine = create_engine(
        DATABASE_URL,
        poolclass=NullPool,
        connect_args={
            # A cold Neon compute takes a few seconds to wake after its
            # five-minute autosuspend, and the default timeout gives up
            # first -- which presents as an intermittent 500 on the first
            # request of the evening.
            "connect_timeout": 15,
        },
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
