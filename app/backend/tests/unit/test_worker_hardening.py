"""Tests for worker hardening: retry tracking, dead-letter logic, and failure handling."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.backend.models.ingestion_job import IngestionJob
from app.backend.models.schemas import IngestionJobResponse
from app.backend.workers.ingestion_worker import (
    MAX_RETRIES,
    STAGES,
    TERMINAL_STATES,
    _handle_job_failure,
)


class TestDeadLetterLogic:
    """Tests for the dead-letter state machine in the ingestion worker."""

    def test_terminal_states_includes_dead_letter(self):
        assert "dead_letter" in TERMINAL_STATES

    def test_max_retries_is_3(self):
        assert MAX_RETRIES == 3

    def test_stages_order(self):
        assert STAGES == ["parsing", "chunking", "embedding", "indexing"]


class TestHandleJobFailureLogic:
    """Tests for _handle_job_failure retry counting and state transitions."""

    @pytest.mark.asyncio
    async def test_first_failure_increments_retry_to_1(self):
        """A job with retry_count=0 should become retry_count=1 and status=failed."""
        job = IngestionJob(
            id=uuid.uuid4(),
            collection_id=uuid.uuid4(),
            version_id=uuid.uuid4(),
            status="parsing",
            retry_count=0,
        )

        session = AsyncMock()
        session.flush = AsyncMock()

        with patch("app.backend.workers.ingestion_worker._update_job_status", new_callable=AsyncMock) as mock_update, \
             patch("app.backend.workers.ingestion_worker._record_failure", new_callable=AsyncMock) as mock_record:
            await _handle_job_failure(
                session, job,
                stage_name="parsing",
                error_type="parse_failed",
                message="Test error",
                is_retryable=True,
            )

            assert job.retry_count == 1
            mock_record.assert_called_once()
            mock_update.assert_called_once()
            # Should be "failed" not "dead_letter" since retry_count(1) < MAX_RETRIES(3)
            # _update_job_status(session, job_id, status, current_stage)
            call_args = mock_update.call_args
            assert call_args[0][2] == "failed"  # status is 3rd positional arg

    @pytest.mark.asyncio
    async def test_non_retryable_goes_to_dead_letter(self):
        """A non-retryable failure should go to dead_letter immediately."""
        job = IngestionJob(
            id=uuid.uuid4(),
            collection_id=uuid.uuid4(),
            version_id=uuid.uuid4(),
            status="parsing",
            retry_count=0,
        )

        session = AsyncMock()

        with patch("app.backend.workers.ingestion_worker._update_job_status", new_callable=AsyncMock) as mock_update, \
             patch("app.backend.workers.ingestion_worker._record_failure", new_callable=AsyncMock):
            await _handle_job_failure(
                session, job,
                stage_name="parsing",
                error_type="version_not_found",
                message="Version not found",
                is_retryable=False,
            )

            call_args = mock_update.call_args
            assert call_args[0][2] == "dead_letter"

    @pytest.mark.asyncio
    async def test_retry_exhaustion_goes_to_dead_letter(self):
        """After MAX_RETRIES (3) attempts, the job should go to dead_letter."""
        job = IngestionJob(
            id=uuid.uuid4(),
            collection_id=uuid.uuid4(),
            version_id=uuid.uuid4(),
            status="embedding",
            retry_count=2,  # Already failed twice, this will be 3rd
        )

        session = AsyncMock()

        with patch("app.backend.workers.ingestion_worker._update_job_status", new_callable=AsyncMock) as mock_update, \
             patch("app.backend.workers.ingestion_worker._record_failure", new_callable=AsyncMock):
            await _handle_job_failure(
                session, job,
                stage_name="embedding",
                error_type="embedding_failed",
                message="Model unavailable",
                is_retryable=True,
            )

            assert job.retry_count == 3
            call_args = mock_update.call_args
            assert call_args[0][2] == "dead_letter"

    @pytest.mark.asyncio
    async def test_temp_file_cleanup_on_failure(self):
        """Temp files should be cleaned up even on failure."""
        import os
        import tempfile

        # Create a real temp file
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"test content")
            tmp_path = tmp.name

        assert os.path.exists(tmp_path)

        job = IngestionJob(
            id=uuid.uuid4(),
            collection_id=uuid.uuid4(),
            version_id=uuid.uuid4(),
            status="parsing",
            retry_count=0,
        )

        session = AsyncMock()

        with patch("app.backend.workers.ingestion_worker._update_job_status", new_callable=AsyncMock), \
             patch("app.backend.workers.ingestion_worker._record_failure", new_callable=AsyncMock):
            await _handle_job_failure(
                session, job,
                stage_name="parsing",
                error_type="parse_failed",
                message="Error",
                is_retryable=True,
                tmp_path=tmp_path,
            )

            assert not os.path.exists(tmp_path)

    @pytest.mark.asyncio
    async def test_nonexistent_temp_file_no_error(self):
        """If tmp_path doesn't exist, no error should be raised."""
        job = IngestionJob(
            id=uuid.uuid4(),
            collection_id=uuid.uuid4(),
            version_id=uuid.uuid4(),
            status="parsing",
            retry_count=0,
        )

        session = AsyncMock()

        with patch("app.backend.workers.ingestion_worker._update_job_status", new_callable=AsyncMock), \
             patch("app.backend.workers.ingestion_worker._record_failure", new_callable=AsyncMock):
            # Should not raise
            await _handle_job_failure(
                session, job,
                stage_name="parsing",
                error_type="parse_failed",
                message="Error",
                is_retryable=True,
                tmp_path="/nonexistent/path/tmpfile.pdf",
            )


