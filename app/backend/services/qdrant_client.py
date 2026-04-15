"""Qdrant async client initialization and collection setup."""

import logging

from qdrant_client import AsyncQdrantClient, models

from .config import QDRANT_COLLECTION_NAME, get_settings

logger = logging.getLogger(__name__)

# Named vectors: dense vector is "dense", sparse BM25 vector is "sparse"
DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"

_client: AsyncQdrantClient | None = None


async def get_qdrant_client() -> AsyncQdrantClient:
    """Return the shared async Qdrant client."""
    global _client
    if _client is None:
        settings = get_settings()
        kwargs: dict = {"url": settings.qdrant_url}
        if settings.qdrant_api_key:
            kwargs["api_key"] = settings.qdrant_api_key
        _client = AsyncQdrantClient(**kwargs)
    return _client


async def ensure_collection() -> None:
    """Create the Qdrant collection if it does not exist, with indexes.

    Creates the global ``rag_kb_chunks`` collection with named dense and
    sparse vectors, and payload indexes on collection_id, document_id,
    version_id, and version_status.
    """
    settings = get_settings()
    client = await get_qdrant_client()
    collections = await client.get_collections()
    names = [c.name for c in collections.collections]

    if QDRANT_COLLECTION_NAME not in names:
        await client.create_collection(
            collection_name=QDRANT_COLLECTION_NAME,
            vectors_config={
                DENSE_VECTOR_NAME: models.VectorParams(
                    size=settings.embedding_dimensions,
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
        logger.info("qdrant_collection_created name=%s", QDRANT_COLLECTION_NAME)

    # Create payload indexes for efficient filtering
    index_specs = [
        ("collection_id", models.PayloadSchemaType.KEYWORD),
        ("document_id", models.PayloadSchemaType.KEYWORD),
        ("version_id", models.PayloadSchemaType.KEYWORD),
        ("version_status", models.PayloadSchemaType.KEYWORD),
    ]
    for field_name, field_type in index_specs:
        try:
            await client.create_payload_index(
                collection_name=QDRANT_COLLECTION_NAME,
                field_name=field_name,
                field_schema=field_type,
            )
        except Exception:
            pass  # Index already exists

    logger.info("qdrant_collection_ready name=%s", QDRANT_COLLECTION_NAME)


async def close_qdrant() -> None:
    """Close the Qdrant client on shutdown."""
    global _client
    if _client is not None:
        await _client.close()
        _client = None
        logger.info("qdrant_client_closed")