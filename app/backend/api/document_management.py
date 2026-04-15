"""Document replacement and deletion endpoints."""

import hashlib
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import DocumentVersion, IngestionJob, SourceDocument
from ..models.chunk import Chunk
from ..models.derived_asset import DerivedAsset
from ..models.schemas import DocumentUploadResponse
from ..services.auth import require_auth
from ..services.config import Settings, get_settings
from ..services.constants import ALLOWED_MIME_TYPES
from ..services.database import get_session
from ..services.storage import get_storage

logger = logging.getLogger(__name__)

router = APIRouter()


def _compute_hash(content: bytes) -> str:
    """Compute SHA-256 hash of file content."""
    return hashlib.sha256(content).hexdigest()


def _build_storage_key(
    collection_id: uuid.UUID,
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    filename: str,
) -> str:
    """Build the object storage key per architecture pattern."""
    return f"{collection_id}/{document_id}/{version_id}/{filename}"


@router.post(
    "/documents/{document_id}/replace",
    status_code=201,
    response_model=DocumentUploadResponse,
)
async def replace_document(
    document_id: uuid.UUID,
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    api_key: str = require_auth,
) -> DocumentUploadResponse:
    """Replace a document by creating a new version.

    Marks the old active version as inactive (is_active=False,
    index_status='superseded') and creates a new version with
    a new IngestionJob.
    """
    # Validate MIME type
    mime_type = file.content_type or ""
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid MIME type: {mime_type}")

    # Read and validate size
    content = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail="File too large")

    # Validate file content matches claimed MIME type (magic bytes)
    from ..services.file_validation import validate_file_signature
    is_valid, validation_reason = validate_file_signature(content, mime_type)
    if not is_valid:
        logger.warning(
            "file_signature_mismatch mime=%s reason=%s",
            mime_type, validation_reason,
        )
        raise HTTPException(
            status_code=400,
            detail=f"File content does not match claimed type: {validation_reason}",
        )

    # Get existing document
    stmt = select(SourceDocument).where(
        SourceDocument.id == document_id,
        SourceDocument.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    document = result.scalars().first()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # Mark old active versions as superseded
    old_ver_stmt = select(DocumentVersion).where(
        DocumentVersion.document_id == document_id,
        DocumentVersion.is_active.is_(True),
    )
    old_ver_result = await session.execute(old_ver_stmt)
    old_versions = old_ver_result.scalars().all()

    max_version = 0
    for old_ver in old_versions:
        old_ver.is_active = False
        old_ver.index_status = "superseded"
        max_version = max(max_version, old_ver.version_number)

    # Update Qdrant payloads for superseded versions
    if old_versions:
        from ..services.indexer import mark_version_superseded
        for old_ver in old_versions:
            await mark_version_superseded(old_ver.id)

    # Update document metadata
    file_hash = _compute_hash(content)
    document.file_hash = file_hash
    document.file_size_bytes = len(content)
    document.mime_type = mime_type
    document.title = file.filename or document.title
    document.original_filename = file.filename or document.original_filename
    document.updated_at = datetime.now(UTC)

    # Create new version
    version_id = uuid.uuid4()
    storage_key = _build_storage_key(
        document.collection_id, document_id, version_id, file.filename or "untitled"
    )
    new_version = DocumentVersion(
        id=version_id,
        document_id=document_id,
        version_number=max_version + 1,
        is_active=True,
        storage_key=storage_key,
        index_status="pending",
    )
    session.add(new_version)

    # Save file to storage
    storage = get_storage(settings.storage_path)
    await storage.save(storage_key, content)

    # Create ingestion job
    job_id = uuid.uuid4()
    job = IngestionJob(
        id=job_id,
        collection_id=document.collection_id,
        version_id=version_id,
        status="queued",
    )
    session.add(job)
    await session.flush()

    return DocumentUploadResponse(
        document_id=document_id,
        version_id=version_id,
        job_id=job_id,
        title=document.title,
        mime_type=mime_type,
        file_size_bytes=len(content),
    )


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    api_key: str = require_auth,
) -> dict:
    """Soft-delete a document and remove its Qdrant points."""
    stmt = select(SourceDocument).where(
        SourceDocument.id == document_id,
        SourceDocument.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    document = result.scalars().first()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    document.deleted_at = datetime.now(UTC)
    await session.flush()

    # Clean up chunks and derived assets from PostgreSQL for all versions
    version_ids_stmt = select(DocumentVersion.id).where(
        DocumentVersion.document_id == document_id
    )
    version_result = await session.execute(version_ids_stmt)
    version_ids = [row[0] for row in version_result.fetchall()]

    if version_ids:
        # Delete chunks for all versions of this document
        await session.execute(
            delete(Chunk).where(Chunk.version_id.in_(version_ids))
        )
        # Delete derived assets for all versions
        await session.execute(
            delete(DerivedAsset).where(DerivedAsset.version_id.in_(version_ids))
        )

    await session.flush()

    await _delete_qdrant_document_points(document_id, document.collection_id)

    return {"deleted": True}


async def _delete_qdrant_document_points(
    document_id: uuid.UUID, collection_id: uuid.UUID
) -> None:
    """Delete Qdrant points for a document. Awaits the result and logs errors."""
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
                            key="document_id",
                            match=models.MatchValue(value=str(document_id)),
                        )
                    ]
                )
            ),
        )
    except Exception as e:
        logger.warning(
            "qdrant_doc_delete_failed doc=%s error=%s", document_id, e
        )