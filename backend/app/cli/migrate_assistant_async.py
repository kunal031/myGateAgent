"""Add the columns that let an answer be generated after the request.

On Lambda the assistant cannot answer inside the request: Gemini takes
30-60 seconds and API Gateway hard-caps at 29. So the endpoint writes a
placeholder assistant message, dispatches the work, and the client polls
the thread until it fills in.

That placeholder needs somewhere to say it is not an answer yet --
otherwise an empty message renders as the assistant replying with
nothing.

    python -m app.cli.migrate_assistant_async
    python -m app.cli.migrate_assistant_async --target neon
"""

import argparse

from sqlalchemy import create_engine, text

from ..core.config import settings

STEPS = [
    ("add assistant_messages.status",
     "SELECT 1 FROM information_schema.columns WHERE "
     "table_name='assistant_messages' AND column_name='status'",
     "ALTER TABLE assistant_messages ADD COLUMN status VARCHAR(16) "
     "NOT NULL DEFAULT 'ready'"),
    ("add assistant_messages.error",
     "SELECT 1 FROM information_schema.columns WHERE "
     "table_name='assistant_messages' AND column_name='error'",
     "ALTER TABLE assistant_messages ADD COLUMN error TEXT DEFAULT ''"),
    ("index assistant_messages.status",
     "SELECT 1 FROM pg_indexes WHERE indexname='ix_assistant_messages_status'",
     "CREATE INDEX ix_assistant_messages_status "
     "ON assistant_messages (status)"),
]


def _engine(target: str):
    dsn = settings._normalise_dsn({
        "aiven": settings.POSTGRESQL_AIVEN_URI,
        "neon": settings.NEON_DATABASE_URL,
    }.get(target, settings.POSTGRES_URL))
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
    parser.add_argument("--target", default="local",
                        choices=["local", "aiven", "neon"])
    args = parser.parse_args()
    print(f"\n{migrate(args.target)} change(s) applied to {args.target}.")


if __name__ == "__main__":
    main()
