# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.3.0] - 2026-04-13

### Fixed
- **GZIP detection in file validation** - `_detect_actual_type()` compared 4-byte slice against 2-byte GZIP signature, never matching. Fixed to use `content[:2]`.
- **IngestionJobResponse missing retry_count** - API response schema didn't include the new `retry_count` field. Added to schema and ingestion endpoint response.

### Added
- **Worker dead-letter handling** - Ingestion jobs that fail 3 times (or encounter non-retryable errors) now enter `dead_letter` state instead of retrying indefinitely. Prevents infinite retry loops.
- **Retry tracking across reindex** - `_reindex_single_document()` carries over prior retry_count from the most recent job, so the dead-letter cap is enforced across reindex attempts.
- **`_handle_job_failure()` function** - Centralized failure handler in ingestion worker: increments retry count, records FailureEvent, determines dead_letter vs. failed status, cleans up temp files.
- **File content validation (magic bytes)** - `app/backend/services/file_validation.py` validates uploaded files by checking magic byte signatures (PDF: `%PDF`, DOCX: `PK\x03\x04`) and UTF-8 validity for text types. Prevents MIME type spoofing attacks.
- **Docling timeout guard** - Parser enforces `PARSE_TIMEOUT_SECONDS=120` via `asyncio.wait_for()` wrapping thread pool execution. Files exceeding `MAX_PARSE_FILE_SIZE_MB=100` are rejected before parsing.
- **Alembic initial migration** - `app/backend/alembic/versions/001_initial_schema.py` creates all 9 tables including `retry_count` on `ingestion_jobs` and `evidence_json` on `answer_records`. Auto-applied on startup with `create_all` fallback.
- **`retry_count` on IngestionJob** - ORM model field tracking cumulative failure attempts.
- **`dead_letter` terminal state** - Added to `TERMINAL_STATES` in worker and recognized by reindex logic.
- **Tests: file validation** - `test_file_validation.py`: 26 tests for magic byte validation, MIME type spoofing detection, and actual-type detection.
- **Tests: worker hardening** - `test_worker_hardening.py`: 14 tests for dead-letter logic, retry exhaustion, temp file cleanup, reindex retry carryover, and schema validation.
- **Tests: parser guards** - `test_parser_guards.py`: 10 tests for timeout, file size, MIME type rejection, and ParseResult defaults.
- **Hybrid search validation script** - `scripts/validate_hybrid_search.py`: Standalone script for validating dense, sparse, and RRF fusion searches against a live Qdrant instance.
- **E2E smoke test script** - `scripts/smoke_test_e2e.py`: Full workflow test (upload -> ingest -> search -> ask -> retrieve answer).

## [0.2.0] - 2026-04-12

### Fixed
- **Qdrant dense vector naming** - Collection now creates named "dense" vector instead of unnamed default, matching retrieval prefetch references. Hybrid search would fail at runtime without this fix.
- **Search filters not applied** - `SearchFilters` (modality, section_path_prefix, page_number_min/max) were defined in the schema but never passed to the retrieval query. Filters now propagate through the full retrieval pipeline.
- **GET /answers/{id} returns empty evidence** - Past answers returned placeholder `EvidenceItem` objects with empty text, nil UUIDs, and zero confidence. The endpoint now stores and restores full evidence data via a new `evidence_json` column.
- **Evidence packaging missing document titles** - `package_evidence()` never received DB document titles, falling back to stale chunk-level titles. The search and ask endpoints now query and pass document titles.
- **Temp file leak in worker** - `NamedTemporaryFile(delete=False)` was never cleaned up after parsing. All failure and success paths now explicitly delete the temp file.
- **Document deletion doesn't clean up chunks/assets** - Soft-delete only set `deleted_at` on the source document. PostgreSQL chunks and derived assets for all versions now cascade-delete on document deletion.
- **OCR confidence detection** - Parser checked a non-existent `doc.ocr_used` attribute, giving all documents confidence=1.0. New heuristic checks for empty extraction and OCR artifact patterns.
- **Docling section extraction** - `iterate_items()` yields `(item, level)` tuples, not objects with `.heading`. Updated to properly destructure tuples and detect headings from labels.
- **Docling page mapping** - Updated to handle Docling's provenance (`prov`) attribute correctly.
- **Docling InputFormat enum** - `InputFormat.MARKDOWN` doesn't exist in current Docling; changed to `InputFormat.MD`.
- **Path traversal bypass** - Keys like `col1/../etc/doc.txt` bypassed the resolve-based check. Now also checks for `..` path segments before resolution.
- **Embedding blocks async event loop** - `embed_texts()` was synchronous, blocking the async worker. Added `embed_texts_async()` that runs in a thread pool executor.
- **Embedding dimension validation** - No check that embedding vectors matched Qdrant collection dimensions. Indexer now validates before upsert.
- **Frontend evidence inspector link** - "View original document" linked to `/collections/{documentId}` instead of `/documents/{documentId}`.
- **`_is_valid_uuid(None)` TypeError** - Function didn't handle `None` input, raising `TypeError` on Python 3.14.
- **Build system** - `setuptools.backends._legacy:_Backend` doesn't exist; changed to `setuptools.build_meta`. Added package discovery config.
- **Pydantic forward reference** - `'CollectionHealthResponse' | None` failed on Python 3.14; changed to `Optional["CollectionHealthResponse"]`.
- **Integration test** - `file_size_bytes` assertion had wrong expected value (24 vs 22).

### Added
- `DENSE_VECTOR_NAME` and `SPARSE_VECTOR_NAME` constants in `qdrant_client.py` for consistent named vector references.
- `_build_retrieval_filter()` function that constructs Qdrant filter from collection ID and optional search filters.
- `_build_document_titles()` helper in search API to query DB for current document titles.
- `evidence_json` column on `AnswerRecord` for storing full evidence data.
- `embed_texts_async()` async wrapper that runs embedding in a thread pool.
- `app/backend/services/constants.py` - centralized MIME types and OCR confidence threshold.
- `app/backend/tests/unit/test_production_readiness.py` - 23 tests covering retrieval filters, evidence packaging, versioning, constants consistency, and answer record evidence round-tripping.

## [0.1.0] - 2026-04-12

### Added
- Collection CRUD API - Create, list, get, and delete knowledge collections
- Document upload API - Upload PDF, Markdown, DOCX, TXT, and HTML files with MIME validation and size limits
- Document versioning - Replace documents with new versions; old versions are kept as superseded
- Document management - Soft delete with indexed data cleanup
- Ingestion pipeline - Four-stage processing: parsing, chunking, embedding, indexing
- Document parsing - Docling-based parser with OCR support for PDFs
- Structure-aware chunking - Preserves heading paths, page numbers, and section boundaries
- Dense embedding - sentence-transformers/all-MiniLM-L6-v2 (384 dimensions)
- Hybrid retrieval - Dense semantic + BM25 lexical search with RRF fusion via Qdrant
- Cross-encoder reranking - ms-marco-MiniLM-L-6-v2 with graceful fallback
- Grounded answer generation - LLM-generated answers with strict evidence grounding
- Abstention logic - System refuses to answer when evidence is weak or missing
- Answer modes - Three modes: answered_with_evidence, partially_answered_with_caveat, insufficient_evidence
- Citation tracking - Every answer includes source references with page numbers and section paths
- Evidence inspector - View the exact text chunks used to generate each answer
- Failure visibility - Diagnostics page shows ingestion failures with suggested actions
- PostgreSQL job queue - Background worker with FOR UPDATE SKIP LOCKED
- Qdrant vector store - Single global collection with collection_id filtering
- Local filesystem storage - Pluggable storage protocol for future S3 support
- FastAPI backend - Async API with CORS, health/readiness endpoints
- Next.js 15 frontend - App Router with shadcn/ui components and Tailwind CSS
- Docker Compose - PostgreSQL 16, Qdrant v1.12, API, Worker, Frontend
- Alembic migrations - Async migration support
- Test suite - Backend unit/integration tests with pytest, frontend tests with vitest

### Security
- Path traversal protection on file storage operations
- MIME type validation on document upload
- File size limits enforced at API level
- SHA-256 hashing for uploaded files
- All secrets from environment variables, never hardcoded