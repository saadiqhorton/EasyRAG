"""Query normalization and preprocessing service."""

import re
import uuid
from dataclasses import dataclass, field


@dataclass
class QueryContext:
    """Processed query ready for retrieval."""

    raw_query: str
    normalized_query: str
    collection_id: uuid.UUID
    filters: dict = field(default_factory=dict)


def normalize_query(query: str, collection_id: uuid.UUID) -> QueryContext:
    """Normalize a user query for retrieval.

    Applies: lowercase, whitespace normalization, removal of special chars
    that interfere with search, and basic filter extraction.

    Args:
        query: Raw user query string.
        collection_id: UUID of the collection to search.

    Returns:
        QueryContext with normalized query and filters.
    """
    raw = query.strip()
    normalized = raw.lower().strip()
    normalized = re.sub(r"\s+", " ", normalized)

    # Extract simple quoted phrases for exact matching
    exact_phrases = re.findall(r'"([^"]+)"', raw)
    filters = {}
    if exact_phrases:
        filters["exact_phrases"] = exact_phrases

    return QueryContext(
        raw_query=raw,
        normalized_query=normalized,
        collection_id=collection_id,
        filters=filters,
    )