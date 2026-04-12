"""Cross-encoder reranking adapter with graceful fallback."""

import logging
import time
from abc import ABC, abstractmethod

from .retriever import RetrievalCandidate

logger = logging.getLogger(__name__)

_reranker: CrossEncoderProvider | None = None


class RerankerProvider(ABC):
    """Abstract interface for reranker providers."""

    @abstractmethod
    def rerank(
        self, query: str, candidates: list[RetrievalCandidate], top_k: int = 5
    ) -> tuple[list[RetrievalCandidate], bool]:
        """Rerank candidates. Returns (reranked, reranker_used)."""
        ...


class CrossEncoderProvider(RerankerProvider):
    """Reranker using cross-encoder models from sentence-transformers."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2") -> None:
        self._model_name = model_name
        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(model_name)
            logger.info("reranker_loaded model=%s", model_name)
        except ImportError:
            logger.error("sentence-transformers not installed for reranker")
            raise
        except Exception as e:
            logger.error("reranker_load_failed model=%s error=%s", model_name, e)
            raise

    def rerank(
        self, query: str, candidates: list[RetrievalCandidate], top_k: int = 5
    ) -> tuple[list[RetrievalCandidate], bool]:
        """Rerank candidates using cross-encoder scoring."""
        if not candidates:
            return candidates, True

        start = time.time()
        try:
            pairs = [(query, c.text_content) for c in candidates]
            scores = self._model.predict(pairs)

            # Sort by score descending
            scored = list(zip(candidates, scores))
            scored.sort(key=lambda x: x[1], reverse=True)

            reranked = [c for c, _ in scored[:top_k]]
            elapsed = (time.time() - start) * 1000
            logger.info("reranked candidates=%d -> %d latency_ms=%.0f", len(candidates), top_k, elapsed)
            return reranked, True

        except Exception as e:
            logger.warning("reranker_failed, using original ranking: %s", e)
            return candidates[:top_k], False


def rerank_candidates(
    query: str,
    candidates: list[RetrievalCandidate],
    top_k: int = 5,
    model_name: str | None = None,
) -> tuple[list[RetrievalCandidate], bool]:
    """Rerank candidates with graceful fallback to original ranking.

    Args:
        query: The user query text.
        candidates: Retrieved candidates to rerank.
        top_k: Number of top candidates to return.
        model_name: Optional reranker model override.

    Returns:
        Tuple of (reranked candidates, whether reranker was used).
    """
    global _reranker
    try:
        from .config import get_settings
        settings = get_settings()
        name = model_name or settings.reranker_model_name

        if _reranker is None or _reranker._model_name != name:
            _reranker = CrossEncoderProvider(name)
        return _reranker.rerank(query, candidates, top_k)
    except Exception as e:
        logger.warning("reranker_unavailable, fallback: %s", e)
        return candidates[:top_k], False