# Architecture

## Overview
The system is a modular RAG platform with a web UI, ingestion workers, metadata storage, vector plus lexical retrieval, and optional graph-enhanced retrieval.

## Component diagram

```text
[Web UI]
   |
   v
[API Gateway / FastAPI]
   |-------------------------------|
   |                               |
   v                               v
[Metadata DB]                [Job Queue / Workers]
   |                               |
   |                               v
   |                        [Parser / Normalizer]
   |                               |
   |                               v
   |                        [Chunker / Enricher]
   |                               |
   |-------------------------------|
   |
   v
[Retriever]
   |------ dense search ------> [Qdrant]
   |------ lexical search ----> [Qdrant / lexical index]
   |------ optional graph ----> [LightRAG / graph layer]
   |
   v
[Reranker]
   |
   v
[Grounded Answer Generator]
   |
   v
[Answer + Citations + Evidence]
```

## Deployment modes

### Local single-user
- Next.js frontend
- FastAPI backend
- local PostgreSQL
- local Qdrant
- local file storage
- optional local LLM services

### Team self-hosted
- reverse proxy
- containerized services
- background workers
- object storage
- shared Postgres and Qdrant

### Managed cloud
- frontend hosting
- autoscaled API/workers
- managed Postgres
- managed object storage
- managed vector DB if desired

## Logical services

### 1. Frontend service
Responsibilities:
- collections dashboard
- document management
- chat/search interface
- evidence inspection
- admin diagnostics

### 2. API service
Responsibilities:
- auth and access checks
- ingestion API
- query API
- admin API
- collection and metadata CRUD

### 3. Ingestion worker service
Responsibilities:
- type detection
- parsing and normalization
- OCR fallback
- transcription jobs
- chunking and enrichment
- embedding creation
- graph extraction jobs

### 4. Retrieval service
Responsibilities:
- dense retrieval
- lexical retrieval
- filter application
- candidate merge and dedupe
- reranker execution
- evidence packaging

### 5. Generation service
Responsibilities:
- grounded prompting
- citation attachment
- abstention logic
- answer formatting

## Storage design

### PostgreSQL tables
Recommended core tables:
- `collections`
- `source_documents`
- `document_versions`
- `derived_assets`
- `chunks`
- `ingestion_jobs`
- `failure_events`
- `query_sessions`
- `answer_records`
- `graph_nodes`
- `graph_edges`

### Qdrant collections
Current implementation: one global collection (`rag_kb_chunks`) with named dense and sparse vectors.
- Dense vector name: `"dense"` (COSINE distance, configurable dimensions)
- Sparse vector name: `"sparse"` (BM25 with IDF modifier)

Payload indexes on: `collection_id`, `document_id`, `version_id`, `version_status`.

Vector record payload includes:
- collection_id
- document_id
- version_id
- chunk_id
- source_type
- title
- section_path
- page_number
- timestamp_start
- timestamp_end
- modality
- confidence
- created_at
- version_status

### Object storage
Use object storage for:
- original uploaded files
- normalized markdown or JSON
- OCR outputs
- transcripts
- extracted images or keyframes

## Document lifecycle
1. File uploaded
2. SourceDocument created
3. IngestionJob queued
4. File parsed into normalized representation
5. Derived artifacts stored
6. Chunk records created
7. Embeddings written to vector store
8. Optional graph entities/edges extracted
9. Job marked succeeded or failed
10. Document visible to query layer

## Versioning strategy
Each content item should support version lineage.

Rules:
- only one version is active by default
- prior versions remain auditable
- retrieval should prefer active version unless query explicitly requests history
- replacing a document should not orphan old chunk records silently

## Metadata model
Minimum metadata fields:
- title
- original filename
- mime type
- collection
- uploader
- source URI if remote
- language
- page count or duration
- parse confidence
- created_at
- updated_at
- indexing status
- active version flag

## Graph layer strategy
Use graph retrieval only as a supplement. Graph nodes and edges may be stored:
- directly in LightRAG-managed structures, or
- mirrored to relational storage for observability

Recommended graph metadata:
- source chunk IDs used to derive node/edge
- extraction confidence
- extraction model version
- canonicalization status

## Failure isolation
The architecture should isolate failures by stage:
- parse failure should not corrupt metadata
- embedding failure should not erase prior active index without explicit rollback
- graph extraction failure should not block baseline document retrieval
- reranker outage should allow degraded retrieval mode

## API surfaces

### Ingestion endpoints
- `POST /collections`
- `POST /collections/{id}/documents`
- `POST /collections/{id}/reindex`
- `GET /ingestion-jobs/{id}`

### Retrieval endpoints
- `POST /collections/{id}/search`
- `POST /collections/{id}/ask`
- `GET /answers/{id}`

### Admin endpoints
- `GET /collections/{id}/health`
- `GET /collections/{id}/failures`
- `POST /documents/{id}/replace`
- `DELETE /documents/{id}`

## Suggested repository layout

```text
/app
  /frontend
  /backend
    /api
    /workers
    /services
    /models
    /prompts
    /tests
  /infra
  /docs
```
