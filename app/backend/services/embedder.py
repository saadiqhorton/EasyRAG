"""Model-agnostic embedding adapter with sentence-transformers default."""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """Abstract interface for embedding providers."""

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        ...

    @abstractmethod
    def get_dimension(self) -> int:
        """Return the embedding vector dimension."""
        ...

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the model identifier."""
        ...


class SentenceTransformerProvider(EmbeddingProvider):
    """Embedding provider using sentence-transformers library."""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        self._model_name = model_name
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(model_name)
        except ImportError:
            logger.error("sentence-transformers not installed")
            raise
        except Exception as e:
            logger.error("embedding_model_load_failed model=%s error=%s", model_name, e)
            raise

        self._dimension = self._model.get_embedding_dimension()
        logger.info("embedding_model_loaded name=%s dim=%d", model_name, self._dimension)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate dense embeddings for texts."""
        if not texts:
            return []
        embeddings: np.ndarray = self._model.encode(texts, batch_size=32, show_progress_bar=False)
        return embeddings.tolist()

    def get_dimension(self) -> int:
        """Return the embedding vector dimension."""
        return self._dimension

    def get_model_name(self) -> str:
        """Return the model identifier."""
        return self._model_name


# Module-level provider instance (lazy)
_provider: EmbeddingProvider | None = None


def get_embedding_provider(model_name: str | None = None) -> EmbeddingProvider:
    """Get or create the embedding provider singleton."""
    global _provider
    if _provider is None:
        from .config import get_settings
        settings = get_settings()
        name = model_name or settings.embedding_model_name
        _provider = SentenceTransformerProvider(name)
    return _provider


def embed_texts(texts: list[str], model_name: str | None = None) -> list[list[float]]:
    """Convenience function to embed texts using the default provider.

    This is a synchronous call that runs the embedding model.
    For use in async contexts, use embed_texts_async() instead.
    """
    provider = get_embedding_provider(model_name)
    return provider.embed_texts(texts)


async def embed_texts_async(texts: list[str], model_name: str | None = None) -> list[list[float]]:
    """Async wrapper for embed_texts that runs in a thread pool.

    Use this in async contexts (like the ingestion worker) to avoid
    blocking the event loop during embedding generation.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, embed_texts, texts, model_name)