"""Point the app at a throwaway database, before anything imports it.

Imported first by conftest.py and by any module that needs app.* at
collection time. The app resolves its DSN when app.core.database is
imported, so this has to win the race -- setting the variables after that
import leaves a bound engine still pointing at Postgres, and the tests
would mutate the real corpus.
"""

import os
import tempfile
from pathlib import Path

TMP_DIR = Path(tempfile.mkdtemp(prefix="gateai-tests-"))

os.environ["DATABASE_URL"] = f"sqlite:///{TMP_DIR}/test.db"
os.environ["DB_TARGET"] = "sqlite"
os.environ["JWT_SECRET"] = "t" * 48
os.environ["GEMINI_API_KEY"] = ""


def create_schema() -> None:
    """Build the schema on the throwaway database.

    Called at import time rather than from a session fixture: the auth
    sweep imports app.main at collection time to enumerate routes, which
    happens before any fixture runs. Without the tables those requests
    fail with a 500 from the database instead of the 401 under test --
    which looks exactly like a missing auth guard.
    """
    from app.core.database import Base, engine
    import app.models  # noqa: F401  (registers every table)

    Base.metadata.create_all(bind=engine)


create_schema()
