// TypeScript types matching backend Pydantic schemas
// See architecture.md Section 7 (Data Models) and Section 8 (API Design)

// ─── Collection ───────────────────────────────────────────────────

export interface Collection {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
  document_count: number;
  index_status_summary: IndexStatusSummary;
}

export interface IndexStatusSummary {
  pending: number;
  indexing: number;
  indexed: number;
  failed: number;
  superseded: number;
}

export interface CollectionCreate {
  name: string;
  description?: string;
}

export interface CollectionDetail extends Collection {
  recent_failures: FailureEvent[];
  health: CollectionHealth;
}

// ─── Document ────────────────────────────────────────────────────

export interface DocumentListItem {
  id: string;
  title: string;
  mime_type: string;
  index_status: DocumentStatus;
  version_number: number;
  original_filename: string;
  updated_at: string;
  parse_confidence: number | null;
}

export interface DocumentDetail {
  id: string;
  collection_id: string;
  title: string;
  original_filename: string;
  mime_type: string;
  file_hash: string;
  file_size_bytes: number;
  source_uri: string | null;
  language: string;
  page_count: number | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  versions: DocumentVersion[];
  active_version: DocumentVersion | null;
}

export interface DocumentVersion {
  id: string;
  version_number: number;
  is_active: boolean;
  storage_key: string;
  parse_confidence: number | null;
  index_status: DocumentStatus;
  created_at: string;
}

export interface DocumentUploadResponse {
  document_id: string;
  version_id: string;
  job_id: string;
  title: string;
  mime_type: string;
  file_size_bytes: number;
}

export type DocumentStatus =
  | "pending"
  | "indexing"
  | "indexed"
  | "failed"
  | "superseded";

// ─── Ingestion ───────────────────────────────────────────────────

export type IngestionJobStatus =
  | "queued"
  | "parsing"
  | "chunking"
  | "embedding"
  | "indexing"
  | "succeeded"
  | "failed";

export interface IngestionJob {
  id: string;
  collection_id: string;
  version_id: string;
  status: IngestionJobStatus;
  current_stage: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  failures: FailureEvent[];
}

export interface FailureEvent {
  id: string;
  job_id: string;
  collection_id: string;
  stage_name: string;
  error_type: string;
  message: string;
  is_retryable: boolean;
  suggested_action: string | null;
  created_at: string;
}

// ─── Search / Ask ────────────────────────────────────────────────

export interface SearchRequest {
  query: string;
  limit?: number;
  filters?: SearchFilters;
}

export interface SearchFilters {
  source_type?: string[];
  modality?: string[];
  min_confidence?: number;
}

export interface ScoredChunk {
  chunk_id: string;
  score: number;
  text: string;
  title: string | null;
  section_path: string | null;
  page_number: number | null;
  modality: string;
  confidence: number;
  document_id: string;
}

export interface SearchResponse {
  results: ScoredChunk[];
}

export interface AskRequest {
  query: string;
  filters?: SearchFilters;
}

export type AnswerMode =
  | "answered_with_evidence"
  | "partially_answered_with_caveat"
  | "insufficient_evidence";

export interface Citation {
  source_number: number;
  document_title: string;
  page_number: number | null;
  section_path: string | null;
  chunk_id: string;
}

export interface EvidenceItem {
  chunk_id: string;
  text: string;
  document_id: string;
  document_title: string;
  page_number: number | null;
  section_path: string | null;
  modality: string;
  confidence: number;
  ocr_used: boolean;
  citation_anchor: string;
}

export interface AskResponse {
  answer_id: string;
  answer_text: string;
  answer_mode: AnswerMode;
  citations: Citation[];
  evidence: EvidenceItem[];
}

export interface AnswerDetail {
  id: string;
  session_id: string;
  collection_id: string;
  answer_text: string;
  answer_mode: AnswerMode;
  citations: Citation[];
  evidence: EvidenceItem[];
  reranker_used: boolean;
  llm_model: string;
  latency_ms: number;
  created_at: string;
}

// ─── Health ───────────────────────────────────────────────────────

export interface CollectionHealth {
  total_documents: number;
  indexed_count: number;
  failed_count: number;
  last_ingestion_at: string | null;
  storage_bytes: number;
}

export interface SystemHealth {
  status: string;
  version: string;
}

export interface ReadinessCheck {
  status: string;
  postgres: boolean;
  qdrant: boolean;
}

// ─── Reindex ─────────────────────────────────────────────────────

export interface ReindexRequest {
  document_id?: string;
}

export interface ReindexResponse {
  queued_jobs: number;
}