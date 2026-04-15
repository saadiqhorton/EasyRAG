# Rule: architecture guardrails

## Required architecture traits
- The system remains modular and adapter-friendly.
- Parsing/normalization, indexing, retrieval, and generation remain separable concerns.
- Metadata and source lineage are first-class, not optional.
- Version-aware retrieval is required.
- Hybrid retrieval plus reranking is the default retrieval posture.
- Graph retrieval, including LightRAG-style paths, is supplemental and must resolve back to source evidence.

## Do not do these
- Do not make LightRAG the only retrieval path.
- Do not design a pure vector-only retrieval stack unless the spec is updated.
- Do not drop lexical retrieval, evidence packaging, or abstention support for speed or convenience.
- Do not collapse all modalities into a single undifferentiated text pipeline.
