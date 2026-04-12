"""Collection CRUD endpoints: create, list, detail, delete."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Collection, DocumentVersion, SourceDocument
from ..models.schemas import (
    CollectionCreate,
    CollectionDetailResponse,
    CollectionHealthResponse,
    CollectionResponse,
    FailureEventResponse,
)
from ..services.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter()


def _collection_to_response(
    collection: Collection, document_count: int, status_summary: dict
) -> CollectionResponse:
    """Map an ORM Collection to a CollectionResponse schema."""
    return CollectionResponse(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
        document_count=document_count,
        index_status_summary=status_summary,
    )


async def _get_status_summary(
    session: AsyncSession, collection_id: uuid.UUID
) -> dict[str, int]:
    """Get index status counts for a collection's document versions."""
    stmt = (
        select(DocumentVersion.index_status, func.count(DocumentVersion.id))
        .join(SourceDocument)
        .where(
            SourceDocument.collection_id == collection_id,
            SourceDocument.deleted_at.is_(None),
            DocumentVersion.is_active.is_(True),
        )
        .group_by(DocumentVersion.index_status)
    )
    result = await session.execute(stmt)
    rows = result.fetchall()
    return {row[0]: row[1] for row in rows}


@router.post("/collections", status_code=201, response_model=CollectionResponse)
async def create_collection(
    body: CollectionCreate,
    session: AsyncSession = Depends(get_session),
) -> CollectionResponse:
    """Create a new knowledge collection."""
    try:
        collection = Collection(name=body.name, description=body.description)
        session.add(collection)
        await session.flush()
        return _collection_to_response(collection, 0, {})
    except Exception as e:
        logger.error("create_collection_error", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create collection") from e


@router.get("/collections", response_model=list[CollectionResponse])
async def list_collections(
    skip: int = 0,
    limit: int = 20,
    session: AsyncSession = Depends(get_session),
) -> list[CollectionResponse]:
    """List all knowledge collections with document counts."""
    try:
        stmt = select(Collection).order_by(Collection.created_at.desc()).offset(skip).limit(limit)
        result = await session.execute(stmt)
        collections = result.scalars().all()

        responses = []
        for col in collections:
            count_stmt = select(func.count(SourceDocument.id)).where(
                SourceDocument.collection_id == col.id,
                SourceDocument.deleted_at.is_(None),
            )
            count_result = await session.execute(count_stmt)
            doc_count = count_result.scalar() or 0

            status_summary = await _get_status_summary(session, col.id)
            responses.append(_collection_to_response(col, doc_count, status_summary))
        return responses
    except Exception as e:
        logger.error("list_collections_error", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list collections") from e


@router.get("/collections/{collection_id}", response_model=CollectionDetailResponse)
async def get_collection(
    collection_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> CollectionDetailResponse:
    """Get detailed information about a single collection."""
    stmt = select(Collection).where(Collection.id == collection_id)
    result = await session.execute(stmt)
    collection = result.scalars().first()
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    doc_count_stmt = select(func.count(SourceDocument.id)).where(
        SourceDocument.collection_id == collection_id,
        SourceDocument.deleted_at.is_(None),
    )
    doc_count_result = await session.execute(doc_count_stmt)
    doc_count = doc_count_result.scalar() or 0

    status_summary = await _get_status_summary(session, collection_id)

    health = await _build_health(session, collection_id)

    recent_failures = await _get_recent_failures(session, collection_id, limit=5)

    return CollectionDetailResponse(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
        document_count=doc_count,
        index_status_summary=status_summary,
        recent_failures=recent_failures,
        health=health,
    )


@router.delete("/collections/{collection_id}")
async def delete_collection(
    collection_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Delete a collection and all its documents, versions, and chunks.

    Also removes Qdrant points by collection_id filter.
    """
    stmt = select(Collection).where(Collection.id == collection_id)
    result = await session.execute(stmt)
    collection = result.scalars().first()
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    await session.delete(collection)
    await session.flush()

    await _delete_qdrant_collection_points(collection_id)

    return {"deleted": True}


@router.get("/collections/{collection_id}/health", response_model=CollectionHealthResponse)
async def get_collection_health(
    collection_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> CollectionHealthResponse:
    """Get health summary for a collection."""
    stmt = select(Collection).where(Collection.id == collection_id)
    result = await session.execute(stmt)
    if result.scalars().first() is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    return await _build_health(session, collection_id)


async def _build_health(
    session: AsyncSession, collection_id: uuid.UUID
) -> CollectionHealthResponse:
    """Build the health summary for a collection."""
    total_stmt = select(func.count(SourceDocument.id)).where(
        SourceDocument.collection_id == collection_id,
        SourceDocument.deleted_at.is_(None),
    )
    total_result = await session.execute(total_stmt)
    total = total_result.scalar() or 0

    indexed_stmt = (
        select(func.count(DocumentVersion.id))
        .join(SourceDocument)
        .where(
            SourceDocument.collection_id == collection_id,
            SourceDocument.deleted_at.is_(None),
            DocumentVersion.is_active.is_(True),
            DocumentVersion.index_status == "indexed",
        )
    )
    indexed_result = await session.execute(indexed_stmt)
    indexed = indexed_result.scalar() or 0

    failed_stmt = (
        select(func.count(DocumentVersion.id))
        .join(SourceDocument)
        .where(
            SourceDocument.collection_id == collection_id,
            SourceDocument.deleted_at.is_(None),
            DocumentVersion.index_status == "failed",
        )
    )
    failed_result = await session.execute(failed_stmt)
    failed = failed_result.scalar() or 0

    return CollectionHealthResponse(
        total_documents=total,
        indexed_count=indexed,
        failed_count=failed,
    )


async def _get_recent_failures(
    session: AsyncSession, collection_id: uuid.UUID, limit: int = 5
) -> list[FailureEventResponse]:
    """Get recent failure events for a collection."""
    from ..models import FailureEvent

    stmt = (
        select(FailureEvent)
        .where(FailureEvent.collection_id == collection_id)
        .order_by(FailureEvent.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    failures = result.scalars().all()
    return [
        FailureEventResponse(
            id=f.id,
            job_id=f.job_id,
            collection_id=f.collection_id,
            stage_name=f.stage_name,
            error_type=f.error_type,
            message=f.message,
            is_retryable=f.is_retryable,
            suggested_action=f.suggested_action,
            created_at=f.created_at,
        )
        for f in failures
    ]


async def _delete_qdrant_collection_points(collection_id: uuid.UUID) -> None:
    """Delete Qdrant points for a collection. Awaits the result and logs errors."""
    try:
        from qdrant_client import models

        from ..services.config import QDRANT_COLLECTION_NAME
        from ..services.qdrant_client import get_qdrant_client

        client = await get_qdrant_client()
        await client.delete(
            collection_name=QDRANT_COLLECTION_NAME,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="collection_id",
                            match=models.MatchValue(value=str(collection_id)),
                        )
                    ]
                )
            ),
        )
    except Exception as e:
        logger.warning("qdrant_delete_failed collection_id=%s error=%s", collection_id, e)