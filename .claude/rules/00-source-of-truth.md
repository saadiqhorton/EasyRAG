# Rule: spec and docs are authoritative

## Purpose
Keep implementation aligned with the written project spec instead of drifting toward ad hoc decisions.

## Requirements
- Treat `spec.md` as the primary project authority.
- Before changing architecture, retrieval behavior, ingestion behavior, evaluation logic, or trust-critical UX, read the relevant supporting doc in `docs/`.
- If a task conflicts with the spec, call out the conflict explicitly.
- Do not silently override the spec because a different solution seems easier.
- If the task requires changing the spec, update the spec docs as part of the same change or clearly propose the doc changes first.

## Behavior
- Prefer implementing to the spec over improvising new patterns.
- Quote or reference the governing spec area in plans, commit messages, or summaries when the task is significant.
- When uncertain, preserve the more conservative, evidence-preserving interpretation.
