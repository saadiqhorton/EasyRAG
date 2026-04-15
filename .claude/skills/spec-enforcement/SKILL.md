---
name: spec-enforcement
description: Enforce spec.md and docs as the source of truth for architecture, workflows, retrieval behavior, ingestion behavior, and trust-sensitive UI changes.
user-invocable: false
---

## Purpose
Load this skill whenever the task could drift away from the written project specification.

## Instructions
- Read `spec.md` first.
- Read the most relevant file(s) in `docs/` for the area being changed.
- Identify any mismatch between the requested change and the written spec.
- Prefer conservative, evidence-preserving interpretations.
- If the task would require spec drift, say so explicitly and update docs rather than silently diverging.
