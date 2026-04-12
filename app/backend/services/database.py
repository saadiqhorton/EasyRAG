"""Async engine, session factory, and FastAPI dependency for database access."""

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
    """
    global _engine, _session_factory
    _engine = create_async_engine(
        settings.postgres_url,
        pool_size=20,
        max_overflow=10,
    )
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