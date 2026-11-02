"""Alembic environment, wired to the application's own configuration.

The DSN comes from app.core.config rather than alembic.ini, so a
migration always targets the database the app resolved -- DB_TARGET,
DATABASE_URL and the Aiven/Neon URIs all behave identically here and at
runtime. A second URL in the ini would be a second source of truth, and
the failure mode is migrating one database while the app reads another.

Importing app.models (the package, not a module) registers every table on
one metadata. Importing a subset makes autogenerate believe the missing
tables were dropped, and it will cheerfully write a migration that drops
them.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# The app package lives one directory up from migrations/.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings  # noqa: E402
from app.core.database import Base  # noqa: E402
import app.models  # noqa: F401,E402  (registers every table on Base.metadata)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.resolved_database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it, for review before a deploy."""
    context.configure(
        url=settings.resolved_database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Needed on SQLite, which cannot ALTER a column in place and has to
        # rebuild the table instead. Harmless on Postgres.
        render_as_batch=settings.resolved_database_url.startswith("sqlite"),
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=connection.dialect.name == "sqlite",
            # Without this a changed column type is invisible to
            # autogenerate, which is how a schema silently drifts.
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
