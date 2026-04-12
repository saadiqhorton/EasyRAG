# RAG Knowledge Base Framework Specification

## Document status
Draft v1

## Purpose
This specification defines a modular, production-oriented framework for building a RAG-based knowledge base from scratch with a simple, clean UI. The system must ingest and normalize multiple content types, index them reliably, retrieve grounded evidence consistently, and provide AI-generated answers with source transparency.

The design prioritizes:
- reliability over flashy demos
- clean user experience
- support for multimodal knowledge ingestion
- traceable retrieval and citations
- extensibility for graph-enhanced retrieval such as LightRAG

## Primary goals

### Functional goals
- Ingest Markdown, PDF, DOCX, TXT, HTML, images, and optionally video/audio.
- Normalize heterogeneous content into a structured document model.
- Build a searchable knowledge base from uploaded or connected sources.
- Support grounded question answering with citations.
- Allow users to browse collections, documents, chunks, and indexing state.
- Expose an API and a web UI.
- Support reindexing, versioning, and deletion.

### Non-functional goals
- Keep answers faithful to retrieved context.
- Make failure states visible instead of silent.
- Support hybrid retrieval and reranking.
- Be modular enough to swap parsers, embedding models, vector stores, and LLMs.
- Scale from local single-user deployment to team or cloud deployment.

## Product vision
The product is a knowledge-base platform that lets a user upload source material and ask questions against it with confidence. It should feel simple on the surface, but the backend should preserve document structure, provenance, metadata, and retrieval quality.

The user should be able to:
1. Create one or more knowledge collections.
2. Upload or sync source files.
3. Watch ingestion progress and failures.
4. Search or chat against the indexed knowledge.
5. Inspect the evidence behind every answer.
6. Reindex or remove stale content.

## Supported content types

### Required at MVP
- Markdown
- PDF
- DOCX
- TXT
- HTML
- PNG/JPG images

### Optional in phase 2+
- PPTX
- XLSX/CSV
- audio files
- video files with transcript extraction
- webpage ingestion
- connected cloud sources

## Core design principles
- Retrieval quality is more important than model cleverness.
- Every answer should be traceable to source evidence.
- Text extraction and chunking are first-class system concerns.
- Multimodal support should be honest about confidence and limitations.
- The system must be able to say there is not enough evidence.
- Graph-based retrieval should be additive, not mandatory.

## High-level architecture
The framework is divided into six layers:

1. **UI layer**
   - web app for upload, search, collections, and answer review
2. **API layer**
   - ingestion endpoints, query endpoints, admin endpoints
3. **Ingestion layer**
   - parsing, OCR, transcription, metadata extraction, normalization
4. **Indexing layer**
   - chunking, embedding, lexical indexing, graph extraction, version handling
5. **Retrieval layer**
   - hybrid retrieval, filters, reranking, citation packaging
6. **Generation layer**
   - grounded answer generation, abstention logic, formatting

See [docs/architecture.md](docs/architecture.md) for detailed architecture.

## Recommended reference stack

### Frontend
- Next.js
- Tailwind CSS
- shadcn/ui or similar component library

### Backend
- FastAPI
- background job runner for ingestion
- PostgreSQL for relational metadata
- Redis optional for queues/caching

### Parsing and normalization
- Docling as primary parser/normalizer
- OCR fallback for scanned files
- optional media transcription layer for audio/video

### Retrieval and storage
- Qdrant for vector plus hybrid retrieval
- PostgreSQL metadata tables
- optional object storage for originals and derived artifacts

### LLM and ranking
- embedding model for chunk and document representations
- reranker model for top-k refinement
- answer model with strict grounded prompt

### Optional graph layer
- LightRAG or equivalent graph-enhanced retrieval path

## Why LightRAG is optional, not foundational
LightRAG is useful when the corpus contains rich entity and relationship structure across documents. It can improve recall for relation-heavy knowledge bases. However, it should not be the only retrieval strategy because:
- noisy extraction can create bad graph edges
- plain chunk retrieval is still needed for citation-grade evidence
- multimodal ingestion quality still depends on preprocessing

Recommended approach:
- build a stable hybrid RAG core first
- add LightRAG as an enhancement path for graph-aware retrieval
- evaluate whether it improves real queries before making it default

## User roles

### End user
- uploads content
- manages collections
- asks questions
- reviews sources and citations

### Admin or operator
- configures models and pipelines
- monitors failures
- tunes chunking and retrieval
- manages reindexing rules and system health

## Primary user workflows

### 1. Create collection
- user creates a named knowledge collection
- optional description, tags, access policy

### 2. Ingest content
- user uploads files or submits source URLs
- system parses, normalizes, chunks, indexes, and reports status

### 3. Search and ask
- user submits natural-language query
- system retrieves evidence, reranks, and generates an answer with citations

### 4. Inspect evidence
- user opens document snippets, pages, sections, timestamps, or image-derived evidence

### 5. Maintain knowledge base
- user replaces outdated files, reindexes failed items, removes duplicates, or archives stale content

See [docs/ui-and-workflows.md](docs/ui-and-workflows.md) for deeper workflow definitions.

