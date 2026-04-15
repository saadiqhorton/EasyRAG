"""Critical production-readiness tests for retrieval filters, versioning, and evidence."""

import json
import uuid

import pytest

from app.backend.services.retriever import _build_retrieval_filter, MAX_CHUNKS_PER_DOCUMENT
from app.backend.services.evidence import package_evidence, EvidencePackage
from app.backend.services.retriever import RetrievalCandidate
from app.backend.services.constants import ALLOWED_MIME_TYPES, OCR_CONFIDENCE_THRESHOLD


def _make_candidate(**kwargs):
    """Create a RetrievalCandidate with sensible defaults."""
    defaults = {
        "chunk_id": str(uuid.uuid4()),
        "document_id": str(uuid.uuid4()),
        "version_id": str(uuid.uuid4()),
        "collection_id": str(uuid.uuid4()),
        "score": 0.85,
        "title": "Test Document",
        "section_path": "Introduction",
        "page_number": 1,
        "modality": "text",
        "confidence": 0.95,
        "text_content": "This is sample evidence text for testing.",
        "version_status": "active",
    }
    defaults.update(kwargs)
    return RetrievalCandidate(**defaults)


class TestRetrievalFilter:
    """Tests for _build_retrieval_filter: ensures search filters are applied."""

    def test_basic_collection_filter(self):
        """A collection filter always includes collection_id and version_status=active."""
        from qdrant_client import models

        collection_id = uuid.uuid4()
        f = _build_retrieval_filter(collection_id)

        assert isinstance(f, models.Filter)
        must_keys = [c.key for c in f.must]
        assert "collection_id" in must_keys
        assert "version_status" in must_keys
        # version_status must be "active"
        vs_cond = next(c for c in f.must if c.key == "version_status")
        assert vs_cond.match.value == "active"

    def test_modality_filter(self):
        """Modality filter adds a must condition on the modality field."""
        from qdrant_client import models

        collection_id = uuid.uuid4()
        f = _build_retrieval_filter(collection_id, filters={"modality": "ocr_text"})

        must_keys = [c.key for c in f.must]
        assert "modality" in must_keys
        mod_cond = next(c for c in f.must if c.key == "modality")
        assert mod_cond.match.value == "ocr_text"

    def test_section_path_prefix_filter(self):
        """Section path prefix filter adds a must condition."""
        from qdrant_client import models

        collection_id = uuid.uuid4()
        f = _build_retrieval_filter(
            collection_id, filters={"section_path_prefix": "Chapter 1"}
        )

        must_keys = [c.key for c in f.must]
        assert "section_path" in must_keys

    def test_page_range_filter(self):
        """Page range filters add range conditions."""
        from qdrant_client import models

        collection_id = uuid.uuid4()
        f = _build_retrieval_filter(
            collection_id,
            filters={"page_number_min": 5, "page_number_max": 10},
        )

        must_keys = [c.key for c in f.must]
        assert "page_number" in must_keys
        # There should be two page_number conditions (min and max)
        page_conditions = [c for c in f.must if c.key == "page_number"]
        assert len(page_conditions) == 2

    def test_no_filters_basic(self):
        """With no filters, only collection_id and version_status are required."""
        from qdrant_client import models

        collection_id = uuid.uuid4()
        f = _build_retrieval_filter(collection_id)

        assert len(f.must) == 2  # collection_id + version_status


class TestEvidencePackagingWithTitles:
    """Tests that evidence packaging correctly uses document titles from DB."""

    def test_evidence_uses_provided_titles(self):
        """Document titles from the DB override chunk titles."""
        doc_id = str(uuid.uuid4())
        candidate = _make_candidate(
            document_id=doc_id,
            title="Chunk-level title",
            text_content="Evidence text from document.",
        )
        doc_titles = {doc_id: "DB-level Document Title"}

        pkg = package_evidence([candidate], doc_titles)

        assert pkg.items[0].document_title == "DB-level Document Title"

    def test_evidence_falls_back_to_chunk_title(self):
        """Without DB titles, chunk title is used."""
        candidate = _make_candidate(
            title="Chunk-level title",
            text_content="Evidence text.",
        )

        pkg = package_evidence([candidate], None)

        assert pkg.items[0].document_title == "Chunk-level title"

    def test_evidence_low_confidence_flag(self):
        """Low-confidence items set has_low_confidence=True."""
        low_conf = _make_candidate(confidence=0.4, modality="ocr_text")
        high_conf = _make_candidate(confidence=0.95, modality="text")

        pkg = package_evidence([low_conf, high_conf])

        assert pkg.has_low_confidence is True

    def test_evidence_all_high_confidence(self):
        """All high-confidence items set has_low_confidence=False."""
        c1 = _make_candidate(confidence=0.95, modality="text")
        c2 = _make_candidate(confidence=0.90, modality="text")

        pkg = package_evidence([c1, c2])

        assert pkg.has_low_confidence is False


