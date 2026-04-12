# UI and Workflows

## Design goals
- simple, clean, low-clutter interface
- visible system state
- fast path for upload and ask
- easy inspection of evidence and failures

## Primary screens

### 1. Collections dashboard
Shows:
- collection cards
- document counts
- indexing status summary
- recent failures
- recent activity

Actions:
- create collection
- open collection
- upload documents

### 2. Collection detail view
Tabs:
- Overview
- Documents
- Ask
- Search
- Diagnostics
- Settings

### 3. Document library
Columns:
- title
- type
- status
- version
- source
- updated date
- parse confidence

Actions:
- open
- replace
- reindex
- archive
- delete

### 4. Upload flow
The upload experience should show:
- files in queue
- per-file progress
- parser stage
- OCR/transcription stage if used
- warnings and failures

### 5. Ask interface
Core elements:
- query input
- answer pane
- citations panel
- retrieved evidence drawer
- filters

Optional advanced controls:
- retrieval mode: standard or graph-assisted
- answer mode: concise or detailed
- collection subsets

### 6. Evidence inspector
Should show:
- chunk text
- source document title
- page number or timestamp
- section path
- parse confidence
- whether OCR/transcript was used

### 7. Diagnostics view
For operators or advanced users:
- ingestion errors
- failed files
- chunk counts
- retrieval traces
- reranker diagnostics
- graph extraction warnings

## UX rules
- never hide ingestion failure behind a green success badge
- never show a polished answer without sources nearby
- always show whether a document is still indexing
- make reindex and replace obvious but safe
- let users open the original source artifact

## Example workflow: upload then ask
1. User opens a collection.
2. User uploads 10 files.
3. UI shows each file progressing through parse, chunk, embed, and index stages.
4. Two files show warnings for OCR confidence.
5. User asks a question.
6. Answer returns with citations.
7. User opens evidence drawer and reviews page references.

## Example workflow: failed document recovery
1. Document fails during parsing.
2. UI shows failure badge and failure reason.
3. User opens diagnostics.
4. User retries with OCR enabled or replaces the file.
5. Successful reindex updates the active version.

## Minimal MVP wireframe outline

```text
[Sidebar]
- Collections
- Recent
- Settings

[Main Header]
Collection Name | Upload | Ask

[Content]
-------------------------------------------------
| Documents tab | Ask tab | Diagnostics tab     |
-------------------------------------------------

Ask tab:
[Query Input..................................]
[Filters]

[Answer Card]
- Answer text
- Confidence / support status
- Citations

[Evidence Drawer]
- Source A, page 4
- Source B, section 2.1
```

## Clean UI without hiding reality
The UI can be simple as long as it still exposes:
- confidence
- status
- citations
- failures
- version state
