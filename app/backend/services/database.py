"""Async engine, session factory, and FastAPI dependency for database access.

Supports both PostgreSQL and SQLite via the database URL:
- PostgreSQL: postgresql+asyncpg://user:pass@host/db
- SQLite:    sqlite+aiosqlite:///path/to/easyrag.db
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import Settings

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_db(settings: Settings) -> None:
    """Initialize the async engine and session factory.

    Must be called once at application startup.
    Adapts connection pool settings based on the database backend.
    """
    global _engine, _session_factory

    db_url = settings.effective_database_url

    # SQLite does not support connection pooling
    is_sqlite = db_url.startswith("sqlite")

    engine_kwargs = {}
    if not is_sqlite:
        engine_kwargs["pool_size"] = 20
        engine_kwargs["max_overflow"] = 10
    else:
        # SQLite: set check_same_thread for async compatibility
        engine_kwargs["connect_args"] = {"check_same_thread": False}

    _engine = create_async_engine(db_url, **engine_kwargs)
    _session_factory = async_sessionmaker(
        _engine,
        expire_on_commit=False,
    )


def get_engine():
    """Return the async engine (for use in Alembic or shutdown)."""
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the async session factory."""
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async DB session.

    The session is wrapped in a begin/commit block. On exception the
    transaction rolls back automatically.
    """
    async with _session_factory() as session:
        async with session.begin():
            yield session


async def dispose_engine() -> None:
    """Dispose the async engine (call during shutdown)."""
    if _engine is not None:
        await _engine.dispose()
