"""Document upload and listing endpoints."""

import hashlib
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Collection, DocumentVersion, IngestionJob, SourceDocument
from ..models.schemas import (
    DocumentListItem,
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadResponse,
    DocumentVersionResponse,
)
from ..services.config import Settings, get_settings
from ..services.database import get_session
from ..services.storage import get_storage

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_MIME_TYPES = {
    "text/markdown",
    "text/x-markdown",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/html",
}


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
    "/collections/{collection_id}/documents",
    status_code=201,
    response_model=DocumentUploadResponse,
)
async def upload_document(
    collection_id: uuid.UUID,
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> DocumentUploadResponse:
    """Upload a document to a collection.

    Validates MIME type, enforces size limit, computes hash, and
    creates SourceDocument, DocumentVersion, and IngestionJob records.
    """
    # Validate MIME type
    mime_type = file.content_type or ""
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid MIME type: {mime_type}. "
            f"Allowed: {', '.join(sorted(ALLOWED_MIME_TYPES))}",
        )

    # Read content and validate size
    content = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {len(content)} bytes. "
            f"Maximum: {max_bytes} bytes ({settings.max_upload_size_mb}MB).",
        )

    # Verify collection exists
    col_stmt = select(Collection).where(Collection.id == collection_id)
    col_result = await session.execute(col_stmt)
    if col_result.scalars().first() is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Compute hash
    file_hash = _compute_hash(content)
    title = file.filename or "untitled"
    original_filename = file.filename or "untitled"
    file_size = len(content)

    # Create SourceDocument
    document_id = uuid.uuid4()
    document = SourceDocument(
        id=document_id,
        collection_id=collection_id,
        title=title,
        original_filename=original_filename,
        mime_type=mime_type,
        file_hash=file_hash,
        file_size_bytes=file_size,
    )
    session.add(document)

    # Create DocumentVersion
    version_id = uuid.uuid4()
    storage_key = _build_storage_key(
        collection_id, document_id, version_id, original_filename
    )
    version = DocumentVersion(
        id=version_id,
        document_id=document_id,
        version_number=1,
        is_active=True,
        storage_key=storage_key,
        index_status="pending",
    )
    session.add(version)

    # Save file to object storage
    storage = get_storage(settings.storage_path)
    await storage.save(storage_key, content)

    # Create IngestionJob
    job_id = uuid.uuid4()
    job = IngestionJob(
        id=job_id,
        collection_id=collection_id,
        version_id=version_id,
        status="queued",
    )
    session.add(job)
    await session.flush()

    return DocumentUploadResponse(
        document_id=document_id,
        version_id=version_id,
        job_id=job_id,
        title=title,
        mime_type=mime_type,
        file_size_bytes=file_size,
    )


@router.get(
    "/collections/{collection_id}/documents",
    response_model=DocumentListResponse,
)
async def list_documents(
    collection_id: uuid.UUID,
    skip: int = 0,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
) -> DocumentListResponse:
    """List documents in a collection with status information."""
    # Total count
    count_stmt = select(func.count(SourceDocument.id)).where(
        SourceDocument.collection_id == collection_id,
        SourceDocument.deleted_at.is_(None),
    )
    count_result = await session.execute(count_stmt)
    total = count_result.scalar() or 0

    # Fetch documents with active version info
    stmt = (
        select(SourceDocument)
        .where(
            SourceDocument.collection_id == collection_id,
            SourceDocument.deleted_at.is_(None),
        )
        .order_by(SourceDocument.updated_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(stmt)
    documents = result.scalars().all()

    items = []
    for doc in documents:
        active_ver = await _get_active_version(session, doc.id)
        items.append(
            DocumentListItem(
                id=doc.id,
                title=doc.title,
                mime_type=doc.mime_type,
                index_status=active_ver.index_status if active_ver else "pending",
                version_number=active_ver.version_number if active_ver else 0,
                original_filename=doc.original_filename,
                updated_at=doc.updated_at,
                parse_confidence=active_ver.parse_confidence if active_ver else None,
            )
        )

    return DocumentListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> DocumentResponse:
    """Get detailed information about a single document."""
    stmt = select(SourceDocument).where(
        SourceDocument.id == document_id,
        SourceDocument.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    document = result.scalars().first()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    ver_stmt = select(DocumentVersion).where(
        DocumentVersion.document_id == document_id
    ).order_by(DocumentVersion.version_number.asc())
    ver_result = await session.execute(ver_stmt)
    versions = ver_result.scalars().all()

    version_responses = [_version_to_response(v) for v in versions]
    active_version = next(
        (v for v in version_responses if v.is_active), None
    )

    return DocumentResponse(
        id=document.id,
        collection_id=document.collection_id,
        title=document.title,
        original_filename=document.original_filename,
        mime_type=document.mime_type,
        file_hash=document.file_hash,
        file_size_bytes=document.file_size_bytes,
        source_uri=document.source_uri,
        language=document.language,
        page_count=document.page_count,
        created_at=document.created_at,
        updated_at=document.updated_at,
        deleted_at=document.deleted_at,
        versions=version_responses,
        active_version=active_version,
    )


async def _get_active_version(
    session: AsyncSession, document_id: uuid.UUID
) -> DocumentVersion | None:
    """Get the active version for a document."""
    stmt = select(DocumentVersion).where(
        DocumentVersion.document_id == document_id,
        DocumentVersion.is_active.is_(True),
    )
    result = await session.execute(stmt)
    return result.scalars().first()


def _version_to_response(v: DocumentVersion) -> DocumentVersionResponse:
    """Map a DocumentVersion ORM object to a response schema."""
    return DocumentVersionResponse(
        id=v.id,
        version_number=v.version_number,
        is_active=v.is_active,
        storage_key=v.storage_key,
        parse_confidence=v.parse_confidence,
        index_status=v.index_status,
        created_at=v.created_at,
    )