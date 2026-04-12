"""Pydantic request/response schemas for the API layer."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Collection schemas
# ---------------------------------------------------------------------------


class CollectionCreate(BaseModel):
    """Request body for creating a collection."""

    name: str = Field(max_length=255, min_length=1)
    description: str | None = None


class CollectionResponse(BaseModel):
    """Response for a single collection."""

    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    document_count: int = 0
    index_status_summary: dict[str, int] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class CollectionDetailResponse(BaseModel):
    """Detailed response for a single collection with health summary."""

    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    document_count: int = 0
    index_status_summary: dict[str, int] = Field(default_factory=dict)
    recent_failures: list["FailureEventResponse"] = Field(default_factory=list)
    health: "CollectionHealthResponse" | None = None

    model_config = {"from_attributes": True}


class CollectionHealthResponse(BaseModel):
    """Health summary for a collection."""

    total_documents: int = 0
    indexed_count: int = 0
    failed_count: int = 0
    last_ingestion_at: datetime | None = None
    storage_bytes: int = 0

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Document schemas
# ---------------------------------------------------------------------------


class DocumentUploadResponse(BaseModel):
    """Response after a document is uploaded."""

    document_id: uuid.UUID
    version_id: uuid.UUID
    job_id: uuid.UUID
    title: str
    mime_type: str
    file_size_bytes: int

    model_config = {"from_attributes": True}


class DocumentListItem(BaseModel):
    """Item in the document list response."""

    id: uuid.UUID
    title: str
    mime_type: str
    index_status: str
    version_number: int
    original_filename: str
    updated_at: datetime
    parse_confidence: float | None = None

    model_config = {"from_attributes": True}


class DocumentVersionResponse(BaseModel):
    """A single document version in the detail response."""

    id: uuid.UUID
    version_number: int
    is_active: bool
    storage_key: str
    parse_confidence: float | None = None
    index_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentResponse(BaseModel):
    """Detailed response for a single document."""

    id: uuid.UUID
    collection_id: uuid.UUID
    title: str
    original_filename: str
    mime_type: str
    file_hash: str
    file_size_bytes: int
    source_uri: str | None = None
    language: str
    page_count: int | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    versions: list[DocumentVersionResponse] = Field(default_factory=list)
    active_version: DocumentVersionResponse | None = None

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    """Paginated document list response."""

    items: list[DocumentListItem]
    total: int
    skip: int
    limit: int


# ---------------------------------------------------------------------------
# Ingestion schemas
# ---------------------------------------------------------------------------


class IngestionJobResponse(BaseModel):
    """Response for an ingestion job status query."""

    id: uuid.UUID
    collection_id: uuid.UUID
    version_id: uuid.UUID
    status: str
    current_stage: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    failures: list["FailureEventResponse"] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class FailureEventResponse(BaseModel):
    """Response for a single failure event."""

    id: uuid.UUID
    job_id: uuid.UUID
    collection_id: uuid.UUID
    stage_name: str
    error_type: str
    message: str
    is_retryable: bool
    suggested_action: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReindexRequest(BaseModel):
    """Request body for triggering a reindex."""

    document_id: uuid.UUID | None = None


class ReindexResponse(BaseModel):
    """Response after triggering a reindex."""

    queued_jobs: int


# ---------------------------------------------------------------------------
# Search and Ask schemas
# ---------------------------------------------------------------------------


class SearchFilters(BaseModel):
    """Optional metadata filters for search queries."""

    modality: str | None = None
    section_path_prefix: str | None = None
    page_number_min: int | None = None
    page_number_max: int | None = None


class SearchRequest(BaseModel):
    """Request body for search endpoint."""

    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=50)
    filters: SearchFilters | None = None


class ScoredChunk(BaseModel):
    """A chunk with its retrieval score."""

    chunk_id: uuid.UUID
    score: float
    text: str
    title: str | None = None
    section_path: str | None = None
    page_number: int | None = None
    modality: str
    confidence: float
    document_id: uuid.UUID
    version_id: uuid.UUID
    collection_id: uuid.UUID

    model_config = {"from_attributes": True}


class SearchResponse(BaseModel):
    """Response for the search endpoint."""

    results: list[ScoredChunk]


class AskRequest(BaseModel):
    """Request body for the ask endpoint."""

    query: str = Field(min_length=1)
    filters: SearchFilters | None = None


class Citation(BaseModel):
    """A citation reference within an answer."""

    source_number: int
    document_title: str
    section_path: str | None = None
    page_number: int | None = None
    chunk_id: uuid.UUID


class EvidenceItem(BaseModel):
    """An evidence item backing an answer."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    section_path: str | None = None
    page_number: int | None = None
    modality: str
    confidence: float
    text: str
    citation_anchor: str
    ocr_used: bool = False


class AskResponse(BaseModel):
    """Response for the ask endpoint."""

    answer_id: uuid.UUID
    answer_text: str
    answer_mode: str
    citations: list[Citation] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class AnswerResponse(BaseModel):
    """Full answer detail response for GET /answers/{id}."""

    id: uuid.UUID
    session_id: uuid.UUID
    collection_id: uuid.UUID
    answer_text: str
    answer_mode: str
    citations: list[Citation] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    reranker_used: bool
    llm_model: str
    latency_ms: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Health schemas
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    """Response for the health endpoint."""

    status: str
    version: str = "0.1.0"


class ReadinessResponse(BaseModel):
    """Response for the readiness endpoint."""

    status: str
    postgres: bool = False
    qdrant: bool = False