"""Hybrid retrieval service using Qdrant RRF fusion of dense + BM25."""

import logging
import uuid
from dataclasses import dataclass

from qdrant_client import models

from .config import QDRANT_COLLECTION_NAME, get_settings
from .qdrant_client import get_qdrant_client
from .query_normalizer import QueryContext

logger = logging.getLogger(__name__)

# Max chunks from a single document in top-k results
MAX_CHUNKS_PER_DOCUMENT = 3


@dataclass
class RetrievalCandidate:
    """A single retrieved chunk with score and payload."""

    chunk_id: str
    document_id: str
    version_id: str
    collection_id: str
    score: float
    title: str
    section_path: str
    page_number: int | None
    modality: str
    confidence: float
    text_content: str
    version_status: str


async def hybrid_search(
    query: QueryContext,
    top_k: int = 20,
) -> list[RetrievalCandidate]:
    """Execute hybrid retrieval: dense semantic + BM25 lexical with RRF fusion.

    Args:
        query: Normalized query context.
        top_k: Number of candidates to return.

    Returns:
        List of retrieval candidates sorted by fused score.
    """
    settings = get_settings()
    client = await get_qdrant_client()

    # Build collection filter
    collection_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="collection_id",
                match=models.MatchValue(value=str(query.collection_id)),
            ),
            models.FieldCondition(
                key="version_status",
                match=models.MatchValue(value="active"),
            ),
        ]
    )

    try:
        from .embedder import embed_texts

        query_vector = embed_texts([query.normalized_query])[0]

        results = await client.query_points(
            collection_name=QDRANT_COLLECTION_NAME,
            prefetch=[
                models.Prefetch(
                    query=query_vector,
                    using="dense",
                    limit=top_k * 2,
                    filter=collection_filter,
                ),
                models.Prefetch(
                    query=query.normalized_query,
                    using="sparse",
                    limit=top_k * 2,
                    filter=collection_filter,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            query_filter=collection_filter,
            limit=top_k,
            with_payload=True,
        )
    except Exception as e:
        logger.error("hybrid_search_failed query=%s error=%s", query.raw_query, e)
        raise

    candidates = []
    for point in results.points:
        payload = point.payload or {}
        candidates.append(
            RetrievalCandidate(
                chunk_id=payload.get("chunk_id", ""),
                document_id=payload.get("document_id", ""),
                version_id=payload.get("version_id", ""),
                collection_id=payload.get("collection_id", ""),
                score=point.score or 0.0,
                title=payload.get("title", ""),
                section_path=payload.get("section_path", ""),
                page_number=payload.get("page_number"),
                modality=payload.get("modality", "text"),
                confidence=payload.get("confidence", 1.0),
                text_content=payload.get("text_content", ""),
                version_status=payload.get("version_status", "active"),
            )
        )

    logger.info(
        "hybrid_search query=%s candidates=%d",
        query.raw_query[:50], len(candidates),
    )
    return candidates


def deduplicate_candidates(
    candidates: list[RetrievalCandidate],
) -> list[RetrievalCandidate]:
    """Deduplicate and diversify retrieval results.

    - Remove near-identical chunks from the same section
    - Prefer active versions over inactive
    - Diversify across documents (max 3 per document)
    """
    seen_keys: set[str] = set()
    doc_counts: dict[str, int] = {}
    result: list[RetrievalCandidate] = []

    for candidate in candidates:
        dedupe_key = (
            f"{candidate.document_id}:{candidate.section_path}:"
            f"{candidate.page_number}"
        )
        if dedupe_key in seen_keys:
            continue

        doc_count = doc_counts.get(candidate.document_id, 0)
        if doc_count >= MAX_CHUNKS_PER_DOCUMENT:
            continue

        seen_keys.add(dedupe_key)
        doc_counts[candidate.document_id] = doc_count + 1
        result.append(candidate)

    logger.info(
        "deduplicated candidates=%d -> %d", len(candidates), len(result)
    )
    return result