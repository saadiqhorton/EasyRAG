---
name: grounding-and-citations
description: Use when working on answer generation, evidence packaging, abstention, citations, or trust-sensitive retrieval behavior.
user-invocable: false
---

## Grounding rules
- Answers must stay within retrieved evidence.
- Support abstention when evidence is weak, conflicting, or modality-limited.
- Preserve the final evidence set used for answering.
- Keep citations inspectable down to document, version, and page/section/timestamp where available.
