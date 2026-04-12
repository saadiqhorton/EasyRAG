"""Qdrant upsert/delete indexing service with version awareness."""

import logging
import uuid
from datetime import UTC, datetime

from qdrant_client import models

from .config import QDRANT_COLLECTION_NAME, get_settings
from .qdrant_client import get_qdrant_client

logger = logging.getLogger(__name__)

BATCH_SIZE = 100


def _build_payload(
    chunk_id: uuid.UUID,
    collection_id: uuid.UUID,
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    title: str | None,
    section_path: str | None,
    page_number: int | None,
    modality: str,
    confidence: float,
    version_status: str,
    text_content: str,
) -> dict:
    """Build the Qdrant point payload from chunk metadata."""
    return {
        "collection_id": str(collection_id),
        "document_id": str(document_id),
        "version_id": str(version_id),
        "chunk_id": str(chunk_id),
        "source_type": modality,
        "title": title or "",
        "section_path": section_path or "",
        "page_number": page_number,
        "modality": modality,
        "confidence": confidence,
        "created_at": int(datetime.now(UTC).timestamp()),
        "version_status": version_status,
        "text_content": text_content,
    }


async def upsert_chunks(
    chunks: list[dict],
    dense_vectors: list[list[float]],
) -> int:
    """Upsert chunk vectors into Qdrant with full payload.

    Args:
        chunks: List of chunk dicts with all metadata fields.
        dense_vectors: Dense embedding vectors for each chunk.

    Returns:
        Number of points upserted.
    """
    client = await get_qdrant_client()
    upserted = 0

    for i in range(0, len(chunks), BATCH_SIZE):
        batch_chunks = chunks[i : i + BATCH_SIZE]
        batch_vectors = dense_vectors[i : i + BATCH_SIZE]

        points = []
        for chunk, vector in zip(batch_chunks, batch_vectors):
            point_id = str(chunk["id"])
            payload = _build_payload(
                chunk_id=chunk["id"],
                collection_id=chunk["collection_id"],
                document_id=chunk["document_id"],
                version_id=chunk["version_id"],
                title=chunk.get("title"),
                section_path=chunk.get("section_path"),
                page_number=chunk.get("page_number_start"),
                modality=chunk.get("modality", "text"),
                confidence=chunk.get("confidence", 1.0),
                version_status="active",
                text_content=chunk["text_content"],
            )

            points.append(
                models.PointStruct(
                    id=point_id,
                    vector={"dense": vector},
                    payload=payload,
                )
            )

        if points:
            try:
                await client.upsert(
                    collection_name=QDRANT_COLLECTION_NAME,
                    points=points,
                )
                upserted += len(points)
            except Exception as e:
                logger.error("qdrant_upsert_failed batch=%d error=%s", i, e)
                raise

    logger.info("qdrant_upserted points=%d", upserted)
    return upserted


async def delete_version_points(version_id: uuid.UUID) -> int:
    """Delete all Qdrant points belonging to a document version.

    Args:
        version_id: UUID of the version to delete.

    Returns:
        Number of points deleted (approximate).
    """
    client = await get_qdrant_client()

    try:
        result = await client.delete(
            collection_name=QDRANT_COLLECTION_NAME,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="version_id",
                            match=models.MatchValue(value=str(version_id)),
                        )
                    ]
                )
            ),
        )
        logger.info("qdrant_version_deleted version=%s", version_id)
        return getattr(result, "deleted_count", 0) or 0
    except Exception as e:
        logger.error("qdrant_delete_failed version=%s error=%s", version_id, e)
        raise


async def mark_version_superseded(version_id: uuid.UUID) -> None:
    """Update version_status payload field to 'superseded' for old version points."""
    client = await get_qdrant_client()

    try:
        await client.set_payload(
            collection_name=QDRANT_COLLECTION_NAME,
            payload={"version_status": "superseded"},
            points=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="version_id",
                            match=models.MatchValue(value=str(version_id)),
                        )
                    ]
                )
            ),
        )
    except Exception as e:
        logger.warning(
            "qdrant_mark_superseded_failed version=%s error=%s", version_id, e
        )