"""Shared test fixtures for the backend test suite."""

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.backend.models import Base, Collection, SourceDocument, DocumentVersion


# Use an in-memory SQLite for unit tests (faster, no PG dependency)
TEST_DATABASE_URL = "sqlite+aiosqlite:///test.db"


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create a test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine):
    """Create a fresh test session with rollback after each test."""
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with factory() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest_asyncio.fixture
async def test_collection(test_session):
    """Create a test collection."""
    collection = Collection(
        name="Test Collection",
        description="A test collection for unit tests",
    )
    test_session.add(collection)
    await test_session.flush()
    return collection


@pytest_asyncio.fixture
async def test_document(test_session, test_collection):
    """Create a test document with a version."""
    doc = SourceDocument(
        collection_id=test_collection.id,
        title="Test Document",
        original_filename="test.pdf",
        mime_type="application/pdf",
        file_hash="abc123",
        file_size_bytes=1024,
    )
    test_session.add(doc)
    await test_session.flush()

    version = DocumentVersion(
        document_id=doc.id,
        version_number=1,
        is_active=True,
        storage_key=f"{test_collection.id}/{doc.id}/{uuid.uuid4()}/test.pdf",
        index_status="pending",
    )
    test_session.add(version)
    await test_session.flush()
    return doc, version