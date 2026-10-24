"""Add the profile fields to an existing `users` table.

`create_all` adds missing tables but never alters an existing one, so a
deployment with accounts already in it needs this. One column: `phone`.

Idempotent -- the catalogue is checked first -- so a partial failure can
simply be re-run.

    python -m app.cli.migrate_profile
    python -m app.cli.migrate_profile --target aiven
"""

import argparse

from sqlalchemy import create_engine, text

from ..core.config import settings

STEPS = [
    (
        "add users.phone",
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name='users' AND column_name='phone'",
        "ALTER TABLE users ADD COLUMN phone VARCHAR(32)",
    ),
]


def _engine(target: str):
    dsn = settings._normalise_dsn(
        settings.POSTGRESQL_AIVEN_URI if target == "aiven" else settings.POSTGRES_URL
    )
    if not dsn:
        raise SystemExit(f"No connection string configured for {target!r}")
    return create_engine(dsn, connect_args={"connect_timeout": 30})


def migrate(target: str = "local") -> int:
    applied = 0
    with _engine(target).begin() as conn:
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
    parser.add_argument("--target", default="local", choices=["local", "aiven"])
    args = parser.parse_args()
    print(f"\n{migrate(args.target)} change(s) applied to {args.target}.")


if __name__ == "__main__":
    main()
