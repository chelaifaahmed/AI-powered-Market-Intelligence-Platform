"""
database/connection.py
----------------------
Database engine, session factory, and dependency injection helpers.

Configuration is driven entirely by environment variables (via config.py).
"""

from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from database.base import Base

# ---------------------------------------------------------------------------
# Lazy import to avoid circular dependencies
# ---------------------------------------------------------------------------
def _get_settings():
    import os
    try:
        from config import settings  # type: ignore
        return settings
    except (ImportError, ModuleNotFoundError):
        class _FallbackSettings:
            _db_pw = os.environ.get("DB_PASSWORD", "")
            _db_user = os.environ.get("DB_USER", "postgres")
            _db_host = os.environ.get("DB_HOST", "localhost")
            _db_port = os.environ.get("DB_PORT", "5432")
            _db_name = os.environ.get("DB_NAME", "automotive_intelligence")
            DATABASE_URL = os.getenv(
                "DATABASE_URL",
                f"postgresql+psycopg2://{_db_user}:{_db_pw}@{_db_host}:{_db_port}/{_db_name}"
            )
            DATABASE_ASYNC_URL = os.getenv(
                "DATABASE_ASYNC_URL",
                f"postgresql+asyncpg://{_db_user}:{_db_pw}@{_db_host}:{_db_port}/{_db_name}"
            )
            DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
            DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "20"))
            DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))
            DB_ECHO = os.getenv("DB_ECHO", "false").lower() == "true"
        return _FallbackSettings()


# ---------------------------------------------------------------------------
# Synchronous engine + session factory
# (used by schedulers, CLI scripts, Celery tasks)
# ---------------------------------------------------------------------------

def create_sync_engine():
    settings = _get_settings()
    engine = create_engine(
        settings.DATABASE_URL,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_pre_ping=True,           # detects stale connections
        echo=settings.DB_ECHO,
    )

    # Enable UUID extension on first connect
    @event.listens_for(engine, "connect")
    def _set_uuid_extension(dbapi_conn, _connection_record):
        with dbapi_conn.cursor() as cursor:
            cursor.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')

    return engine


def create_sync_session_factory(engine=None):
    if engine is None:
        engine = create_sync_engine()
    return sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )


# Singleton instances
_sync_engine = None
_SyncSession = None


def get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_sync_engine()
    return _sync_engine


def get_sync_session_factory():
    global _SyncSession
    if _SyncSession is None:
        _SyncSession = create_sync_session_factory(get_sync_engine())
    return _SyncSession


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Context manager for synchronous DB sessions.

    Usage:
        with get_db_session() as session:
            records = session.query(CarBrand).all()
    """
    SessionLocal = get_sync_session_factory()
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Asynchronous engine + session factory
# (used by FastAPI endpoints, async scrapers)
# ---------------------------------------------------------------------------

def create_async_engine_instance():
    settings = _get_settings()
    return create_async_engine(
        settings.DATABASE_ASYNC_URL,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_pre_ping=True,
        echo=settings.DB_ECHO,
    )


_async_engine = None
_AsyncSession = None


def get_async_engine():
    global _async_engine
    if _async_engine is None:
        _async_engine = create_async_engine_instance()
    return _async_engine


def get_async_session_factory():
    global _AsyncSession
    if _AsyncSession is None:
        _AsyncSession = async_sessionmaker(
            bind=get_async_engine(),
            class_=AsyncSession,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _AsyncSession


@asynccontextmanager
async def get_async_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions.

    Usage:
        async with get_async_db_session() as session:
            result = await session.execute(select(CarBrand))
    """
    AsyncSessionLocal = get_async_session_factory()
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# FastAPI Depends() helper
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for injecting an async DB session.

    Usage in FastAPI:
        @router.get("/brands")
        async def list_brands(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with get_async_db_session() as session:
        yield session


# ---------------------------------------------------------------------------
# Schema management utilities
# ---------------------------------------------------------------------------

def create_all_tables(engine=None) -> None:
    """
    Create all tables defined in the ORM models.
    Should only be used in development / testing.
    In production, use Alembic migrations instead.
    """
    if engine is None:
        engine = get_sync_engine()
    # Import models to ensure they are registered with Base
    import database.models  # noqa: F401
    Base.metadata.create_all(bind=engine)


def drop_all_tables(engine=None) -> None:
    """
    Drop all tables. DANGEROUS — only use in testing environments.
    """
    if engine is None:
        engine = get_sync_engine()
    import database.models  # noqa: F401
    Base.metadata.drop_all(bind=engine)


def health_check(engine=None) -> bool:
    """
    Verify the database is reachable. Returns True if healthy.
    Used by monitoring systems and pipeline startup checks.
    """
    if engine is None:
        engine = get_sync_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
