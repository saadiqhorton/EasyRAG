#!/usr/bin/env python3
"""Validate hybrid search (dense + BM25 sparse) against a real Qdrant instance.

Prerequisites:
  - Qdrant running at QDRANT_URL (default: http://localhost:6333)
  - sentence-transformers/all-MiniLM-L6-v2 model available (for dense vectors)

Usage:
  python scripts/validate_hybrid_search.py

Exit codes:
  0 - All checks passed
  1 - One or more checks failed
"""

import asyncio
import os
import sys
import uuid

# Add project root to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "app", "backend")
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "app"))

from qdrant_client import AsyncQdrantClient, models

# --- Configuration ---
COLLECTION_NAME = "validation_test_hybrid"
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"
DENSE_DIMENSIONS = 384  # all-MiniLM-L6-v2

# Test documents - realistic RAG-style content
TEST_DOCS = [
    "Machine learning models require large datasets for training and validation",
    "PostgreSQL supports advanced indexing including GIN and GiST for full-text search",
    "RAG systems combine information retrieval with generation for grounded answers",
    "Vector databases enable similarity search with embedding models and dense vectors",
    "Document chunking strategies affect retrieval quality significantly in RAG pipelines",
    "OCR technology extracts text from scanned PDF documents with varying confidence levels",
    "Cross-encoder reranking improves retrieval precision by scoring query-document pairs",
    "Hybrid search combining dense vectors and BM25 sparse vectors provides better recall",
    "Abstention logic prevents the system from answering when evidence is insufficient",
    "Version tracking ensures that only the latest document version is retrieved",
]

failures = []


def record(label: str, ok: bool, detail: str = ""):
    status = "OK" if ok else "FAIL"
    print(f"  {status} - {label}")
    if detail:
        print(f"         {detail}")
    if not ok:
        failures.append(label)


