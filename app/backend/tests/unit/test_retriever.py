"""Unit tests for deduplicate_candidates: dedup by key, max per document, empty input."""

import uuid

import pytest

from app.backend.services.retriever import (
    MAX_CHUNKS_PER_DOCUMENT,
    RetrievalCandidate,
    deduplicate_candidates,
)


def _make_candidate(
    document_id=None,
    section_path="Intro",
    page_number=1,
    score=0.8,
    chunk_id=None,
):
    """Helper to create a RetrievalCandidate with sensible defaults."""
    return RetrievalCandidate(
        chunk_id=chunk_id or str(uuid.uuid4()),
        document_id=document_id or str(uuid.uuid4()),
        version_id=str(uuid.uuid4()),
        collection_id=str(uuid.uuid4()),
        score=score,
        title="Test Doc",
        section_path=section_path,
        page_number=page_number,
        modality="text",
        confidence=0.95,
        text_content="Sample content.",
        version_status="active",
    )


class TestDeduplicateCandidatesEmpty:
    """Tests for deduplicate_candidates with empty input."""

    def test_empty_list_returns_empty(self):
        """Arrange: no candidates.
        Act: deduplicate.
        Assert: returns an empty list.
        """
        result = deduplicate_candidates([])

        assert result == []


class TestDeduplicateCandidatesByKey:
    """Tests for deduplication by document_id + section_path + page_number."""

    def test_removes_duplicates_same_key(self):
        """Arrange: two candidates with the same document_id, section_path, and page_number.
        Act: deduplicate.
        Assert: only the first candidate is kept.
        """
        doc_id = str(uuid.uuid4())
        c1 = _make_candidate(document_id=doc_id, section_path="Intro", page_number=1)
        c2 = _make_candidate(
            document_id=doc_id,
            section_path="Intro",
            page_number=1,
            chunk_id=str(uuid.uuid4()),
        )

        result = deduplicate_candidates([c1, c2])

        assert len(result) == 1
        assert result[0] is c1

    def test_different_page_number_not_deduplicated(self):
        """Arrange: two candidates with same document and section but different pages.
        Act: deduplicate.
        Assert: both are kept.
        """
        doc_id = str(uuid.uuid4())
        c1 = _make_candidate(document_id=doc_id, section_path="Intro", page_number=1)
        c2 = _make_candidate(
            document_id=doc_id,
            section_path="Intro",
            page_number=2,
            chunk_id=str(uuid.uuid4()),
        )

        result = deduplicate_candidates([c1, c2])

        assert len(result) == 2

    def test_different_section_not_deduplicated(self):
        """Arrange: two candidates from same document but different sections.
        Act: deduplicate.
        Assert: both are kept.
        """
        doc_id = str(uuid.uuid4())
        c1 = _make_candidate(document_id=doc_id, section_path="Intro")
        c2 = _make_candidate(
            document_id=doc_id,
            section_path="Methods",
            chunk_id=str(uuid.uuid4()),
        )

        result = deduplicate_candidates([c1, c2])

        assert len(result) == 2

    def test_different_document_not_deduplicated(self):
        """Arrange: two candidates from different documents with same section/page.
        Act: deduplicate.
        Assert: both are kept.
        """
        c1 = _make_candidate(document_id=str(uuid.uuid4()), section_path="Intro", page_number=1)
        c2 = _make_candidate(
            document_id=str(uuid.uuid4()),
            section_path="Intro",
            page_number=1,
            chunk_id=str(uuid.uuid4()),
        )

        result = deduplicate_candidates([c1, c2])

        assert len(result) == 2


class TestDeduplicateCandidatesMaxPerDocument:
    """Tests for the max per document limit."""

    def test_max_chunks_per_document_enforced(self):
        """Arrange: more than MAX_CHUNKS_PER_DOCUMENT candidates from the same document.
        Act: deduplicate.
        Assert: at most MAX_CHUNKS_PER_DOCUMENT are returned for that document.
        """
        doc_id = str(uuid.uuid4())
        candidates = []
        for i in range(MAX_CHUNKS_PER_DOCUMENT + 3):
            candidates.append(
                _make_candidate(
                    document_id=doc_id,
                    section_path=f"Section {i}",
                    page_number=i + 1,
                    chunk_id=str(uuid.uuid4()),
                )
            )

        result = deduplicate_candidates(candidates)

        doc_count = sum(1 for c in result if c.document_id == doc_id)
        assert doc_count == MAX_CHUNKS_PER_DOCUMENT

    def test_max_per_document_preserves_highest_scored(self):
        """Arrange: candidates from same document, some with lower scores before higher.
        Act: deduplicate.
        Assert: first MAX_CHUNKS_PER_DOCUMENT by input order are kept.
        """
        doc_id = str(uuid.uuid4())
        candidates = [
            _make_candidate(
                document_id=doc_id,
                section_path="S1",
                page_number=1,
                score=0.9,
            ),
            _make_candidate(
                document_id=doc_id,
                section_path="S2",
                page_number=2,
                score=0.7,
            ),
            _make_candidate(
                document_id=doc_id,
                section_path="S3",
                page_number=3,
                score=0.5,
            ),
            _make_candidate(
                document_id=doc_id,
                section_path="S4",
                page_number=4,
                score=0.99,
            ),
        ]

        result = deduplicate_candidates(candidates)

        # MAX_CHUNKS_PER_DOCUMENT is 3, so first 3 are kept
        assert len(result) == 3
        assert result[0].section_path == "S1"
        assert result[1].section_path == "S2"
        assert result[2].section_path == "S3"

    def test_mixed_documents_each_respected(self):
        """Arrange: candidates from two documents, each with more than MAX.
        Act: deduplicate.
        Assert: each document has at most MAX_CHUNKS_PER_DOCUMENT.
        """
        doc1 = str(uuid.uuid4())
        doc2 = str(uuid.uuid4())
        candidates = []
        for i in range(5):
            candidates.append(
                _make_candidate(
                    document_id=doc1,
                    section_path=f"S{i}",
                    page_number=i,
                    chunk_id=str(uuid.uuid4()),
                )
            )
            candidates.append(
                _make_candidate(
                    document_id=doc2,
                    section_path=f"S{i}",
                    page_number=i,
                    chunk_id=str(uuid.uuid4()),
                )
            )

        result = deduplicate_candidates(candidates)

        doc1_count = sum(1 for c in result if c.document_id == doc1)
        doc2_count = sum(1 for c in result if c.document_id == doc2)
        assert doc1_count == MAX_CHUNKS_PER_DOCUMENT
        assert doc2_count == MAX_CHUNKS_PER_DOCUMENT


class TestDeduplicateCandidatesOrder:
    """Tests that order is preserved for kept candidates."""

    def test_preserves_original_order(self):
        """Arrange: three unique candidates in specific order.
        Act: deduplicate.
        Assert: the returned order matches the input order.
        """
        doc_id = str(uuid.uuid4())
        c1 = _make_candidate(document_id=doc_id, section_path="A", page_number=1)
        c2 = _make_candidate(document_id=doc_id, section_path="B", page_number=2)
        c3 = _make_candidate(document_id=doc_id, section_path="C", page_number=3)

        result = deduplicate_candidates([c1, c2, c3])

        assert result == [c1, c2, c3]