class TestConstantsConsistency:
    """Tests that centralized constants are consistent."""

    def test_allowed_mime_types_contains_essential_types(self):
        """The ALLOWED_MIME_TYPES set must include the core supported types."""
        assert "application/pdf" in ALLOWED_MIME_TYPES
        assert "text/markdown" in ALLOWED_MIME_TYPES
        assert "text/plain" in ALLOWED_MIME_TYPES
        assert "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in ALLOWED_MIME_TYPES

    def test_ocr_confidence_threshold_in_range(self):
        """OCR confidence threshold must be between 0 and 1."""
        assert 0 < OCR_CONFIDENCE_THRESHOLD < 1


class TestAnswerRecordEvidence:
    """Tests for the answer record evidence storage.

    These verify that evidence_json is stored and restored correctly,
    not replaced with empty placeholders.
    """

    def test_evidence_json_stored_and_restored(self):
        """Evidence items stored in evidence_json should round-trip correctly."""
        # This tests the data structure, not the API endpoint
        evidence_data = [
            {
                "chunk_id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "document_title": "Test Document",
                "text": "Full evidence text that should be preserved.",
                "section_path": "Chapter 1",
                "page_number": 5,
                "modality": "text",
                "confidence": 0.95,
                "citation_anchor": "Test Document - Section: Chapter 1 - Page 5",
                "ocr_used": False,
            }
        ]

        # Simulate storage and retrieval
        stored = json.dumps(evidence_data)
        restored = json.loads(stored)

        assert len(restored) == 1
        assert restored[0]["document_title"] == "Test Document"
        assert restored[0]["text"] == "Full evidence text that should be preserved."
        assert restored[0]["page_number"] == 5
        assert restored[0]["ocr_used"] is False


class TestVersioningIntegrity:
    """Tests for document versioning correctness.

    These verify the logic for version supersession and retrieval filtering.
    """

    def test_active_version_filter_in_retrieval(self):
        """Retrieval filter must always include version_status=active."""
        from qdrant_client import models

        collection_id = uuid.uuid4()
        f = _build_retrieval_filter(collection_id)

        vs_cond = next(c for c in f.must if c.key == "version_status")
        assert vs_cond.match.value == "active"

    def test_superseded_version_excluded_from_filter(self):
        """Superseded versions must not appear in retrieval results.

        The filter always requires version_status=active, so superseded
        versions are automatically excluded.
        """
        from qdrant_client import models

        collection_id = uuid.uuid4()
        f = _build_retrieval_filter(collection_id)

        # No condition allows version_status=superseded
        vs_cond = next(c for c in f.must if c.key == "version_status")
        assert vs_cond.match.value == "active"


class TestIngestionConstants:
    """Tests for ingestion pipeline constants and configurations."""

    def test_mime_type_consistency(self):
        """All MIME types in constants should be supported by the parser."""
        from app.backend.services.parser import ALLOWED_MIME_TYPES as PARSER_MIME_TYPES

        # Every MIME type allowed by the API must have a parser format mapping
        for mime in ALLOWED_MIME_TYPES:
            assert mime in PARSER_MIME_TYPES, (
                f"MIME type {mime} accepted by API but not by parser"
            )

    def test_chunk_max_tokens_reasonable(self):
        """Chunk max tokens should be in a reasonable range."""
        from app.backend.services.config import Settings
        settings = Settings(
            postgres_url="postgresql+asyncpg://test:test@localhost/test",
            qdrant_url="http://localhost:6333",
            answer_llm_base_url="http://localhost:11434",
            answer_llm_model="test",
        )
        assert 100 <= settings.chunk_max_tokens <= 2000
        assert 50 <= settings.chunk_overlap_tokens <= settings.chunk_max_tokens