# Ingestion Pipeline

## Objective
Convert raw source materials into a normalized, traceable representation suitable for chunking, indexing, and grounded retrieval.

## Pipeline stages

### 1. Source intake
Accept:
- file upload
- URL submission
- connector sync in later phases

Capture:
- source identity
- collection target
- uploader
- file hash
- mime type guess
- original filename

### 2. Type detection
Determine whether the source is:
- markdown/text
- PDF
- DOCX
- HTML
- image
- audio
- video

If detection is ambiguous, mark with warning and route through safest parser path.

### 3. Parsing and normalization
The parser should output a structured intermediate representation with preserved hierarchy.

Preferred normalized fields:
- document title
- sections and subsection tree
- paragraph blocks
- list items
- tables
- captions
- page mappings
- timestamps for media
- extracted text confidence
- embedded images references

### 4. OCR or transcription fallback
Use OCR for:
- scanned PDFs
- image-only pages
- screenshots
- image documents

Use transcription for:
- audio
- video audio track

Important:
- confidence must be attached to OCR or transcript-derived text
- low-confidence text must not be treated the same as clean text without visibility

### 5. Structural enrichment
Attach:
- heading path
- document outline
- section IDs
- page numbers
- speaker labels where available
- timestamps where available
- image references
- table references

### 6. Chunking
Chunk based on semantic and structural boundaries.

Recommended chunk rules:
- prefer section-aware chunking
- carry title and section path into each chunk
- preserve overlap where context continuation matters
- avoid splitting table rows or list logic across chunks when possible
- attach page/timestamp anchors

Suggested chunk metadata:
- chunk_id
- collection_id
- document_id
- version_id
- order_index
- title
- section_path
- page_number_start
- page_number_end
- timestamp_start
- timestamp_end
- modality
- confidence
- token_count

### 7. Embedding and indexing preparation
Prepare text for:
- dense embedding
- lexical indexing
- optional summary embedding or document embedding
- optional image embedding

### 8. Optional graph extraction
From selected chunks:
- extract entities
- extract relationships
- canonicalize aliases
- link edges back to chunk IDs

This stage must not be required for baseline indexing success.

### 9. Validation and status update
Mark indexing as:
- succeeded
- partially succeeded
- failed

Store detailed error messages, warnings, and derived artifacts.

## Format-specific guidance

### Markdown
Strengths:
- clean headings
- strong structural preservation

Risks:
- broken front matter
- code blocks misleading chunkers

### PDF
Strengths:
- common enterprise format

Risks:
- reading order problems
- multi-column confusion
- scanned pages
- tables and footnotes
- repeated headers and footers contaminating chunks

### DOCX
Strengths:
- richer semantic structure than PDF if parsed correctly

Risks:
- style-based heading inference failures
- comments/track changes noise
- embedded tables/images

### Images
Strengths:
- useful for screenshots and reference diagrams

Risks:
- OCR quality variance
- diagrams require more than OCR alone
- poor grounding if only alt-text-like descriptions are used

### Video
Strengths:
- can produce useful transcript knowledge

Risks:
- transcript alone misses visual evidence
- timestamps need to be preserved
- speaker diarization may be noisy

## Derived artifacts to store
- normalized markdown
- normalized JSON structure
- OCR text blocks
- transcript files
- extracted page images if needed
- keyframes for video if enabled

## Failure policy
A failed stage should emit:
- stage name
- error type
- human-readable message
- retryability flag
- suggested operator action

Examples:
- parse_failed
- ocr_failed
- transcript_failed
- chunk_validation_failed
- embedding_failed
- graph_extraction_failed

## Guardrails
- do not silently strip pages or sections
- do not merge unrelated sections into one chunk to reduce count
- do not treat OCR text as high confidence unless scored
- do not hide partial indexing behind a generic success state
