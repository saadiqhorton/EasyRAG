"""Unit tests for generator: _should_abstain, _determine_mode, _is_valid_uuid, GeneratedAnswer dataclass."""

import uuid

import pytest

from app.backend.services.evidence import EvidencePackage
from app.backend.services.generator import (
    ANSWERED_WITH_EVIDENCE,
    INSUFFICIENT_EVIDENCE,
    PARTIALLY_ANSWERED,
    GeneratedAnswer,
    _determine_mode,
    _is_valid_uuid,
    _should_abstain,
)
from app.backend.models.schemas import Citation, EvidenceItem


def _make_evidence(
    average_score=0.8,
    has_low_confidence=False,
    items=None,
):
    """Helper to build an EvidencePackage with controlled values."""
    if items is None:
        items = [
            EvidenceItem(
                chunk_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                document_title="Test Doc",
                text="Sample text",
                modality="text",
                confidence=0.95,
                citation_anchor="Test Doc - Page 1",
                ocr_used=False,
            )
        ]
    return EvidencePackage(
        items=items,
        citations=[],
        average_score=average_score,
        has_low_confidence=has_low_confidence,
    )


class TestShouldAbstain:
    """Tests for _should_abstain."""

    def test_abstain_when_score_below_threshold(self):
        """Arrange: evidence with average_score 0.2, threshold 0.3.
        Act: check _should_abstain.
        Assert: returns True.
        """
        evidence = _make_evidence(average_score=0.2)

        result = _should_abstain(evidence, score_threshold=0.3)

        assert result is True

    def test_no_abstain_when_score_at_threshold(self):
        """Arrange: evidence with average_score 0.3, threshold 0.3.
        Act: check _should_abstain.
        Assert: returns False (not strictly below).
        """
        evidence = _make_evidence(average_score=0.3)

        result = _should_abstain(evidence, score_threshold=0.3)

        assert result is False

    def test_no_abstain_when_score_above_threshold(self):
        """Arrange: evidence with average_score 0.5, threshold 0.3.
        Act: check _should_abstain.
        Assert: returns False.
        """
        evidence = _make_evidence(average_score=0.5)

        result = _should_abstain(evidence, score_threshold=0.3)

        assert result is False

    def test_abstain_when_all_low_confidence(self):
        """Arrange: all items have confidence < 0.5.
        Act: check _should_abstain.
        Assert: returns True.
        """
        items = [
            EvidenceItem(
                chunk_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                document_title="Doc",
                text="text",
                modality="ocr",
                confidence=0.3,
                citation_anchor="Doc (ocr)",
                ocr_used=True,
            ),
            EvidenceItem(
                chunk_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                document_title="Doc",
                text="text",
                modality="ocr",
                confidence=0.4,
                citation_anchor="Doc (ocr)",
                ocr_used=True,
            ),
        ]
        evidence = _make_evidence(average_score=0.8, items=items)

        result = _should_abstain(evidence, score_threshold=0.3)

        assert result is True

    def test_no_abstain_when_some_high_confidence(self):
        """Arrange: mixed confidence items, not all below 0.5.
        Act: check _should_abstain.
        Assert: returns False.
        """
        items = [
            EvidenceItem(
                chunk_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                document_title="Doc",
                text="text",
                modality="text",
                confidence=0.3,
                citation_anchor="Doc",
                ocr_used=False,
            ),
            EvidenceItem(
                chunk_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                document_title="Doc",
                text="text",
                modality="text",
                confidence=0.9,
                citation_anchor="Doc",
                ocr_used=False,
            ),
        ]
        evidence = _make_evidence(average_score=0.8, items=items)

        result = _should_abstain(evidence, score_threshold=0.3)

        assert result is False

    def test_no_abstain_with_empty_items(self):
        """Arrange: evidence with empty items list but score above threshold.
        Act: check _should_abstain.
        Assert: returns False (empty list does not trigger all_low_confidence).
        """
        evidence = _make_evidence(average_score=0.5, items=[])

        result = _should_abstain(evidence, score_threshold=0.3)

        assert result is False