## Data model overview
The system should model at least the following entities:
- Collection
- SourceDocument
- DocumentVersion
- DerivedAsset
- Chunk
- EmbeddingRecord
- QuerySession
- RetrievalResult
- AnswerRecord
- IngestionJob
- FailureEvent
- GraphNode
- GraphEdge

Detailed structure is in [docs/architecture.md](docs/architecture.md).

## Ingestion specification
The ingestion pipeline must:
- identify file type
- parse into structured intermediate representation
- preserve headings, sections, lists, tables, captions, page numbers, and timestamps where possible
- store original artifacts and normalized output
- create chunks with lineage metadata
- mark confidence for OCR or transcription-derived text
- fail visibly with actionable logs

See [docs/ingestion-pipeline.md](docs/ingestion-pipeline.md).

## Retrieval specification
The retrieval pipeline must:
- support hybrid retrieval: dense plus lexical
- support metadata filtering
- support reranking before answer generation
- deduplicate overlapping candidates
- return citations with chunk lineage
- abstain when evidence is weak

See [docs/retrieval-and-grounding.md](docs/retrieval-and-grounding.md).

## UI specification
The UI should remain simple and clean, but not hide critical system state. It must include:
- collections dashboard
- document library view
- upload and sync views
- ingestion status panel
- search/chat interface
- evidence inspector
- admin diagnostics view

See [docs/ui-and-workflows.md](docs/ui-and-workflows.md).

## Reliability requirements
The system should be considered broken if any of the following become common:
- document text is parsed in the wrong order
- retrieved chunks lack enough context to answer correctly
- old and new document versions conflict without clear precedence
- answers are produced without explicit source evidence
- OCR/transcription confidence is low but hidden
- graph extraction pollutes retrieval with false relations
- users cannot tell whether a document indexed successfully

See [docs/evaluation-and-operations.md](docs/evaluation-and-operations.md) and [docs/risks-and-failure-modes.md](docs/risks-and-failure-modes.md).

## Security and privacy baseline
- collection-level access control
- encryption in transit and at rest
- auditable ingestion and query activity
- configurable retention and deletion policies
- PII-aware document handling where required
- model/provider isolation if using external APIs

## Observability baseline
The system should track:
- ingestion success/failure by file type
- parse confidence and OCR usage rates
- chunk counts and average chunk sizes
- query latency by stage
- retrieval hit quality metrics
- citation coverage rate
- abstention rate
- reindex frequency
- graph extraction error indicators

## Evaluation requirements
The platform needs an evaluation harness with representative questions across document types. Evaluation should measure:
- retrieval recall at top-k
- reranker lift
- answer faithfulness to evidence
- citation correctness
- abstention quality
- failure segmentation by content type

See [docs/evaluation-and-operations.md](docs/evaluation-and-operations.md).

## Phased rollout

### Phase 1: text-first MVP
- collections
- upload UI
- Markdown, PDF, DOCX ingestion
- chunking and embeddings
- hybrid retrieval
- reranking
- grounded answers with citations
- failure logs

### Phase 2: multimodal hardening
- OCR improvements
- image descriptions and image embeddings
- table-aware extraction
- audio/video transcript ingestion
- timestamps and keyframes

### Phase 3: graph augmentation
- entity extraction
- graph storage
- LightRAG integration
- graph-based query mode
- graph debugging UI

### Phase 4: enterprise readiness
- connectors
- RBAC
- audit logs
- org workspaces
- scaling and multi-tenant isolation

See [docs/phased-roadmap.md](docs/phased-roadmap.md).

## Explicit non-goals for MVP
- perfect video scene understanding
- autonomous ingestion from every cloud system
- fully general agentic workflow engine
- graph retrieval as the only retrieval method
- unsupported confidence claims for scanned or low-quality visual documents

## Acceptance criteria for MVP
The MVP is acceptable when all of the following are true:
- A user can create a collection and upload Markdown, PDF, and DOCX files.
- The system clearly shows indexing status and failures.
- The system can answer questions using retrieved evidence with citations.
- The system can decline to answer when evidence is insufficient.
- A user can inspect the exact source chunks used in an answer.
- Reindexing and document replacement work without version confusion.
- Retrieval quality is benchmarked on a defined test set.

## Open decisions
- which embedding model to standardize on
- whether OCR is local-only or provider-assisted
- whether to store raw derived text in PostgreSQL or object storage
- whether graph edges live in PostgreSQL, a graph store, or the LightRAG layer only
- which reranker to use for latency/cost tradeoffs
- whether video support begins with transcript-only or transcript plus keyframe indexing

## Linked documents
- [Architecture](docs/architecture.md)
- [Ingestion Pipeline](docs/ingestion-pipeline.md)
- [Retrieval and Grounding](docs/retrieval-and-grounding.md)
- [UI and Workflows](docs/ui-and-workflows.md)
- [Evaluation and Operations](docs/evaluation-and-operations.md)
- [Risks and Failure Modes](docs/risks-and-failure-modes.md)
- [Phased Roadmap](docs/phased-roadmap.md)
