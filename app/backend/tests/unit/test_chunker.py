"""Unit tests for chunk_document: basic chunking, overlap, section boundaries, token estimation, empty input."""

import uuid

import pytest

from app.backend.services.chunker import (
    CHARS_PER_TOKEN,
    ChunkData,
    _add_overlap,
    _estimate_tokens,
    _split_at_boundary,
    chunk_document,
)


class TestEstimateTokens:
    """Tests for _estimate_tokens helper."""

    def test_short_text(self):
        """Arrange: text shorter than 4 chars.
        Act: estimate tokens.
        Assert: returns 1 (minimum).
        """
        result = _estimate_tokens("ab")
        assert result == 1

    def test_exact_multiple(self):
        """Arrange: text exactly 4 * 500 = 2000 chars.
        Act: estimate tokens.
        Assert: returns 500.
        """
        text = "a" * (CHARS_PER_TOKEN * 500)
        result = _estimate_tokens(text)
        assert result == 500

    def test_partial_token_rounds_down(self):
        """Arrange: text of 10 chars.
        Act: estimate tokens.
        Assert: returns 2 (10 // 4 = 2).
        """
        result = _estimate_tokens("a" * 10)
        assert result == 2

    def test_empty_string(self):
        """Arrange: empty string.
        Act: estimate tokens.
        Assert: returns 1 (max(1, 0)).
        """
        result = _estimate_tokens("")
        assert result == 1


class TestSplitAtBoundary:
    """Tests for _split_at_boundary."""

    def test_short_text_single_chunk(self):
        """Arrange: text well under max_tokens.
        Act: split at boundary.
        Assert: returns a single chunk.
        """
        text = "Short paragraph."
        result = _split_at_boundary(text, max_tokens=500)
        assert len(result) == 1
        assert result[0] == "Short paragraph."

    def test_splits_at_paragraphs(self):
        """Arrange: text with multiple paragraphs exceeding max_tokens.
        Act: split at boundary.
        Assert: splits into multiple chunks.
        """
        para = "Word " * 200  # ~1000 chars ~ 250 tokens
        text = f"{para}\n\n{para}\n\n{para}"
        result = _split_at_boundary(text, max_tokens=300)
        assert len(result) >= 2

    def test_skips_empty_paragraphs(self):
        """Arrange: text with empty paragraphs between content.
        Act: split at boundary.
        Assert: no empty strings in result.
        """
        text = "First.\n\n\n\nSecond."
        result = _split_at_boundary(text, max_tokens=500)
        assert all(chunk.strip() for chunk in result)

    def test_long_paragraph_splits_by_sentence(self):
        """Arrange: a single long paragraph with multiple sentences.
        Act: split at boundary with low max_tokens.
        Assert: splits into sentence-based chunks.
        """
        sentences = "This is sentence one. This is sentence two. This is sentence three. This is sentence four."
        result = _split_at_boundary(sentences, max_tokens=5)
        assert len(result) >= 2


class TestAddOverlap:
    """Tests for _add_overlap."""

    def test_single_chunk_no_overlap(self):
        """Arrange: a list with a single chunk.
        Act: add overlap.
        Assert: returns the same single chunk unchanged.
        """
        result = _add_overlap(["chunk one"], overlap_tokens=50)
        assert result == ["chunk one"]

    def test_overlap_prepended(self):
        """Arrange: two chunks with overlap.
        Act: add overlap.
        Assert: second chunk starts with the tail of the first chunk.
        """
        chunk1 = "a" * 1000
        chunk2 = "b" * 500
        result = _add_overlap([chunk1, chunk2], overlap_tokens=50)
        # overlap_chars = 50 * 4 = 200
        assert len(result) == 2
        assert result[1].startswith(chunk1[-200:])
        assert chunk2 in result[1]

    def test_zero_overlap(self):
        """Arrange: chunks with zero overlap.
        Act: add overlap.
        Assert: returns original chunks.
        """
        chunks = ["first", "second", "third"]
        result = _add_overlap(chunks, overlap_tokens=0)
        assert result == chunks

    def test_overlap_shorter_than_overlap_chars(self):
        """Arrange: first chunk is shorter than overlap_chars.
        Act: add overlap.
        Assert: entire first chunk is used as overlap.
        """
        chunk1 = "short"
        chunk2 = "second"
        result = _add_overlap([chunk1, chunk2], overlap_tokens=100)
        assert result[1].startswith("short")


