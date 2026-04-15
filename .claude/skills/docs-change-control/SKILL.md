---
name: docs-change-control
description: Use when a task changes repository behavior or assumptions and the spec/docs need to stay synchronized.
user-invocable: false
---

## Instructions
- Determine whether the change affects `spec.md` or a supporting doc.
- Update the minimal relevant docs in the same change.
- Keep high-level intent in `spec.md` and detailed behavior in the appropriate file under `docs/`.
- Call out any intentional divergence clearly.