class TestDetermineMode:
    """Tests for _determine_mode."""

    def test_insufficient_evidence_when_abstain(self):
        """Arrange: evidence with low score (triggers abstain).
        Act: determine mode.
        Assert: returns INSUFFICIENT_EVIDENCE.
        """
        evidence = _make_evidence(average_score=0.1)

        result = _determine_mode(evidence, score_threshold=0.3)

        assert result == INSUFFICIENT_EVIDENCE

    def test_partially_answered_when_low_confidence(self):
        """Arrange: evidence with has_low_confidence=True and score above threshold.
        Act: determine mode.
        Assert: returns PARTIALLY_ANSWERED.
        """
        evidence = _make_evidence(average_score=0.5, has_low_confidence=True)

        result = _determine_mode(evidence, score_threshold=0.3)

        assert result == PARTIALLY_ANSWERED

    def test_partially_answered_when_score_near_threshold(self):
        """Arrange: evidence score between threshold and 1.5 * threshold.
        Act: determine mode.
        Assert: returns PARTIALLY_ANSWERED.
        """
        # 1.5 * 0.3 = 0.45; score of 0.4 is below that
        evidence = _make_evidence(average_score=0.4, has_low_confidence=False)

        result = _determine_mode(evidence, score_threshold=0.3)

        assert result == PARTIALLY_ANSWERED

    def test_answered_with_evidence_when_strong(self):
        """Arrange: evidence with high score and no low confidence.
        Act: determine mode.
        Assert: returns ANSWERED_WITH_EVIDENCE.
        """
        # 1.5 * 0.3 = 0.45; score of 0.6 is above
        evidence = _make_evidence(average_score=0.6, has_low_confidence=False)

        result = _determine_mode(evidence, score_threshold=0.3)

        assert result == ANSWERED_WITH_EVIDENCE


class TestIsValidUuid:
    """Tests for _is_valid_uuid."""

    def test_valid_uuid_returns_true(self):
        """Arrange: a valid UUID string.
        Act: validate.
        Assert: True.
        """
        assert _is_valid_uuid(str(uuid.uuid4())) is True

    def test_invalid_string_returns_false(self):
        """Arrange: a non-UUID string.
        Act: validate.
        Assert: False.
        """
        assert _is_valid_uuid("not-a-uuid") is False

    def test_nil_uuid_returns_true(self):
        """Arrange: nil UUID string.
        Act: validate.
        Assert: True.
        """
        assert _is_valid_uuid("00000000-0000-0000-0000-000000000000") is True

    def test_none_returns_false(self):
        """Arrange: None value.
        Act: validate.
        Assert: False (AttributeError caught).
        """
        assert _is_valid_uuid(None) is False


class TestGeneratedAnswer:
    """Tests for GeneratedAnswer dataclass."""

    def test_creation(self):
        """Arrange: build all fields.
        Act: create GeneratedAnswer.
        Assert: all fields match.
        """
        citation = Citation(
            source_number=1,
            document_title="Doc",
            section_path="Intro",
            page_number=1,
            chunk_id=uuid.uuid4(),
        )
        answer = GeneratedAnswer(
            answer_text="Test answer",
            answer_mode=ANSWERED_WITH_EVIDENCE,
            citations=[citation],
            evidence_ids=["abc-123"],
            llm_model="test-model",
            reranker_used=True,
            latency_ms=150,
        )

        assert answer.answer_text == "Test answer"
        assert answer.answer_mode == ANSWERED_WITH_EVIDENCE
        assert len(answer.citations) == 1
        assert answer.evidence_ids == ["abc-123"]
        assert answer.llm_model == "test-model"
        assert answer.reranker_used is True
        assert answer.latency_ms == 150

    def test_raw_candidate_scores_default_none(self):
        """Arrange: create GeneratedAnswer without raw_candidate_scores.
        Act: inspect the field.
        Assert: defaults to None.
        """
        answer = GeneratedAnswer(
            answer_text="text",
            answer_mode=INSUFFICIENT_EVIDENCE,
            citations=[],
            evidence_ids=[],
            llm_model="model",
            reranker_used=False,
            latency_ms=50,
        )

        assert answer.raw_candidate_scores is None

    def test_raw_candidate_scores_set(self):
        """Arrange: create GeneratedAnswer with raw_candidate_scores.
        Act: inspect the field.
        Assert: values match.
        """
        scores = [{"chunk_id": "abc", "score": 0.9}]
        answer = GeneratedAnswer(
            answer_text="text",
            answer_mode=ANSWERED_WITH_EVIDENCE,
            citations=[],
            evidence_ids=[],
            llm_model="model",
            reranker_used=True,
            latency_ms=100,
            raw_candidate_scores=scores,
        )

        assert answer.raw_candidate_scores == scores