class TestChunkDocument:
    """Tests for the main chunk_document function."""

    def _make_uuids(self):
        return uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    def test_basic_chunking_with_text_content(self):
        """Arrange: simple text content with no sections.
        Act: chunk_document.
        Assert: returns at least one ChunkData.
        """
        col_id, doc_id, ver_id = self._make_uuids()
        text = "This is a simple document with some text content."
        result = chunk_document(
            text_content=text,
            sections=[],
            page_mapping={},
            collection_id=col_id,
            document_id=doc_id,
            version_id=ver_id,
            confidence=1.0,
            modality="text",
        )
        assert len(result) >= 1
        assert all(isinstance(c, ChunkData) for c in result)

    def test_chunk_metadata_populated(self):
        """Arrange: simple text with known parameters.
        Act: chunk_document.
        Assert: metadata fields (collection_id, document_id, version_id, modality, confidence) are correct.
        """
        col_id, doc_id, ver_id = self._make_uuids()
        result = chunk_document(
            text_content="Hello world.",
            sections=[],
            page_mapping={},
            collection_id=col_id,
            document_id=doc_id,
            version_id=ver_id,
            confidence=0.95,
            modality="text",
            title="Test Doc",
        )
        chunk = result[0]
        assert chunk.collection_id == col_id
        assert chunk.document_id == doc_id
        assert chunk.version_id == ver_id
        assert chunk.modality == "text"
        assert chunk.confidence == 0.95
        assert chunk.title == "Test Doc"

    def test_section_aware_chunking(self):
        """Arrange: document with sections.
        Act: chunk_document.
        Assert: section_path is set on each chunk.
        """
        col_id, doc_id, ver_id = self._make_uuids()
        sections = [
            {"heading": "Introduction", "level": 1, "text": "Intro paragraph."},
            {"heading": "Methods", "level": 1, "text": "Methods paragraph."},
        ]
        result = chunk_document(
            text_content="",
            sections=sections,
            page_mapping={1: "Intro paragraph."},
            collection_id=col_id,
            document_id=doc_id,
            version_id=ver_id,
            confidence=1.0,
            modality="text",
        )
        assert len(result) == 2
        assert result[0].section_path == "Introduction"
        assert result[1].section_path == "Methods"

    def test_order_index_increments(self):
        """Arrange: enough text to produce multiple chunks.
        Act: chunk_document.
        Assert: order_index values start at 0 and increment.
        """
        col_id, doc_id, ver_id = self._make_uuids()
        text = "Word. " * 4000  # Long text
        result = chunk_document(
            text_content=text,
            sections=[],
            page_mapping={},
            collection_id=col_id,
            document_id=doc_id,
            version_id=ver_id,
            confidence=1.0,
            modality="text",
            max_tokens=100,
        )
        indices = [c.order_index for c in result]
        assert indices == list(range(len(result)))

    def test_empty_text_no_sections_returns_empty(self):
        """Arrange: empty text and empty sections.
        Act: chunk_document.
        Assert: returns an empty list.
        """
        col_id, doc_id, ver_id = self._make_uuids()
        result = chunk_document(
            text_content="",
            sections=[],
            page_mapping={},
            collection_id=col_id,
            document_id=doc_id,
            version_id=ver_id,
            confidence=1.0,
            modality="text",
        )
        assert result == []

    def test_page_mapping_sets_page_numbers(self):
        """Arrange: text content with a page mapping.
        Act: chunk_document.
        Assert: page_number_start/end are set from the mapping.
        """
        col_id, doc_id, ver_id = self._make_uuids()
        text = "Some text on page 5."
        result = chunk_document(
            text_content=text,
            sections=[],
            page_mapping={5: "Some text on page 5."},
            collection_id=col_id,
            document_id=doc_id,
            version_id=ver_id,
            confidence=1.0,
            modality="text",
        )
        assert len(result) >= 1
        chunk = result[0]
        assert chunk.page_number_start == 5
        assert chunk.page_number_end == 5

    def test_section_with_empty_text_skipped(self):
        """Arrange: section with empty text.
        Act: chunk_document.
        Assert: no chunk produced for that section.
        """
        col_id, doc_id, ver_id = self._make_uuids()
        sections = [
            {"heading": "Empty Section", "level": 1, "text": "   "},
            {"heading": "Has Content", "level": 1, "text": "Some real content here."},
        ]
        result = chunk_document(
            text_content="",
            sections=sections,
            page_mapping={},
            collection_id=col_id,
            document_id=doc_id,
            version_id=ver_id,
            confidence=1.0,
            modality="text",
        )
        assert len(result) == 1
        assert result[0].section_path == "Has Content"

    def test_token_count_estimated(self):
        """Arrange: chunk a document.
        Act: inspect token_count.
        Assert: token_count is >= 1 for each chunk.
        """
        col_id, doc_id, ver_id = self._make_uuids()
        result = chunk_document(
            text_content="A reasonable amount of text for a chunk.",
            sections=[],
            page_mapping={},
            collection_id=col_id,
            document_id=doc_id,
            version_id=ver_id,
            confidence=1.0,
            modality="text",
        )
        for chunk in result:
            assert chunk.token_count >= 1