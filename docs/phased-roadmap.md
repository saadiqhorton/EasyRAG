# Phased Roadmap

## Phase 1: Text-first MVP
Duration target: shortest path to a usable product

### Deliverables
- collection management
- upload flow
- Markdown, PDF, DOCX support
- normalized document model
- structure-aware chunking
- dense + lexical retrieval
- reranker
- grounded answer generation with citations
- evidence inspector
- ingestion failures view

### Exit criteria
- reliable text-doc ingestion
- stable search and ask flows
- benchmark coverage for core file types

## Phase 2: Multimodal hardening

### Deliverables
- OCR-first handling for scanned documents
- image support with OCR and optional captions/embeddings
- table extraction improvements
- transcript ingestion for audio/video
- timestamps in evidence paths
- optional video keyframe indexing

### Exit criteria
- multimodal queries work with documented limits
- failure and confidence states are exposed clearly

## Phase 3: Graph-augmented retrieval

### Deliverables
- entity extraction pipeline
- relationship extraction pipeline
- canonicalization logic
- LightRAG integration or equivalent
- graph-assisted query mode
- graph debugging diagnostics

### Exit criteria
- graph path measurably improves recall/utility on target query classes
- graph errors do not degrade baseline retrieval

## Phase 4: Scale and governance

### Deliverables
- connectors and sync jobs
- RBAC
- audit trails
- workspace or tenant boundaries
- usage analytics
- quota controls

### Exit criteria
- multi-user reliability
- supportable operational posture

## Phase 5: Advanced enterprise features

### Candidates
- approval workflows for source sets
- human feedback loop on answers
- document trust scoring
- automated regression testing on customer corpora
- policy-aware retrieval filters
