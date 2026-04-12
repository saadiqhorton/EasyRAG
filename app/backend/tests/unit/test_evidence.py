"""Unit tests for package_evidence: citation building, average_score, low_confidence, ocr_used, empty candidates."""

import uuid

import pytest

from app.backend.services.evidence import (
    EvidencePackage,
    ServiceCitation,
    _build_citation_anchor,
    _is_valid_uuid,
    package_evidence,
)
from app.backend.services.retriever import RetrievalCandidate


def _make_candidate(
    score=0.8,
    confidence=0.95,
    modality="text",
    section_path="Intro",
    page_number=1,
    document_id=None,
    chunk_id=None,
    title="Test Doc",
    text_content="Sample content for testing.",
):
    """Helper to create a RetrievalCandidate with sensible defaults."""
    return RetrievalCandidate(
        chunk_id=chunk_id or str(uuid.uuid4()),
        document_id=document_id or str(uuid.uuid4()),
        version_id=str(uuid.uuid4()),
        collection_id=str(uuid.uuid4()),
        score=score,
        title=title,
        section_path=section_path,
        page_number=page_number,
        modality=modality,
        confidence=confidence,
        text_content=text_content,
        version_status="active",
    )


class TestPackageEvidenceEmpty:
    """Tests for package_evidence with empty input."""

    def test_empty_candidates_returns_empty_package(self):
        """Arrange: no candidates.
        Act: package evidence.
        Assert: returns empty items, citations, zero average, no low confidence.
        """
        result = package_evidence([])

        assert isinstance(result, EvidencePackage)
        assert result.items == []
        assert result.citations == []
        assert result.average_score == 0.0
        assert result.has_low_confidence is False


class TestPackageEvidenceCitations:
    """Tests for citation building."""

    def test_citations_created_for_each_candidate(self):
        """Arrange: two candidates.
        Act: package evidence.
        Assert: two citations are created with correct indices.
        """
        candidates = [_make_candidate(), _make_candidate()]

        result = package_evidence(candidates)

        assert len(result.citations) == 2
        assert result.citations[0].index == 1
        assert result.citations[1].index == 2

    def test_citation_snippet_truncated_at_200_chars(self):
        """Arrange: candidate with text longer than 200 chars.
        Act: package evidence.
        Assert: snippet is truncated and ends with '...'.
        """
        long_text = "x" * 300
        candidate = _make_candidate(text_content=long_text)

        result = package_evidence([candidate])

        assert len(result.citations[0].snippet) == 203  # 200 + "..."
        assert result.citations[0].snippet.endswith("...")

    def test_citation_snippet_short_text_unchanged(self):
        """Arrange: candidate with short text.
        Act: package evidence.
        Assert: snippet is the full text_content.
        """
        short_text = "Short text."
        candidate = _make_candidate(text_content=short_text)

        result = package_evidence([candidate])

        assert result.citations[0].snippet == short_text

    def test_citation_fields_populated(self):
        """Arrange: candidate with known fields.
        Act: package evidence.
        Assert: citation fields match candidate.
        """
        doc_id = str(uuid.uuid4())
        chunk_id = str(uuid.uuid4())
        candidate = _make_candidate(
            document_id=doc_id,
            chunk_id=chunk_id,
            section_path="Methods",
            page_number=42,
            title="Paper X",
        )

        result = package_evidence([candidate])

        citation = result.citations[0]
        assert citation.document_id == doc_id
        assert citation.chunk_id == chunk_id
        assert citation.section_path == "Methods"
        assert citation.page_number == 42
        assert citation.document_title == "Paper X"


class TestPackageEvidenceAverageScore:
    """Tests for average_score calculation."""

    def test_average_score_single_candidate(self):
        """Arrange: one candidate with score 0.8.
        Act: package evidence.
        Assert: average_score is 0.8.
        """
        candidate = _make_candidate(score=0.8)

        result = package_evidence([candidate])

        assert result.average_score == pytest.approx(0.8)

    def test_average_score_multiple_candidates(self):
        """Arrange: three candidates with scores 0.6, 0.8, 1.0.
        Act: package evidence.
        Assert: average_score is 0.8.
        """
        candidates = [
            _make_candidate(score=0.6),
            _make_candidate(score=0.8),
            _make_candidate(score=1.0),
        ]

        result = package_evidence(candidates)

        assert result.average_score == pytest.approx(0.8)