async def main():
    print("=" * 60)
    print("Hybrid Search Validation")
    print(f"Qdrant URL: {QDRANT_URL}")
    print("=" * 60)
    print()

    # 1. Connect to Qdrant
    print("[1/9] Connecting to Qdrant...")
    try:
        client = AsyncQdrantClient(url=QDRANT_URL)
        health = await client.get_collections()
        record("Qdrant connection", True, f"{len(health.collections)} existing collections")
    except Exception as e:
        record("Qdrant connection", False, str(e))
        return 1

    # 2. Create collection with named dense + sparse vectors
    print("[2/9] Creating collection with named dense + sparse vectors...")
    try:
        try:
            await client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass

        await client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config={
                DENSE_VECTOR_NAME: models.VectorParams(
                    size=DENSE_DIMENSIONS,
                    distance=models.Distance.COSINE,
                ),
            },
            sparse_vectors_config={
                SPARSE_VECTOR_NAME: models.SparseVectorParams(
                    index=models.SparseIndexParams(on_disk=False),
                    modifier=models.Modifier.IDF,
                ),
            },
        )
        record("Collection creation", True, f"'{COLLECTION_NAME}' with dense({DENSE_DIMENSIONS}) + sparse(IDF)")
    except Exception as e:
        record("Collection creation", False, str(e))
        return 1

    # 3. Verify collection schema
    print("[3/9] Verifying collection schema...")
    try:
        info = await client.get_collection(COLLECTION_NAME)
        has_dense = DENSE_VECTOR_NAME in (info.config.params.vectors or {})
        has_sparse = SPARSE_VECTOR_NAME in (info.config.params.sparse_vectors or {})
        record("Named dense vector", has_dense, f"'{DENSE_VECTOR_NAME}' found" if has_dense else "MISSING")
        record("Named sparse vector", has_sparse, f"'{SPARSE_VECTOR_NAME}' with IDF" if has_sparse else "MISSING")
    except Exception as e:
        record("Schema verification", False, str(e))

    # 4. Generate real dense embeddings
    print("[4/9] Generating real dense embeddings with sentence-transformers...")
    try:
        from services.embedder import embed_texts
        dense_vectors = embed_texts(TEST_DOCS)
        record("Dense embedding generation", len(dense_vectors) == len(TEST_DOCS),
               f"{len(dense_vectors)} vectors, dim={len(dense_vectors[0])}")
    except Exception as e:
        record("Dense embedding generation", False, str(e))
        return 1

    # 5. Generate BM25 sparse vectors
    print("[5/9] Generating BM25 sparse vectors...")
    try:
        from services.sparse_vector import texts_to_sparse_vectors
        sparse_vectors = texts_to_sparse_vectors(TEST_DOCS)
        non_empty = sum(1 for sv in sparse_vectors if sv["indices"])
        record("BM25 sparse vector generation", non_empty == len(TEST_DOCS),
               f"{non_empty}/{len(TEST_DOCS)} with non-empty vectors")
    except Exception as e:
        record("BM25 sparse vector generation", False, str(e))
        return 1

    # 6. Insert points with both dense + sparse vectors
    print("[6/9] Inserting points with dense + sparse vectors...")
    try:
        doc_ids = [str(uuid.uuid4()) for _ in TEST_DOCS]
        points = []
        for i, text in enumerate(TEST_DOCS):
            points.append(
                models.PointStruct(
                    id=doc_ids[i],
                    vector={
                        DENSE_VECTOR_NAME: dense_vectors[i],
                        SPARSE_VECTOR_NAME: models.SparseVector(
                            indices=sparse_vectors[i]["indices"],
                            values=sparse_vectors[i]["values"],
                        ),
                    },
                    payload={
                        "text_content": text,
                        "document_id": str(uuid.uuid4()),
                        "collection_id": "test-collection",
                        "version_id": str(uuid.uuid4()),
                        "chunk_id": str(uuid.uuid4()),
                        "modality": "text",
                        "confidence": 1.0,
                        "version_status": "active",
                        "title": f"Document {i+1}",
                        "section_path": "",
                        "page_number": None,
                    },
                )
            )

        await client.upsert(collection_name=COLLECTION_NAME, points=points)
        record("Point upsert with dense + sparse", True, f"{len(points)} points")
    except Exception as e:
        record("Point upsert", False, str(e))
        return 1

    # 7. Test dense-only search
    print("[7/9] Testing dense vector search...")
    try:
        query_text = "how does hybrid retrieval work"
        query_dense = embed_texts([query_text])[0]
        dense_results = await client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_dense,
            using=DENSE_VECTOR_NAME,
            limit=5,
            with_payload=True,
        )
        has_results = len(dense_results.points) > 0
        record("Dense search returns results", has_results,
               f"{len(dense_results.points)} results")
        if has_results:
            top = dense_results.points[0]
            print(f"         Top: score={top.score:.4f} | {top.payload['text_content'][:60]}...")
    except Exception as e:
        record("Dense search", False, str(e))

    # 8. Test BM25 sparse search
    print("[8/9] Testing BM25 sparse search...")
    try:
        from services.sparse_vector import text_to_sparse_vector
        query_sparse_raw = text_to_sparse_vector(query_text)
        query_sparse = models.SparseVector(
            indices=query_sparse_raw["indices"],
            values=query_sparse_raw["values"],
        )
        sparse_results = await client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_sparse,
            using=SPARSE_VECTOR_NAME,
            limit=5,
            with_payload=True,
        )
        has_results = len(sparse_results.points) > 0
        record("BM25 sparse search returns results", has_results,
               f"{len(sparse_results.points)} results")
        if has_results:
            top = sparse_results.points[0]
            print(f"         Top: score={top.score:.4f} | {top.payload['text_content'][:60]}...")
    except Exception as e:
        record("BM25 sparse search", False, str(e))

    # 9. Test hybrid RRF fusion search
    print("[9/9] Testing hybrid RRF fusion search...")
    try:
        fusion_results = await client.query_points(
            collection_name=COLLECTION_NAME,
            prefetch=[
                models.Prefetch(
                    query=query_dense,
                    using=DENSE_VECTOR_NAME,
                    limit=20,
                ),
                models.Prefetch(
                    query=query_sparse,
                    using=SPARSE_VECTOR_NAME,
                    limit=20,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=5,
            with_payload=True,
        )
        has_results = len(fusion_results.points) > 0
        record("Hybrid RRF fusion returns results", has_results,
               f"{len(fusion_results.points)} results")
        if has_results:
            top = fusion_results.points[0]
            print(f"         Top: score={top.score:.4f} | {top.payload['text_content'][:60]}...")

        # Verify metadata filter behavior
        filter_results = await client.query_points(
            collection_name=COLLECTION_NAME,
            prefetch=[
                models.Prefetch(
                    query=query_dense,
                    using=DENSE_VECTOR_NAME,
                    limit=20,
                    filter=models.Filter(must=[
                        models.FieldCondition(
                            key="version_status",
                            match=models.MatchValue(value="active"),
                        ),
                    ]),
                ),
                models.Prefetch(
                    query=query_sparse,
                    using=SPARSE_VECTOR_NAME,
                    limit=20,
                    filter=models.Filter(must=[
                        models.FieldCondition(
                            key="version_status",
                            match=models.MatchValue(value="active"),
                        ),
                    ]),
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=5,
            with_payload=True,
        )
        record("Metadata filter (version_status=active)", len(filter_results.points) > 0,
               f"{len(filter_results.points)} results with active filter")

        # Verify version_status filter excludes superseded
        # Mark one point as superseded
        await client.set_payload(
            collection_name=COLLECTION_NAME,
            payload={"version_status": "superseded"},
            points=models.PointIdsList(points=[doc_ids[0]]),
        )

        superseded_filter_results = await client.query_points(
            collection_name=COLLECTION_NAME,
            prefetch=[
                models.Prefetch(
                    query=query_dense,
                    using=DENSE_VECTOR_NAME,
                    limit=20,
                    filter=models.Filter(must=[
                        models.FieldCondition(
                            key="version_status",
                            match=models.MatchValue(value="active"),
                        ),
                    ]),
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=10,
            with_payload=True,
        )
        superseded_excluded = all(
            p.payload.get("version_status") != "superseded"
            for p in superseded_filter_results.points
        )
        record("Superseded version excluded from active filter", superseded_excluded,
               f"{len(superseded_filter_results.points)} results, no superseded")
    except Exception as e:
        record("Hybrid fusion / filter", False, str(e))

    # Cleanup
    print()
    print("Cleaning up test collection...")
    try:
        await client.delete_collection(COLLECTION_NAME)
        print(f"  Collection '{COLLECTION_NAME}' deleted")
    except Exception as e:
        print(f"  WARN - Could not delete: {e}")

    await client.close()

    # Summary
    print()
    print("=" * 60)
    if failures:
        print(f"FAILED - {len(failures)} check(s) failed:")
        for f in failures:
            print(f"  - {f}")
        print("=" * 60)
        return 1
    else:
        print("PASSED - All hybrid search checks passed")
        print("=" * 60)
        return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)