# Project: RAG Knowledge Base Framework

## Instruction priority
1. Follow `spec.md` as the primary project source of truth.
2. Follow the relevant supporting docs in `docs/` for the area being changed.
3. Follow `.claude/rules/` for implementation behavior, change control, and trust requirements.
4. If code or task requirements conflict with the spec, stop and surface the conflict explicitly instead of silently choosing.

## What this repository is
This repository defines and will implement a modular, production-oriented RAG knowledge base platform.
The system must ingest and normalize multiple content types, index them reliably, retrieve grounded evidence consistently, and provide AI-generated answers with source transparency.

## Source-of-truth documents
- `spec.md` — product and system specification
- `docs/architecture.md` — service boundaries, data flow, storage design
- `docs/ingestion-pipeline.md` — parser, OCR, normalization, chunking, ingestion stages
- `docs/retrieval-and-grounding.md` — hybrid retrieval, reranking, evidence packaging, abstention
- `docs/ui-and-workflows.md` — UX expectations, evidence inspection, diagnostics, trust surfaces
- `docs/evaluation-and-operations.md` — metrics, monitoring, runbooks, evaluation requirements
- `docs/risks-and-failure-modes.md` — known ways the system can fail or become untrustworthy
- `docs/phased-roadmap.md` — delivery phases and exit criteria

## Non-negotiable product constraints
- Retrieval quality is more important than model cleverness.
- Every answer must be traceable to source evidence.
- The system must support abstention when evidence is weak or conflicting.
- LightRAG is optional and additive, not the foundation of the system.
- Hybrid retrieval and reranking are required unless the spec is explicitly changed.
- UI must expose failures, indexing state, and evidence clearly.
- Do not flatten all modalities into plain text and pretend capability is equal across them.

## Working rules
- Read `spec.md` and the most relevant doc(s) before changing architecture, APIs, retrieval logic, ingestion logic, or trust-critical UX.
- Keep implementations modular so parsers, embedders, rerankers, vector stores, and graph retrieval paths can be swapped.
- Preserve source lineage in designs and code: document, version, section, page, timestamp, modality, and confidence where relevant.
- Prefer additive, minimal changes over broad speculative rewrites.
- Do not invent repository structure, services, or commands that are not present unless you are explicitly scaffolding them.
- When scaffolding, keep names aligned with the spec terminology.

## How to respond to implementation tasks
- Start by identifying the spec sections that govern the task.
- State any conflicts or ambiguities before coding.
- Implement the smallest correct change that moves the repo toward the spec.
- Update the relevant docs when behavior, architecture, or workflow changes.
- Add or update tests/evals where the task affects ingestion, retrieval, grounding, or user trust.

## Commands currently safe and relevant in this repo
These are the most useful repo-level inspection commands right now:
- `find .claude -maxdepth 3 -type f | sort`
- `find docs -maxdepth 2 -type f | sort`
- `sed -n '1,220p' spec.md`
- `sed -n '1,220p' docs/<file>.md`
- `git status`
- `git diff --stat`
- `git diff`

## Future app command policy
When actual app scaffolding is added, update this file with the real run, test, lint, typecheck, and build commands.
Until then, do not assume `frontend/`, `backend/`, `workers/`, `pnpm`, `uv`, or Docker commands are available unless those files are added.

## Running commands
### Backend tests
```bash
# Set up virtual environment (one-time)
python3 -m venv .venv
.venv/bin/pip install -e "app/backend/[dev]"

# Run unit tests
.venv/bin/python -m pytest app/backend/tests/unit/ -v

# Run integration tests
.venv/bin/python -m pytest app/backend/tests/integration/ -v

# Run all tests
.venv/bin/python -m pytest app/backend/tests/ -v
```

### Frontend tests
```bash
cd app/frontend && npm test
```

## Definition of done for spec-sensitive work
A change is not done unless:
- it aligns with the applicable spec docs,
- it does not weaken grounding or evidence traceability,
- it does not hide failures behind a cleaner UI,
- and any spec drift is either resolved or explicitly documented.
