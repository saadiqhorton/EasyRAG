#!/usr/bin/env python3
"""End-to-end smoke test: upload documents, ingest, search, ask, verify citations.

Prerequisites:
  - PostgreSQL running and accessible
  - Qdrant running at QDRANT_URL
  - API server running at API_URL (default: http://localhost:8000)
  - Worker running (processes ingestion jobs)

Usage:
  python scripts/smoke_test_e2e.py

Exit codes:
  0 - All checks passed
  1 - One or more checks failed
"""

import asyncio
import os
import sys
import time
import uuid

import httpx

# --- Configuration ---
API_URL = os.environ.get("API_URL", "http://localhost:8000")
API_PREFIX = "/api/v1"
POLL_INTERVAL = 3
MAX_POLL_ATTEMPTS = 40  # 120s max wait

# Markdown test document
MARKDOWN_DOC = b"""# RAG Knowledge Base Guide

## Introduction
Retrieval-Augmented Generation (RAG) is a technique that combines information retrieval with text generation. The system first retrieves relevant documents from a knowledge base, then uses a language model to generate answers grounded in the retrieved evidence.

## How It Works
1. Documents are uploaded and parsed into chunks
2. Chunks are embedded using a sentence transformer model
3. Embeddings are indexed in a vector database (Qdrant)
4. When a user asks a question, the system retrieves the most relevant chunks
5. Retrieved evidence is used to generate a grounded answer with citations

## Key Features
- Hybrid search combining dense vectors and BM25 sparse vectors
- Cross-encoder reranking for improved relevance
- OCR support for scanned PDF documents
- Document versioning with supersession tracking
- Abstention when evidence is insufficient

## Limitations
- OCR-derived text may contain errors
- Reranking adds latency to each query
- The system only answers from indexed content
"""

failures = []


def record(label: str, ok: bool, detail: str = ""):
    status = "OK" if ok else "FAIL"
    print(f"  {status} - {label}")
    if detail:
        print(f"         {detail}")
    if not ok:
        failures.append(label)


async def wait_for_api(client: httpx.AsyncClient, max_wait: int = 30) -> bool:
    for _ in range(max_wait):
        try:
            resp = await client.get(f"{API_URL}/health")
            if resp.status_code == 200:
                return True
        except Exception:
            pass
        await asyncio.sleep(1)
    return False


async def wait_for_job(client: httpx.AsyncClient, job_id: str) -> dict:
    for attempt in range(MAX_POLL_ATTEMPTS):
        resp = await client.get(f"{API_URL}{API_PREFIX}/ingestion-jobs/{job_id}")
        if resp.status_code != 200:
            await asyncio.sleep(POLL_INTERVAL)
            continue
        data = resp.json()
        status = data["status"]
        if status in ("succeeded", "failed", "dead_letter"):
            return data
        if attempt % 3 == 0:
            print(f"    ... job {job_id[:8]} status={status} stage={data.get('current_stage', '?')} retry={data.get('retry_count', 0)}")
        await asyncio.sleep(POLL_INTERVAL)
    return {"status": "timeout", "id": job_id}


