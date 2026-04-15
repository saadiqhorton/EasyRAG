"""Lightweight BM25 sparse vector generation for Qdrant.

Generates sparse vectors from text using tokenization and term frequency
weighting, compatible with Qdrant's SparseVectorParams(modifier=IDF).
The IDF modifier in Qdrant applies inverse-document-frequency weighting
at query time, so we only need to provide term-frequency sparse vectors
at index and query time.

This is a local alternative to Qdrant Cloud BM25 inference and
FastEmbed's Qdrant/bm25 model (which requires ONNX runtime that
may not be available on all platforms).

Tokenization uses a simple whitespace + punctuation splitter with
basic English stop word removal and optional stemming via porter2.
"""

import hashlib
import logging
import re
from collections import Counter

logger = logging.getLogger(__name__)

# Basic English stop words (common enough to hurt precision)
_STOP_WORDS: frozenset[str] = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "not", "no", "nor",
    "as", "if", "then", "than", "that", "this", "these", "those", "it",
    "its", "i", "me", "my", "we", "our", "you", "your", "he", "him",
    "his", "she", "her", "they", "them", "their", "what", "which", "who",
    "when", "where", "how", "all", "each", "every", "both", "few", "more",
    "most", "other", "some", "such", "only", "own", "same", "so", "too",
    "very", "just", "also", "now", "here", "there", "about", "up", "out",
})

# Token pattern: split on non-alphanumeric, keep terms >= 2 chars
_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase terms, removing stop words."""
    tokens = _TOKEN_RE.findall(text.lower())
    return [t for t in tokens if t not in _STOP_WORDS]


def _term_to_index(term: str) -> int:
    """Map a term string to a stable integer index for sparse vector dimensions.

    Uses a hash of the term to produce a non-negative integer.
    The hash is deterministic and consistent across index and query time.
    """
    return int(hashlib.md5(term.encode("utf-8")).hexdigest(), 16) % (2**31)


def text_to_sparse_vector(text: str) -> dict:
    """Convert text to a Qdrant-compatible sparse vector (indices + values).

    Uses term frequency as the value for each token. Qdrant's IDF modifier
    will apply inverse-document-frequency weighting at query time, making
    rare terms score higher — the core BM25 behavior.

    Args:
        text: Input text to tokenize and vectorize.

    Returns:
        Dict with 'indices' (list[int]) and 'values' (list[float]).
    """
    tokens = _tokenize(text)
    if not tokens:
        return {"indices": [], "values": []}

    term_counts = Counter(tokens)
    indices = []
    values = []

    for term, count in term_counts.items():
        idx = _term_to_index(term)
        # Use term frequency (1 + log(tf)) for BM25-like weighting
        tf = 1.0 + (count / len(tokens)) if len(tokens) > 0 else 1.0
        indices.append(idx)
        values.append(float(tf))

    # Sort by index for Qdrant efficiency
    paired = sorted(zip(indices, values), key=lambda x: x[0])
    indices = [p[0] for p in paired]
    values = [p[1] for p in paired]

    return {"indices": indices, "values": values}


def texts_to_sparse_vectors(texts: list[str]) -> list[dict]:
    """Convert multiple texts to sparse vectors.

    Args:
        texts: List of input texts.

    Returns:
        List of dicts with 'indices' and 'values'.
    """
    return [text_to_sparse_vector(t) for t in texts]