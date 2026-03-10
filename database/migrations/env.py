"""
database/migrations/env.py
--------------------------
Alembic environment configuration.

Supports three modes:
  1. Offline  (--sql)     — emits SQL without a live DB connection
  2. Sync online          — standard psycopg2 connection  (Celery / CLI)
  3. Async online         — asyncpg connection            (FastAPI runtime)

The target metadata is read from database.base.Base.metadata so Alembic
can auto-generate migrations from the ORM models.
"""

from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, async_engine_from_config

# ---------------------------------------------------------------------------
# Make the project root importable so "database.*" resolves correctly when
# Alembic is invoked from any working directory.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Import declarative base — provides the target metadata for auto-generation
# ---------------------------------------------------------------------------
from database.base import Base  # noqa: E402  (must come after sys.path patch)
import database.models  # noqa: E402, F401  — registers all ORM models with Base.metadata

# ---------------------------------------------------------------------------
# Alembic Config object — gives access to values in alembic.ini
# ---------------------------------------------------------------------------
config = context.config

# Interpret the alembic.ini loggers section (if present)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Target metadata for `alembic revision --autogenerate`
# ---------------------------------------------------------------------------
target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# Database URL resolution (env var takes priority over alembic.ini)
# ---------------------------------------------------------------------------

def get_url() -> str:
    """Return the synchronous database URL."""
    url = os.getenv("DATABASE_URL")
    if url:
        # asyncpg URLs are not usable for sync migration — swap driver
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    # Fallback to alembic.ini (interpolated from env via %(VAR)s)
    return config.get_main_option("sqlalchemy.url")


def get_async_url() -> str:
    """Return the async database URL (asyncpg)."""
    url = os.getenv("DATABASE_ASYNC_URL") or os.getenv("DATABASE_URL", "")
    if url and "asyncpg" not in url:
        url = url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
        url = url.replace("postgresql://", "postgresql+asyncpg://")
    return url or get_url().replace("psycopg2", "asyncpg")


# ---------------------------------------------------------------------------
# Offline mode  (alembic upgrade head --sql)
# Generates SQL without connecting to the database.
# ---------------------------------------------------------------------------

def run_migrations_offline() -> None:
    """Emit migration SQL to stdout without a live connection."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Render ENUM types as CREATE TYPE in offline SQL output
        include_schemas=True,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Sync online mode  (used by Celery workers and the CLI)
# ---------------------------------------------------------------------------

def run_migrations_online_sync() -> None:
    """Run migrations using a standard synchronous psycopg2 connection."""
    connectable = engine_from_config(
        {"sqlalchemy.url": get_url()},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args={"client_encoding": "utf8"}
    )

    with connectable.connect() as connection:
        _configure_and_run(connection)


def _configure_and_run(connection: Connection) -> None:
    """Shared migration runner for both sync and async modes."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
        # Render ENUM  types so autogenerate detects changes
        user_module_prefix="database.enums.",
        transaction_per_migration=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Async online mode  (usable from FastAPI startup event or async runner)
# ---------------------------------------------------------------------------

async def run_async_migrations() -> None:
    """Run migrations via asyncpg (suitable for async application startup)."""
    connectable: AsyncEngine = async_engine_from_config(
        {"sqlalchemy.url": get_async_url()},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(_configure_and_run)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    Entry point for online mode.

    Uses asyncio if an async URL is available (asyncpg), otherwise falls
    back to the synchronous psycopg2 path.
    """
    async_url = os.getenv("DATABASE_ASYNC_URL") or os.getenv("DATABASE_URL", "")
    if "asyncpg" in async_url:
        asyncio.run(run_async_migrations())
    else:
        run_migrations_online_sync()


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
