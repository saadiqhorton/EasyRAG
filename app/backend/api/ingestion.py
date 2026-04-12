"""Ingestion job status and failure endpoints."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    DocumentVersion,
    FailureEvent,
    IngestionJob,
    SourceDocument,
)
from ..models.schemas import (
    FailureEventResponse,
    IngestionJobResponse,
    ReindexRequest,
    ReindexResponse,
)
from ..services.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/ingestion-jobs/{job_id}", response_model=IngestionJobResponse)
async def get_ingestion_job(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> IngestionJobResponse:
    """Get the status of an ingestion job with its failure events."""
    stmt = select(IngestionJob).where(IngestionJob.id == job_id)
    result = await session.execute(stmt)
    job = result.scalars().first()
    if job is None:
        raise HTTPException(status_code=404, detail="Ingestion job not found")

    failures = [
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
        for f in job.failure_events
    ]

    return IngestionJobResponse(
        id=job.id,
        collection_id=job.collection_id,
        version_id=job.version_id,
        status=job.status,
        current_stage=job.current_stage,
        started_at=job.started_at,
        completed_at=job.completed_at,
        created_at=job.created_at,
        failures=failures,
    )


@router.get(
    "/collections/{collection_id}/failures",
    response_model=list[FailureEventResponse],
)
async def list_collection_failures(
    collection_id: uuid.UUID,
    skip: int = 0,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
) -> list[FailureEventResponse]:
    """List failure events for a collection."""
    stmt = (
        select(FailureEvent)
        .where(FailureEvent.collection_id == collection_id)
        .order_by(FailureEvent.created_at.desc())
        .offset(skip)
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


@router.post(
    "/collections/{collection_id}/reindex",
    response_model=ReindexResponse,
)
async def reindex_collection(
    collection_id: uuid.UUID,
    body: ReindexRequest | None = None,
    session: AsyncSession = Depends(get_session),
) -> ReindexResponse:
    """Reindex documents in a collection.

    If document_id is provided, reindex only that document.
    Otherwise, reindex all failed documents in the collection.
    """
    queued_count = 0

    if body and body.document_id:
        queued_count = await _reindex_single_document(
            session, collection_id, body.document_id
        )
    else:
        queued_count = await _reindex_failed_documents(session, collection_id)

    return ReindexResponse(queued_jobs=queued_count)


async def _reindex_single_document(
    session: AsyncSession,
    collection_id: uuid.UUID,
    document_id: uuid.UUID,
) -> int:
    """Create a new ingestion job for a single document."""
    doc_stmt = select(SourceDocument).where(
        SourceDocument.id == document_id,
        SourceDocument.collection_id == collection_id,
        SourceDocument.deleted_at.is_(None),
    )
    doc_result = await session.execute(doc_stmt)
    document = doc_result.scalars().first()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    ver_stmt = select(DocumentVersion).where(
        DocumentVersion.document_id == document_id,
        DocumentVersion.is_active.is_(True),
    )
    ver_result = await session.execute(ver_stmt)
    active_version = ver_result.scalars().first()
    if active_version is None:
        raise HTTPException(status_code=404, detail="No active version found")

    # Reset version status
    active_version.index_status = "pending"

    # Create new ingestion job
    job = IngestionJob(
        collection_id=collection_id,
        version_id=active_version.id,
        status="queued",
    )
    session.add(job)
    await session.flush()
    return 1


async def _reindex_failed_documents(
    session: AsyncSession,
    collection_id: uuid.UUID,
) -> int:
    """Create ingestion jobs for all failed document versions."""
    stmt = select(DocumentVersion).join(SourceDocument).where(
        SourceDocument.collection_id == collection_id,
        SourceDocument.deleted_at.is_(None),
        DocumentVersion.index_status == "failed",
        DocumentVersion.is_active.is_(True),
    )
    result = await session.execute(stmt)
    failed_versions = result.scalars().all()

    queued = 0
    for version in failed_versions:
        version.index_status = "pending"
        job = IngestionJob(
            collection_id=collection_id,
            version_id=version.id,
            status="queued",
        )
        session.add(job)
        queued += 1

    await session.flush()
    return queued