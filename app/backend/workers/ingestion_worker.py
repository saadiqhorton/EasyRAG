"""Ingestion worker that polls PostgreSQL for queued jobs."""

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.chunk import Chunk
from ..models.derived_asset import DerivedAsset
from ..models.document_version import DocumentVersion
from ..models.failure_event import FailureEvent
from ..models.ingestion_job import IngestionJob
from ..services.config import get_settings
from ..services.database import get_session_factory, init_db

logger = logging.getLogger(__name__)

# Job state machine stages in order
STAGES = ["parsing", "chunking", "embedding", "indexing"]
TERMINAL_STATES = ["succeeded", "failed"]


async def _poll_next_job(session: AsyncSession) -> IngestionJob | None:
    """Poll for the next queued ingestion job using FOR UPDATE SKIP LOCKED."""
    stmt = (
        select(IngestionJob)
        .where(IngestionJob.status == "queued")
        .order_by(IngestionJob.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _update_job_status(
    session: AsyncSession,
    job_id: uuid.UUID,
    status: str,
    current_stage: str | None = None,
) -> None:
    """Update job status and stage."""
    job = await session.get(IngestionJob, job_id)
    if job is None:
        return
    job.status = status
    job.current_stage = current_stage
    if status in TERMINAL_STATES:
        job.completed_at = datetime.now(UTC)
    elif status not in ("queued",) and job.started_at is None:
        job.started_at = datetime.now(UTC)
    await session.flush()


async def _record_failure(
    session: AsyncSession,
    job_id: uuid.UUID,
    collection_id: uuid.UUID,
    stage_name: str,
    error_type: str,
    message: str,
    is_retryable: bool = True,
    suggested_action: str | None = None,
) -> None:
    """Record a failure event for a job."""
    failure = FailureEvent(
        job_id=job_id,
        collection_id=collection_id,
        stage_name=stage_name,
        error_type=error_type,
        message=message,
        is_retryable=is_retryable,
        suggested_action=suggested_action,
    )
    session.add(failure)
    await session.flush()


async def _process_job(job: IngestionJob, session: AsyncSession) -> None:
    """Process a single ingestion job through all stages."""
    from ..models.source_document import SourceDocument
    from ..services.indexer import mark_version_superseded, upsert_chunks
    from ..services.parser import parse_document
    from ..services.chunker import chunk_document
    from ..services.embedder import embed_texts
    from ..services.storage import get_storage
    from ..services.qdrant_client import ensure_collection

    settings = get_settings()
    storage = get_storage(settings.storage_path)
    version = await session.get(DocumentVersion, job.version_id)
    if version is None:
        await _record_failure(
            session, job.id, job.collection_id,
            "parsing", "version_not_found",
            f"Document version {job.version_id} not found",
            is_retryable=False,
        )
        await _update_job_status(session, job.id, "failed", "parsing")
        return

    # Stage 1: Parsing
    await _update_job_status(session, job.id, "parsing", "parsing")
    result = None
    try:
        file_content = await storage.get(version.storage_key)
        import tempfile

        with tempfile.NamedTemporaryFile(
            suffix=_get_suffix(version.storage_key), delete=False
        ) as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name

        mime_type = _guess_mime(version.storage_key)
        result = await parse_document(tmp_path, mime_type)

        # Store derived assets
        if result.normalized_markdown:
            md_key = f"{version.storage_key}/normalized.md"
            await storage.save(md_key, result.normalized_markdown.encode())
            md_asset = DerivedAsset(
                version_id=version.id,
                asset_type="normalized_markdown",
                storage_key=md_key,
            )
            session.add(md_asset)

        if result.normalized_json:
            json_key = f"{version.storage_key}/normalized.json"
            await storage.save(json_key, result.normalized_json.encode())
            json_asset = DerivedAsset(
                version_id=version.id,
                asset_type="normalized_json",
                storage_key=json_key,
            )
            session.add(json_asset)

        # Update version parse confidence
        version.parse_confidence = result.confidence
        await session.flush()
    except Exception as e:
        logger.error("parse_failed job=%s error=%s", job.id, e)
        await _record_failure(
            session, job.id, job.collection_id,
            "parsing", "parse_failed",
            str(e), is_retryable=True,
            suggested_action="Check file integrity and format.",
        )
        await _update_job_status(session, job.id, "failed", "parsing")
        return

    # Stage 2: Chunking
    await _update_job_status(session, job.id, "chunking", "chunking")
    chunks = []
    try:
        doc = await session.get(SourceDocument, version.document_id)
        doc_id = version.document_id

        chunks = chunk_document(
            text_content=result.text_content,
            sections=result.sections,
            page_mapping=result.page_mapping,
            collection_id=job.collection_id,
            document_id=doc_id,
            version_id=version.id,
            confidence=result.confidence,
            modality=result.modality,
            max_tokens=settings.chunk_max_tokens,
            overlap_tokens=settings.chunk_overlap_tokens,
            title=result.title,
        )

        # Insert chunk records
        for chunk_data in chunks:
            chunk_record = Chunk(
                id=chunk_data.id,
                version_id=chunk_data.version_id,
                collection_id=chunk_data.collection_id,
                document_id=chunk_data.document_id,
                order_index=chunk_data.order_index,
                title=chunk_data.title,
                section_path=chunk_data.section_path,
                page_number_start=chunk_data.page_number_start,
                page_number_end=chunk_data.page_number_end,
                modality=chunk_data.modality,
                confidence=chunk_data.confidence,
                token_count=chunk_data.token_count,
                text_content=chunk_data.text_content,
            )
            session.add(chunk_record)
        await session.flush()
    except Exception as e:
        logger.error("chunk_failed job=%s error=%s", job.id, e)
        await _record_failure(
            session, job.id, job.collection_id,
            "chunking", "chunk_validation_failed",
            str(e), is_retryable=True,
            suggested_action="Check chunking configuration and document structure.",
        )
        await _update_job_status(session, job.id, "failed", "chunking")
        return

    # Stage 3: Embedding
    await _update_job_status(session, job.id, "embedding", "embedding")
    dense_vectors = []
    try:
        texts = [c.text_content for c in chunks]
        dense_vectors = embed_texts(texts)
    except Exception as e:
        logger.error("embedding_failed job=%s error=%s", job.id, e)
        await _record_failure(
            session, job.id, job.collection_id,
            "embedding", "embedding_failed",
            str(e), is_retryable=True,
            suggested_action="Check embedding model availability.",
        )
        await _update_job_status(session, job.id, "failed", "embedding")
        return

    # Stage 4: Indexing
    await _update_job_status(session, job.id, "indexing", "indexing")
    try:
        await ensure_collection()

        # Mark old active version as superseded if replacing
        if version.is_active:
            old_versions_stmt = select(DocumentVersion).where(
                DocumentVersion.document_id == version.document_id,
                DocumentVersion.id != version.id,
            )
            old_result = await session.execute(old_versions_stmt)
            for old_ver in old_result.scalars().all():
                if old_ver.is_active:
                    old_ver.is_active = False
                    old_ver.index_status = "superseded"
                if old_ver.index_status not in ("superseded", "failed"):
                    old_ver.index_status = "superseded"
                await mark_version_superseded(old_ver.id)

        chunk_dicts = [
            {
                "id": c.id,
                "collection_id": c.collection_id,
                "document_id": c.document_id,
                "version_id": c.version_id,
                "title": c.title,
                "section_path": c.section_path,
                "page_number_start": c.page_number_start,
                "modality": c.modality,
                "confidence": c.confidence,
                "text_content": c.text_content,
            }
            for c in chunks
        ]
        await upsert_chunks(chunk_dicts, dense_vectors)

        # Mark version as indexed
        version.index_status = "indexed"
        await session.flush()
    except Exception as e:
        logger.error("indexing_failed job=%s error=%s", job.id, e)
        await _record_failure(
            session, job.id, job.collection_id,
            "indexing", "indexing_failed",
            str(e), is_retryable=True,
            suggested_action="Check Qdrant availability and retry.",
        )
        await _update_job_status(session, job.id, "failed", "indexing")
        version.index_status = "failed"
        await session.flush()
        return

    # Success
    await _update_job_status(session, job.id, "succeeded")
    logger.info("ingestion_succeeded job=%s chunks=%d", job.id, len(chunks))


def _get_suffix(storage_key: str) -> str:
    """Get file suffix from storage key."""
    key = storage_key.rsplit("/", 1)[-1]
    dot = key.rfind(".")
    return key[dot:] if dot >= 0 else ""


def _guess_mime(storage_key: str) -> str:
    """Guess MIME type from storage key extension."""
    suffix = _get_suffix(storage_key).lower()
    mime_map = {
        ".md": "text/markdown",
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".txt": "text/plain",
        ".html": "text/html",
    }
    return mime_map.get(suffix, "text/plain")


async def run_worker() -> None:
    """Main worker loop: poll for jobs and process them."""
    settings = get_settings()
    init_db(settings)
    factory = get_session_factory()

    logger.info(
        "ingestion_worker_started poll_interval=%.1fs",
        settings.worker_poll_interval,
    )

    while True:
        try:
            async with factory() as session:
                async with session.begin():
                    job = await _poll_next_job(session)
                    if job is not None:
                        logger.info(
                            "processing job=%s version=%s",
                            job.id, job.version_id,
                        )
                        await _process_job(job, session)
                    else:
                        await asyncio.sleep(settings.worker_poll_interval)
        except Exception as e:
            logger.error("worker_loop_error: %s", e, exc_info=True)
            await asyncio.sleep(settings.worker_poll_interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker())