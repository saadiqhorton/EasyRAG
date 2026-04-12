# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

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