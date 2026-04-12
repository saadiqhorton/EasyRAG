"""Integration test fixtures: test app with SQLite, mocked Qdrant, and mocked storage."""

import os
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# ---------------------------------------------------------------------------
# Set environment variables BEFORE any Settings instantiation.
# These are required by the Settings class and must exist before the
# app.backend.services.config module is first imported.
# ---------------------------------------------------------------------------
os.environ.setdefault("POSTGRES_URL", "sqlite+aiosqlite://")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("ANSWER_LLM_BASE_URL", "http://localhost:8000")
os.environ.setdefault("ANSWER_LLM_MODEL", "test-model")

from app.backend.models import Base  # noqa: E402
from app.backend.services.config import Settings, get_settings  # noqa: E402
from app.backend.services.database import get_session  # noqa: E402


# ---------------------------------------------------------------------------
# In-memory SQLite engine (shared across the test session via StaticPool)
# ---------------------------------------------------------------------------

INTEGRATION_DB_URL = "sqlite+aiosqlite://"


@pytest_asyncio.fixture(scope="session")
async def integration_engine():
    """Create an in-memory SQLite engine shared across the integration test session.

    Uses StaticPool so every checkout returns the same underlying connection,
    which is required for in-memory SQLite to keep data visible across sessions.
    """
    from sqlalchemy.pool import StaticPool

    engine = create_async_engine(
        INTEGRATION_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ---------------------------------------------------------------------------
# Mock service implementations
# ---------------------------------------------------------------------------


class MockStorage:
    """Dict-based mock that satisfies the ObjectStorage protocol."""

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    async def save(self, key: str, content: bytes) -> str:
        self._store[key] = content
        return key

    async def get(self, key: str) -> bytes:
        return self._store[key]

    async def delete(self, key: str) -> bool:
        return self._store.pop(key, None) is not None

    async def exists(self, key: str) -> bool:
        return key in self._store


class MockQdrantClient:
    """Mock AsyncQdrantClient for health checks and point deletion."""

    async def get_collections(self):
        result = MagicMock()
        result.collections = []
        return result

    async def delete(self, **kwargs):
        pass

    async def close(self):
        pass


@pytest.fixture()
def mock_storage():
    """Provide a fresh MockStorage for each test."""
    return MockStorage()


@pytest.fixture()
def mock_qdrant():
    """Provide a fresh MockQdrantClient for each test."""
    return MockQdrantClient()


# ---------------------------------------------------------------------------
# Test Settings
# ---------------------------------------------------------------------------

TEST_SETTINGS = Settings(
    postgres_url=INTEGRATION_DB_URL,
    qdrant_url="http://localhost:6333",
    answer_llm_base_url="http://localhost:8000",
    answer_llm_model="test-model",
    max_upload_size_mb=50,
    storage_path="/tmp/test_storage",
)


# ---------------------------------------------------------------------------
# Test application and client
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def app(integration_engine, mock_storage, mock_qdrant):
    """Create a FastAPI test application with all external services mocked.

    - PostgreSQL is replaced by in-memory SQLite.
    - Qdrant client is replaced by a mock.
    - File storage is replaced by an in-memory dict.
    - The lifespan init/teardown calls are patched out so no real
      connections are opened.
    """
    import app.backend.services.database as db_module

    # Point the database module at our test engine so that get_engine()
    # (used by the readiness endpoint) returns the SQLite engine.
    db_module._engine = integration_engine
    test_factory = async_sessionmaker(integration_engine, expire_on_commit=False)
    db_module._session_factory = test_factory

    # Override the FastAPI get_session dependency to use the test factory.
    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with test_factory() as session:
            async with session.begin():
                yield session

    # Patch every place where the lifespan and endpoints call out to
    # external services.  The patches must target the name in the module
    # where it is *used*, not just where it is *defined*.
    with (
        patch("app.backend.main.init_db"),
        patch("app.backend.main.ensure_collection", new_callable=AsyncMock),
        patch("app.backend.main.close_qdrant", new_callable=AsyncMock),
        patch("app.backend.main.dispose_engine", new_callable=AsyncMock),
        patch("app.backend.main.get_qdrant_client", new_callable=AsyncMock, return_value=mock_qdrant),
        # Also patch the source module for late imports inside route handlers
        patch("app.backend.services.qdrant_client.get_qdrant_client", new_callable=AsyncMock, return_value=mock_qdrant),
        # Storage is imported at the top of documents.py and document_management.py
        patch("app.backend.api.documents.get_storage", return_value=mock_storage),
        patch("app.backend.api.document_management.get_storage", return_value=mock_storage),
    ):
        from app.backend.main import create_app

        application = create_app()
        application.dependency_overrides[get_session] = override_get_session
        application.dependency_overrides[get_settings] = lambda: TEST_SETTINGS

        yield application

        application.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app) -> AsyncClient:
    """Provide an httpx AsyncClient backed by the test app's ASGI transport."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Test isolation: truncate all tables after each test
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_tables(integration_engine):
    """Delete all rows from every table after each test for isolation.

    Tables are truncated in reverse topological order (children first) to
    satisfy foreign-key constraints.
    """
    yield
    async with integration_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())