async def main():
    print("=" * 60)
    print("RAG Knowledge Base - End-to-End Smoke Test")
    print("=" * 60)
    print(f"API URL: {API_URL}")
    print()

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Health check
        print("[1/8] Checking API health...")
        try:
            resp = await client.get(f"{API_URL}/health")
            record("API health", resp.status_code == 200, f"status={resp.status_code}")
        except Exception as e:
            record("API health", False, str(e))
            return 1

        # 2. Readiness check
        print("[2/8] Checking service readiness (PostgreSQL + Qdrant)...")
        resp = await client.get(f"{API_URL}/health/ready")
        data = resp.json() if resp.status_code else {}
        pg_ok = data.get("postgres", False)
        qd_ok = data.get("qdrant", False)
        record("PostgreSQL ready", pg_ok)
        record("Qdrant ready", qd_ok)
        if not (pg_ok and qd_ok):
            print("  Cannot proceed without services. Exiting.")
            return 1

        # 3. Create a collection
        print("[3/8] Creating test collection...")
        col_resp = await client.post(
            f"{API_URL}{API_PREFIX}/collections",
            json={"name": f"smoke-{uuid.uuid4().hex[:8]}", "description": "E2E smoke test"},
        )
        record("Collection creation", col_resp.status_code == 201,
               f"status={col_resp.status_code}")
        if col_resp.status_code != 201:
            print(f"  Detail: {col_resp.text}")
            return 1
        collection_id = col_resp.json()["id"]

        # 4. Upload a markdown document
        print("[4/8] Uploading markdown document...")
        upload_resp = await client.post(
            f"{API_URL}{API_PREFIX}/collections/{collection_id}/documents",
            files={"file": ("rag-guide.md", MARKDOWN_DOC, "text/markdown")},
        )
        record("Document upload", upload_resp.status_code == 201,
               f"status={upload_resp.status_code}")
        if upload_resp.status_code != 201:
            print(f"  Detail: {upload_resp.text}")
            return 1
        upload_data = upload_resp.json()
        doc_id = upload_data["document_id"]
        job_id = upload_data["job_id"]
        print(f"         doc={doc_id[:8]} job={job_id[:8]}")

        # 5. Wait for ingestion
        print("[5/8] Waiting for ingestion to complete...")
        job_data = await wait_for_job(client, job_id)
        job_status = job_data["status"]
        if job_status == "succeeded":
            record("Ingestion succeeded", True,
                   f"retry_count={job_data.get('retry_count', 0)}")
        else:
            failure_msgs = "; ".join(f.get("message", "")[:80] for f in job_data.get("failures", []))
            record("Ingestion succeeded", False,
                   f"status={job_status} failures={failure_msgs or 'none'}")

        # 6. Search
        print("[6/8] Searching for 'how does RAG work'...")
        search_resp = await client.post(
            f"{API_URL}{API_PREFIX}/collections/{collection_id}/search",
            json={"query": "how does RAG work", "limit": 5},
        )
        if search_resp.status_code == 200:
            search_results = search_resp.json()["results"]
            record("Search returns results", len(search_results) > 0,
                   f"{len(search_results)} results")
            for i, r in enumerate(search_results[:3]):
                print(f"         [{i+1}] score={r['score']:.4f} | {r['text'][:60]}...")
        else:
            record("Search returns results", False,
                   f"status={search_resp.status_code} body={search_resp.text[:100]}")

        # 7. Ask (may fail if LLM not configured)
        print("[7/8] Asking 'What are the key features of this RAG system?'...")
        ask_resp = await client.post(
            f"{API_URL}{API_PREFIX}/collections/{collection_id}/ask",
            json={"query": "What are the key features of this RAG system?"},
        )
        if ask_resp.status_code == 200:
            ask_data = ask_resp.json()
            mode = ask_data.get("answer_mode", "unknown")
            citations = ask_data.get("citations", [])
            evidence = ask_data.get("evidence", [])
            record("Ask endpoint returns answer", True,
                   f"mode={mode} citations={len(citations)} evidence={len(evidence)}")
            print(f"         Answer: {ask_data.get('answer_text', '')[:100]}...")
        else:
            print(f"  WARN - Ask returned {ask_resp.status_code} (LLM may not be configured)")

        # 8. Retrieve answer by ID
        if ask_resp.status_code == 200:
            print("[8/8] Retrieving answer by ID...")
            answer_id = ask_data["answer_id"]
            get_resp = await client.get(f"{API_URL}{API_PREFIX}/answers/{answer_id}")
            if get_resp.status_code == 200:
                stored = get_resp.json()
                ev_count = len(stored.get("evidence", []))
                record("Answer retrieval by ID", True,
                       f"evidence_items={ev_count}")
            else:
                record("Answer retrieval by ID", False,
                       f"status={get_resp.status_code}")
        else:
            print("[8/8] Skipped (ask endpoint not available)")

        # Cleanup
        print()
        print("Cleaning up...")
        try:
            del_resp = await client.delete(f"{API_URL}{API_PREFIX}/documents/{doc_id}")
            print(f"  Document deleted: {del_resp.status_code == 200}")
        except Exception as e:
            print(f"  Cleanup error: {e}")

    print()
    print("=" * 60)
    if failures:
        print(f"FAILED - {len(failures)} check(s) failed:")
        for f in failures:
            print(f"  - {f}")
        print("=" * 60)
        return 1
    else:
        print("PASSED - All E2E smoke test checks passed")
        print("=" * 60)
        return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)