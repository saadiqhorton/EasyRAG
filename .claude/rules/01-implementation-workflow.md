# Rule: implementation workflow

## For every non-trivial task
1. Identify which spec file(s) govern the task.
2. Inspect the current repository state before proposing new structure.
3. Plan the smallest viable change that respects the architecture.
4. Implement incrementally.
5. Verify the result.
6. Update docs if the repo behavior, structure, or assumptions changed.

## Constraints
- Avoid broad rewrites unless the task explicitly calls for one.
- Avoid introducing new dependencies without a clear need tied to the spec.
- Preserve modular boundaries between frontend, API, ingestion, indexing, retrieval, and generation concerns.
- Keep naming aligned with the existing spec vocabulary.
