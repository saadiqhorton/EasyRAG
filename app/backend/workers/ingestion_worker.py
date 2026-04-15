"""Ingestion worker that polls PostgreSQL for queued jobs."""

import asyncio
import logging
import os
import tempfile
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
from ..services.embedder import embed_texts_async

logger = logging.getLogger(__name__)

# Job state machine stages in order
STAGES = ["parsing", "chunking", "embedding", "indexing"]
TERMINAL_STATES = ["succeeded", "failed", "dead_letter"]

# Maximum retries before a job enters dead_letter state
MAX_RETRIES = 3


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


async def _handle_job_failure(
    session: AsyncSession,
    job: IngestionJob,
    stage_name: str,
    error_type: str,
    message: str,
    is_retryable: bool = True,
    suggested_action: str | None = None,
    version: DocumentVersion | None = None,
    tmp_path: str | None = None,
) -> None:
    """Handle a job failure with retry tracking and dead-letter logic.

    Increments retry_count. If the job has been retried too many times
    or the failure is not retryable, marks it as dead_letter.
    Otherwise marks as failed so it can be re-queued via reindex.
    """
    # Clean up temp file if provided
    if tmp_path and os.path.exists(tmp_path):
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    # Increment retry count and record failure
    job.retry_count += 1
    await _record_failure(
        session, job.id, job.collection_id,
        stage_name, error_type, message,
        is_retryable=is_retryable,
        suggested_action=suggested_action,
    )

    # Determine final state: dead_letter if exhausted or non-retryable
    if not is_retryable or job.retry_count >= MAX_RETRIES:
        logger.warning(
            "job_dead_letter job=%s retries=%d stage=%s error_type=%s",
            job.id, job.retry_count, stage_name, error_type,
        )
        await _update_job_status(session, job.id, "dead_letter", stage_name)
        if version is not None:
            version.index_status = "failed"
            await session.flush()
    else:
        await _update_job_status(session, job.id, "failed", stage_name)
        if version is not None:
            version.index_status = "failed"
            await session.flush()


async def _process_job(job: IngestionJob, session: AsyncSession) -> None:
    """Process a single ingestion job through all stages."""
    from ..models.source_document import SourceDocument
    from ..services.indexer import mark_version_superseded, upsert_chunks
    from ..services.parser import parse_document
    from ..services.chunker import chunk_document
    from ..services.storage import get_storage
    from ..services.qdrant_client import ensure_collection

    settings = get_settings()
    storage = get_storage(settings.storage_path)
    version = await session.get(DocumentVersion, job.version_id)
    if version is None:
        await _handle_job_failure(
            session, job,
            stage_name="parsing",
            error_type="version_not_found",
            message=f"Document version {job.version_id} not found",
            is_retryable=False,
        )
        return

    # Stage 1: Parsing
    await _update_job_status(session, job.id, "parsing", "parsing")
    result = None
    tmp_path = None
    try:
        file_content = await storage.get(version.storage_key)

        # Write to a temp file that the parser can read.
        # Use delete=False so the file persists for the parser,
        # then clean it up explicitly after parsing.
        suffix = _get_suffix(version.storage_key)
        with tempfile.NamedTemporaryFile(
            suffix=suffix, delete=False, dir=tempfile.gettempdir()
        ) as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name

        mime_type = _guess_mime(version.storage_key)
        result = await parse_document(tmp_path, mime_type)

        # Store derived assets alongside the original file.
        # storage_key points to the file (e.g. col/doc/ver/file.md),
        # so derived assets go under col/doc/ver/_derived/ to avoid
        # trying to create a directory named after the file.
        storage_dir = "/".join(version.storage_key.split("/")[:-1])
        derived_prefix = f"{storage_dir}/_derived"

        if result.normalized_markdown:
            md_key = f"{derived_prefix}/normalized.md"
            await storage.save(md_key, result.normalized_markdown.encode())
            md_asset = DerivedAsset(
                version_id=version.id,
                asset_type="normalized_markdown",
                storage_key=md_key,
            )
            session.add(md_asset)

        if result.normalized_json:
            json_key = f"{derived_prefix}/normalized.json"
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
        await _handle_job_failure(
            session, job,
            stage_name="parsing",
            error_type="parse_failed",
            message=str(e),
            is_retryable=True,
            suggested_action="Check file integrity and format.",
            version=version,
            tmp_path=tmp_path,
        )
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

        # Set total chunks for progress tracking
        job.chunks_total = len(chunks)
        job.chunks_processed = 0
        await session.flush()

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
        await _handle_job_failure(
            session, job,
            stage_name="chunking",
            error_type="chunk_validation_failed",
            message=str(e),
            is_retryable=True,
            suggested_action="Check chunking configuration and document structure.",
            version=version,
            tmp_path=tmp_path,
        )
        return

    # Stage 3: Embedding
    await _update_job_status(session, job.id, "embedding", "embedding")
    dense_vectors = []
    try:
        texts = [c.text_content for c in chunks]
        dense_vectors = await embed_texts_async(texts)
        # Update progress: embedding complete = all chunks processed for embedding
        job.chunks_processed = len(chunks)
        await session.flush()
    except Exception as e:
        logger.error("embedding_failed job=%s error=%s", job.id, e)
        await _handle_job_failure(
            session, job,
            stage_name="embedding",
            error_type="embedding_failed",
            message=str(e),
            is_retryable=True,
            suggested_action="Check embedding model availability.",
            version=version,
            tmp_path=tmp_path,
        )
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
        await _handle_job_failure(
            session, job,
            stage_name="indexing",
            error_type="indexing_failed",
            message=str(e),
            is_retryable=True,
            suggested_action="Check Qdrant availability and retry.",
            version=version,
            tmp_path=tmp_path,
        )
        return

    # Success
    # Clean up temp file after all stages complete
    if tmp_path and os.path.exists(tmp_path):
        try:
            os.unlink(tmp_path)
        except OSError:
            logger.warning("tmp_cleanup_failed path=%s", tmp_path)
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
        "ingestion_worker_started poll_interval=%.1fs max_retries=%d",
        settings.worker_poll_interval, MAX_RETRIES,
    )

    while True:
        try:
            async with factory() as session:
                async with session.begin():
                    job = await _poll_next_job(session)
                    if job is not None:
                        logger.info(
                            "processing job=%s version=%s retry_count=%d",
                            job.id, job.version_id, job.retry_count,
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