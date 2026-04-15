# API Documentation

## Overview

This document describes all API endpoints for the RAG Knowledge Base. The API handles collections, documents, search, and answer generation.

**Base URL:** `http://localhost:8000/api/v1`

## Authentication

The API does not require authentication in Phase 1. All endpoints are open within the local network.

## Collections

### Create Collection - POST /collections

Creates a new knowledge collection to group related documents.

**Request**
```http
POST /api/v1/collections
Content-Type: application/json

{
  "name": "Project Documentation",
  "description": "All docs for the project"
}
```

**Request Parameters**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| name | string | yes | Collection name (1-255 chars) |
| description | string | no | Optional description |

**Response - Success (201)**
```json
{
  "id": "uuid",
  "name": "Project Documentation",
  "description": "All docs for the project",
  "created_at": "2026-04-12T10:00:00Z",
  "updated_at": "2026-04-12T10:00:00Z",
  "document_count": 0,
  "index_status_summary": {}
}
```

### List Collections - GET /collections

Returns all collections with document counts and status summaries.

**Request Parameters**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| skip | int | no | Number to skip (default 0) |
| limit | int | no | Max to return (default 20) |

### Get Collection - GET /collections/{collection_id}

Returns collection details with health summary and recent failures.

### Delete Collection - DELETE /collections/{collection_id}

Deletes a collection and all its documents. Also removes indexed data from the search engine.

## Documents

### Upload Document - POST /collections/{collection_id}/documents

Uploads a file to a collection. Creates a document record and starts indexing.

**Request:** Multipart form with a `file` field.

**Allowed file types:** Markdown, PDF, DOCX, plain text, HTML.

**Size limit:** Configurable via `MAX_UPLOAD_SIZE_MB` (default 50MB).

**Response - Success (201)**
```json
{
  "document_id": "uuid",
  "version_id": "uuid",
  "job_id": "uuid",
  "title": "report.pdf",
  "mime_type": "application/pdf",
  "file_size_bytes": 1024
}
```

### List Documents - GET /collections/{collection_id}/documents

Returns documents in a collection with their indexing status.

**Response**
```json
{
  "items": [
    {
      "id": "uuid",
      "title": "report.pdf",
      "mime_type": "application/pdf",
      "index_status": "indexed",
      "version_number": 1,
      "original_filename": "report.pdf",
      "updated_at": "2026-04-12T10:00:00Z",
      "parse_confidence": 0.95
    }
  ],
  "total": 1,
  "skip": 0,
  "limit": 50
}
```

### Replace Document - POST /documents/{document_id}/replace

Uploads a new version of a document. Old versions are kept but marked as superseded.

### Delete Document - DELETE /documents/{document_id}

Soft-deletes a document and removes its indexed data. Also cleans up all PostgreSQL chunks and derived assets for all versions of the document.

## Search and Ask

### Search - POST /collections/{collection_id}/search

Searches for relevant text chunks without generating an answer.

**Request**
```json
{
  "query": "How does authentication work?",
  "limit": 10,
  "filters": {
    "modality": "text",
    "section_path_prefix": "Chapter 1",
    "page_number_min": 1,
    "page_number_max": 20
  }
}
```

**Filter fields are now enforced:** The `modality`, `section_path_prefix`, `page_number_min`, and `page_number_max` filters are applied to the Qdrant query, narrowing retrieval results to matching chunks.

**Response**
```json
{
  "results": [
    {
      "chunk_id": "uuid",
      "score": 0.85,
      "text": "The authentication system checks...",
      "title": "Security Guide",
      "section_path": "Chapter 1/Security",
      "page_number": 5,
      "modality": "text",
      "confidence": 0.9,
      "document_id": "uuid",
      "version_id": "uuid",
      "collection_id": "uuid"
    }
  ]
}
```

### Ask - POST /collections/{collection_id}/ask

Asks a question and generates an answer with citations.

**Request**
```json
{
  "query": "How does authentication work?",
  "filters": {}
}
```

**Response**
```json
{
  "answer_id": "uuid",
  "answer_text": "The authentication system verifies users by checking...",
  "answer_mode": "answered_with_evidence",
  "citations": [
    {
      "source_number": 1,
      "document_title": "Security Guide",
      "section_path": "Chapter 1/Security",
      "page_number": 5,
      "chunk_id": "uuid"
    }
  ],
  "evidence": [
    {
      "chunk_id": "uuid",
      "text": "The authentication system checks...",
      "document_id": "uuid",
      "document_title": "Security Guide",
      "page_number": 5,
      "section_path": "Chapter 1/Security",
      "modality": "text",
      "confidence": 0.9,
      "ocr_used": false,
      "citation_anchor": "Security Guide - Chapter 1/Security - Page 5"
    }
  ]
}
```

### Answer Modes

| Mode | Meaning |
|------|---------|
| `answered_with_evidence` | Good evidence found, answer is reliable |
| `partially_answered_with_caveat` | Some evidence found but quality is low |
| `insufficient_evidence` | Not enough evidence to answer reliably |

## Ingestion

### Get Job Status - GET /ingestion-jobs/{job_id}

Returns the current status of a document processing job.

### Get Failures - GET /collections/{collection_id}/failures

Returns recent ingestion failures for a collection. Useful for debugging.

### Reindex - POST /collections/{collection_id}/reindex

Re-queues failed jobs for reprocessing.

## Health

### Health - GET /health

Returns service status. Used for liveness checks.

### Readiness - GET /health/ready

Returns service status plus database and search engine connectivity. Returns 503 if any dependency is down.

## Error Codes

| Status | Meaning | What to Do |
|--------|---------|------------|
| 400 | Bad request | Check your request body format |
| 404 | Not found | Check the ID is correct |
| 413 | File too large | Reduce file size below limit |
| 500 | Server error | Check server logs for details |
| 503 | Not ready | Wait for services to start up |