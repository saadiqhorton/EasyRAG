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
from ..services.auth import require_auth
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

    # Calculate progress fields
    progress_percent = None
    elapsed_seconds = None

    if job.chunks_total and job.chunks_total > 0:
        if job.status in ("succeeded", "failed", "dead_letter"):
            progress_percent = 100
        elif job.chunks_processed is not None:
            progress_percent = min(100, int((job.chunks_processed / job.chunks_total) * 100))
    elif job.status == "succeeded":
        progress_percent = 100

    if job.started_at:
        elapsed = datetime.now(timezone.utc) - job.started_at
        elapsed_seconds = int(elapsed.total_seconds())

    return IngestionJobResponse(
        id=job.id,
        collection_id=job.collection_id,
        version_id=job.version_id,
        status=job.status,
        current_stage=job.current_stage,
        retry_count=job.retry_count,
        started_at=job.started_at,
        completed_at=job.completed_at,
        created_at=job.created_at,
        failures=failures,
        chunks_total=job.chunks_total,
        chunks_processed=job.chunks_processed,
        progress_percent=progress_percent,
        elapsed_seconds=elapsed_seconds,
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
    api_key: str = require_auth,
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
    """Create a new ingestion job for a single document.

    Increments the retry_count from the most recent failed/dead_letter job
    for this version, so that the dead-letter cap is respected across
    reindex attempts.
    """
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

    # Find the most recent job for this version to carry over retry_count
    last_job_stmt = (
        select(IngestionJob)
        .where(IngestionJob.version_id == active_version.id)
        .order_by(IngestionJob.created_at.desc())
        .limit(1)
    )
    last_job_result = await session.execute(last_job_stmt)
    last_job = last_job_result.scalars().first()
    prior_retries = last_job.retry_count if last_job else 0

    # Check if this version has exceeded max retries (dead_letter)
    if prior_retries >= 3:
        raise HTTPException(
            status_code=400,
            detail=f"Document has exceeded max retries ({prior_retries}). "
                   f"Delete and re-upload to retry.",
        )

    # Reset version status
    active_version.index_status = "pending"

    # Create new ingestion job, carrying over retry history
    job = IngestionJob(
        collection_id=collection_id,
        version_id=active_version.id,
        status="queued",
        retry_count=prior_retries,
    )
    session.add(job)
    await session.flush()
    return 1


async def _reindex_failed_documents(
    session: AsyncSession,
    collection_id: uuid.UUID,
) -> int:
    """Create ingestion jobs for all failed document versions.

    Skips versions that are in dead_letter state (exceeded max retries).
    """
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
        # Check if this version already has a dead_letter job
        dead_letter_stmt = (
            select(IngestionJob)
            .where(
                IngestionJob.version_id == version.id,
                IngestionJob.status == "dead_letter",
            )
        )
        dl_result = await session.execute(dead_letter_stmt)
        if dl_result.scalars().first() is not None:
            continue  # Skip dead_letter versions

        # Find prior retry count
        last_job_stmt = (
            select(IngestionJob)
            .where(IngestionJob.version_id == version.id)
            .order_by(IngestionJob.created_at.desc())
            .limit(1)
        )
        last_job_result = await session.execute(last_job_stmt)
        last_job = last_job_result.scalars().first()
        prior_retries = last_job.retry_count if last_job else 0

        if prior_retries >= 3:
            continue  # Already exceeded max retries

        version.index_status = "pending"
        job = IngestionJob(
            collection_id=collection_id,
            version_id=version.id,
            status="queued",
            retry_count=prior_retries,
        )
        session.add(job)
        queued += 1

    await session.flush()
    return queued