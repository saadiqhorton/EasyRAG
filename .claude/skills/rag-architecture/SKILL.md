---
name: rag-architecture
description: Apply the repository's RAG architecture constraints when working on parsing, indexing, retrieval, reranking, metadata, versioning, and optional graph retrieval.
user-invocable: false
---

## Key reminders
- Keep frontend, API, ingestion, indexing, retrieval, and generation separable.
- Preserve document lineage and confidence metadata.
- Default to hybrid retrieval plus reranking.
- Treat LightRAG or graph retrieval as additive.
- Avoid designs that make citation-grade evidence hard to trace.
