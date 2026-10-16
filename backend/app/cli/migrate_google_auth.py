"""Add Google sign-in columns to an existing `users` table.

`Base.metadata.create_all` creates missing tables but never alters an
existing one, so a deployment that already has accounts needs this. Three
changes:

* add `google_sub`, unique and indexed
* add `avatar_url`
* drop `NOT NULL` from `password_hash`, so a Google-only account can exist

Idempotent -- every statement checks the catalogue first -- because the
alternative is a migration that cannot be re-run after a partial failure.

    python -m app.cli.migrate_google_auth           # local
    python -m app.cli.migrate_google_auth --target aiven

Nothing here destroys data: two columns are added and one constraint is
relaxed. Relaxing NOT NULL cannot fail against existing rows, which is why
this needs no backfill.
"""

import argparse
import logging

from sqlalchemy import create_engine, text

from ..core.config import settings

logger = logging.getLogger(__name__)


def _engine(target: str):
    """Build an engine for either database.

    Follows the pattern the backup and migrate CLIs already use rather
    than the app's own engine, which is bound to whichever target config
    selected -- running this against the wrong database is precisely the
    hazard those two paths coexisting creates.
    """
    dsn = settings._normalise_dsn(
        settings.POSTGRESQL_AIVEN_URI if target == "aiven" else settings.POSTGRES_URL
    )
    if not dsn:
        raise SystemExit(
            f"No connection string for '{target}'. "
            "Set POSTGRESQL_AIVEN_URI in backend/.env"
            if target == "aiven" else "Set POSTGRES_URL in backend/.env"
        )
    return create_engine(dsn, connect_args={"connect_timeout": 30})

#: Each step is (description, predicate, statement). The predicate asks the
#: catalogue whether the work is already done, so a re-run is a no-op
#: rather than an error.
STEPS = [
    (
        "add users.google_sub",
        """SELECT 1 FROM information_schema.columns
           WHERE table_name='users' AND column_name='google_sub'""",
        "ALTER TABLE users ADD COLUMN google_sub VARCHAR(255)",
    ),
    (
        "add users.avatar_url",
        """SELECT 1 FROM information_schema.columns
           WHERE table_name='users' AND column_name='avatar_url'""",
        "ALTER TABLE users ADD COLUMN avatar_url VARCHAR(512)",
    ),
    (
        # Unique, so two rows can never claim one Google account. Built
        # as an index rather than a constraint because CREATE UNIQUE INDEX
        # has an IF NOT EXISTS form and ADD CONSTRAINT does not.
        "add unique index on users.google_sub",
        "SELECT 1 FROM pg_indexes WHERE indexname='ix_users_google_sub'",
        "CREATE UNIQUE INDEX ix_users_google_sub ON users (google_sub)",
    ),
    (
        "allow users.password_hash to be null",
        """SELECT 1 FROM information_schema.columns
           WHERE table_name='users' AND column_name='password_hash'
             AND is_nullable='YES'""",
        "ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL",
    ),
]


def migrate(target: str = "local") -> int:
    engine = _engine(target)
    applied = 0

    with engine.begin() as conn:
        if not conn.execute(text(
            "SELECT 1 FROM information_schema.tables WHERE table_name='users'"
        )).first():
            print(f"[{target}] no users table; run the app once to create it")
            return 0

        for label, predicate, statement in STEPS:
            if conn.execute(text(predicate)).first():
                print(f"[{target}] already done: {label}")
                continue
            conn.execute(text(statement))
            print(f"[{target}] applied:    {label}")
            applied += 1

    return applied


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target", default="local", choices=["local", "aiven"],
        help="which database to migrate (default: local)",
    )
    args = parser.parse_args()

    changed = migrate(args.target)
    print(f"\n{changed} change(s) applied to {args.target}.")


if __name__ == "__main__":
    main()
