import asyncio

# Load all models so their metadata is visible to Alembic
import sys
from logging.config import fileConfig
from pathlib import Path

import pgvector  # noqa: F401 — registers pgvector types with SQLAlchemy
import pgvector.sqlalchemy  # noqa: F401
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.db.base import Base
from app.db.models import *  # noqa: F401,F403 — registers all model classes

# Alembic Config object
config = context.config

# Interpret the config file for logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Use our app's metadata
target_metadata = Base.metadata

# Override the sqlalchemy.url from settings so we don't duplicate it
# Convert asyncpg DSN → sync psycopg2 URL for Alembic's offline mode
def get_sync_url() -> str:
    return settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://")

def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (generates SQL)."""
    context.configure(
        url=get_sync_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations against the live async database."""
    connectable = async_engine_from_config(
        {"sqlalchemy.url": settings.DATABASE_URL},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