class TestReindexRetryTracking:
    """Tests for the reindex endpoint's retry count carryover."""

    @pytest.mark.asyncio
    async def test_reindex_single_carries_retry_count(self):
        """Reindexing a document should carry over the previous retry_count."""
        from app.backend.api.ingestion import _reindex_single_document

        doc_id = uuid.uuid4()
        col_id = uuid.uuid4()
        ver_id = uuid.uuid4()

        mock_doc = MagicMock()
        mock_doc.id = doc_id

        mock_version = MagicMock()
        mock_version.id = ver_id
        mock_version.index_status = "failed"

        mock_last_job = MagicMock()
        mock_last_job.retry_count = 1

        session = AsyncMock()

        doc_result = MagicMock()
        doc_result.scalars.return_value.first.return_value = mock_doc
        ver_result = MagicMock()
        ver_result.scalars.return_value.first.return_value = mock_version
        job_result = MagicMock()
        job_result.scalars.return_value.first.return_value = mock_last_job

        session.execute = AsyncMock(side_effect=[doc_result, ver_result, job_result])

        result = await _reindex_single_document(session, col_id, doc_id)
        assert result == 1

        session.add.assert_called_once()
        new_job = session.add.call_args[0][0]
        assert new_job.retry_count == 1

    @pytest.mark.asyncio
    async def test_reindex_rejects_exhausted_retries(self):
        """Reindexing should reject documents that have already exceeded max retries."""
        from app.backend.api.ingestion import _reindex_single_document
        from fastapi import HTTPException

        doc_id = uuid.uuid4()
        col_id = uuid.uuid4()
        ver_id = uuid.uuid4()

        mock_doc = MagicMock()
        mock_doc.id = doc_id

        mock_version = MagicMock()
        mock_version.id = ver_id

        mock_last_job = MagicMock()
        mock_last_job.retry_count = 3

        session = AsyncMock()

        doc_result = MagicMock()
        doc_result.scalars.return_value.first.return_value = mock_doc
        ver_result = MagicMock()
        ver_result.scalars.return_value.first.return_value = mock_version
        job_result = MagicMock()
        job_result.scalars.return_value.first.return_value = mock_last_job

        session.execute = AsyncMock(side_effect=[doc_result, ver_result, job_result])

        with pytest.raises(HTTPException) as exc_info:
            await _reindex_single_document(session, col_id, doc_id)
        assert exc_info.value.status_code == 400


class TestIngestionJobResponseSchema:
    """Tests for IngestionJobResponse schema with retry_count."""

    def test_retry_count_in_response(self):
        resp = IngestionJobResponse(
            id=uuid.uuid4(),
            collection_id=uuid.uuid4(),
            version_id=uuid.uuid4(),
            status="failed",
            retry_count=2,
            created_at=datetime.now(UTC),
        )
        assert resp.retry_count == 2

    def test_retry_count_defaults_to_zero(self):
        resp = IngestionJobResponse(
            id=uuid.uuid4(),
            collection_id=uuid.uuid4(),
            version_id=uuid.uuid4(),
            status="queued",
            created_at=datetime.now(UTC),
        )
        assert resp.retry_count == 0

    def test_dead_letter_status_in_response(self):
        resp = IngestionJobResponse(
            id=uuid.uuid4(),
            collection_id=uuid.uuid4(),
            version_id=uuid.uuid4(),
            status="dead_letter",
            retry_count=3,
            created_at=datetime.now(UTC),
        )
        assert resp.status == "dead_letter"
        assert resp.retry_count == 3