class TestPackageEvidenceLowConfidence:
    """Tests for low_confidence detection."""

    def test_low_confidence_when_below_threshold(self):
        """Arrange: candidate with confidence 0.6 (< 0.7).
        Act: package evidence.
        Assert: has_low_confidence is True.
        """
        candidate = _make_candidate(confidence=0.6)

        result = package_evidence([candidate])

        assert result.has_low_confidence is True

    def test_no_low_confidence_when_above_threshold(self):
        """Arrange: candidate with confidence 0.95 (>= 0.7).
        Act: package evidence.
        Assert: has_low_confidence is False.
        """
        candidate = _make_candidate(confidence=0.95)

        result = package_evidence([candidate])

        assert result.has_low_confidence is False

    def test_mixed_confidence_flags_low(self):
        """Arrange: one high and one low confidence candidate.
        Act: package evidence.
        Assert: has_low_confidence is True (any low triggers the flag).
        """
        candidates = [
            _make_candidate(confidence=0.95),
            _make_candidate(confidence=0.5),
        ]

        result = package_evidence(candidates)

        assert result.has_low_confidence is True


class TestPackageEvidenceOcrUsed:
    """Tests for ocr_used flag on EvidenceItem."""

    def test_ocr_used_when_modality_ocr(self):
        """Arrange: candidate with modality 'ocr'.
        Act: package evidence.
        Assert: evidence item has ocr_used=True.
        """
        candidate = _make_candidate(modality="ocr")

        result = package_evidence([candidate])

        assert result.items[0].ocr_used is True

    def test_ocr_not_used_when_modality_text(self):
        """Arrange: candidate with modality 'text'.
        Act: package evidence.
        Assert: evidence item has ocr_used=False.
        """
        candidate = _make_candidate(modality="text")

        result = package_evidence([candidate])

        assert result.items[0].ocr_used is False


class TestPackageEvidenceDocumentTitles:
    """Tests for document_titles mapping."""

    def test_custom_title_overrides_candidate_title(self):
        """Arrange: candidate with title 'Original' and a title mapping.
        Act: package evidence with document_titles={'doc_id': 'Custom Title'}.
        Assert: item and citation use the custom title.
        """
        doc_id = str(uuid.uuid4())
        candidate = _make_candidate(document_id=doc_id, title="Original")
        titles = {doc_id: "Custom Title"}

        result = package_evidence([candidate], document_titles=titles)

        assert result.items[0].document_title == "Custom Title"
        assert result.citations[0].document_title == "Custom Title"

    def test_fallback_to_candidate_title(self):
        """Arrange: candidate with title and no title mapping.
        Act: package evidence without document_titles.
        Assert: uses the candidate's own title.
        """
        candidate = _make_candidate(title="Fallback Title")

        result = package_evidence([candidate])

        assert result.items[0].document_title == "Fallback Title"


class TestBuildCitationAnchor:
    """Tests for _build_citation_anchor helper."""

    def test_basic_anchor(self):
        """Arrange: candidate with section and page.
        Act: build anchor.
        Assert: format is 'Title - Section: X - Page N'.
        """
        candidate = _make_candidate(section_path="Intro", page_number=3)
        result = _build_citation_anchor("My Doc", candidate)
        assert "My Doc" in result
        assert "Section: Intro" in result
        assert "Page 3" in result

    def test_anchor_without_section(self):
        """Arrange: candidate with no section_path.
        Act: build anchor.
        Assert: section part is omitted.
        """
        candidate = _make_candidate(section_path="", page_number=1)
        result = _build_citation_anchor("My Doc", candidate)
        assert "Section" not in result
        assert "Page 1" in result

    def test_anchor_with_ocr_modality(self):
        """Arrange: candidate with ocr modality.
        Act: build anchor.
        Assert: modality tag is included.
        """
        candidate = _make_candidate(modality="ocr", section_path="Results")
        result = _build_citation_anchor("My Doc", candidate)
        assert "(ocr)" in result

    def test_anchor_text_modality_omitted(self):
        """Arrange: candidate with text modality.
        Act: build anchor.
        Assert: modality tag is not included.
        """
        candidate = _make_candidate(modality="text")
        result = _build_citation_anchor("My Doc", candidate)
        assert "(text)" not in result


class TestIsValidUuid:
    """Tests for _is_valid_uuid helper."""

    def test_valid_uuid(self):
        """Arrange: a proper UUID string.
        Act: check validity.
        Assert: returns True.
        """
        assert _is_valid_uuid(str(uuid.uuid4())) is True

    def test_invalid_string(self):
        """Arrange: a non-UUID string.
        Act: check validity.
        Assert: returns False.
        """
        assert _is_valid_uuid("not-a-uuid") is False

    def test_empty_string(self):
        """Arrange: empty string.
        Act: check validity.
        Assert: returns False.
        """
        assert _is_valid_uuid("") is False