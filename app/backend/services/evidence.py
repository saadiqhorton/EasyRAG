"""Evidence packaging service for answer generation."""

import logging
import uuid
from dataclasses import dataclass, field

from ..models.schemas import Citation, EvidenceItem
from .retriever import RetrievalCandidate

logger = logging.getLogger(__name__)


@dataclass
class ServiceCitation:
    """Internal citation reference linking to source evidence."""

    index: int
    document_id: str
    document_title: str
    chunk_id: str
    section_path: str | None
    page_number: int | None
    snippet: str


@dataclass
class EvidencePackage:
    """Complete evidence set for answer generation."""

    items: list[EvidenceItem] = field(default_factory=list)
    citations: list[ServiceCitation] = field(default_factory=list)
    average_score: float = 0.0
    has_low_confidence: bool = False


def package_evidence(
    candidates: list[RetrievalCandidate],
    document_titles: dict[str, str] | None = None,
) -> EvidencePackage:
    """Package retrieval results into evidence for answer generation.

    Builds citation objects with source references, estimates evidence
    quality, and flags low-confidence evidence (e.g. OCR-derived text).

    Args:
        candidates: Reranked retrieval candidates.
        document_titles: Optional mapping of document_id -> title.

    Returns:
        EvidencePackage ready for the generation service.
    """
    titles = document_titles or {}
    items: list[EvidenceItem] = []
    citations: list[ServiceCitation] = []
    scores = []
    has_low_confidence = False

    for i, candidate in enumerate(candidates):
        doc_title = titles.get(candidate.document_id, candidate.title)
        anchor = _build_citation_anchor(doc_title, candidate)

        item = EvidenceItem(
            chunk_id=uuid.UUID(candidate.chunk_id)
            if _is_valid_uuid(candidate.chunk_id)
            else uuid.uuid4(),
            document_id=uuid.UUID(candidate.document_id)
            if _is_valid_uuid(candidate.document_id)
            else uuid.uuid4(),
            document_title=doc_title,
            text=candidate.text_content,
            section_path=candidate.section_path or None,
            page_number=candidate.page_number,
            modality=candidate.modality,
            confidence=candidate.confidence,
            citation_anchor=anchor,
            ocr_used=candidate.modality == "ocr",
        )
        items.append(item)

        snippet = candidate.text_content[:200]
        if len(candidate.text_content) > 200:
            snippet += "..."

        citation = ServiceCitation(
            index=i + 1,
            document_id=candidate.document_id,
            document_title=doc_title,
            chunk_id=candidate.chunk_id,
            section_path=candidate.section_path,
            page_number=candidate.page_number,
            snippet=snippet,
        )
        citations.append(citation)

        scores.append(candidate.score)
        if candidate.confidence < 0.7:
            has_low_confidence = True

    avg_score = sum(scores) / len(scores) if scores else 0.0

    logger.info(
        "evidence_packaged items=%d avg_score=%.3f low_confidence=%s",
        len(items), avg_score, has_low_confidence,
    )

    return EvidencePackage(
        items=items,
        citations=citations,
        average_score=avg_score,
        has_low_confidence=has_low_confidence,
    )


def _build_citation_anchor(
    doc_title: str, candidate: RetrievalCandidate
) -> str:
    """Build a human-readable citation anchor string."""
    parts = [doc_title]
    if candidate.section_path:
        parts.append(f"Section: {candidate.section_path}")
    if candidate.page_number is not None:
        parts.append(f"Page {candidate.page_number}")
    if candidate.modality != "text":
        parts.append(f"({candidate.modality})")
    return " - ".join(parts)


def _is_valid_uuid(value: str) -> bool:
    """Check if a string is a valid UUID."""
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError):
        return False