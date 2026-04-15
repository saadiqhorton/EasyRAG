"""Tests for Docling parser guards: timeout, file size, MIME type validation."""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.backend.services.parser import (
    ALLOWED_MIME_TYPES,
    MAX_PARSE_FILE_SIZE_MB,
    PARSE_TIMEOUT_SECONDS,
    ParseResult,
)


class TestParserConstants:
    """Tests for parser safety constants."""

    def test_parse_timeout_is_reasonable(self):
        """Timeout should be at least 30s and at most 600s."""
        assert PARSE_TIMEOUT_SECONDS >= 30
        assert PARSE_TIMEOUT_SECONDS <= 600

    def test_max_file_size_is_reasonable(self):
        """Max file size should be at least 10MB and at most 500MB."""
        assert MAX_PARSE_FILE_SIZE_MB >= 10
        assert MAX_PARSE_FILE_SIZE_MB <= 500

    def test_allowed_mime_types_covers_essentials(self):
        """Parser must support at minimum: PDF, DOCX, Markdown, plain text."""
        essential = {
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text/markdown",
            "text/plain",
        }
        assert essential.issubset(set(ALLOWED_MIME_TYPES.keys()))


class TestParserMimeTypeValidation:
    """Tests for MIME type rejection in parse_document."""

    @pytest.mark.asyncio
    async def test_unsupported_mime_raises_value_error(self):
        from app.backend.services.parser import parse_document

        with pytest.raises(ValueError, match="Unsupported MIME type"):
            await parse_document("/tmp/test.png", "image/png")

    @pytest.mark.asyncio
    async def test_application_octet_stream_rejected(self):
        from app.backend.services.parser import parse_document

        with pytest.raises(ValueError, match="Unsupported MIME type"):
            await parse_document("/tmp/test.bin", "application/octet-stream")


class TestParserFileSizeGuard:
    """Tests for file size limits in parse_document."""

    @pytest.mark.asyncio
    async def test_oversized_file_raises_value_error(self):
        """Files exceeding MAX_PARSE_FILE_SIZE_MB should be rejected."""
        from app.backend.services.parser import parse_document

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(b"%PDF-1.4 dummy")
            tmp_path = tmp.name

        try:
            mock_stat = MagicMock()
            mock_stat.st_size = (MAX_PARSE_FILE_SIZE_MB + 1) * 1024 * 1024

            with patch("app.backend.services.parser.Path") as mock_path_cls:
                mock_path = MagicMock()
                mock_path.stat.return_value = mock_stat
                mock_path_cls.return_value = mock_path

                with pytest.raises(ValueError, match="too large"):
                    await parse_document(tmp_path, "application/pdf")
        finally:
            os.unlink(tmp_path)


class TestParserTimeoutGuard:
    """Tests for parse timeout enforcement."""

    @pytest.mark.asyncio
    async def test_timeout_raises_runtime_error(self):
        """If parsing exceeds the timeout, a RuntimeError should be raised."""
        import asyncio
        from app.backend.services.parser import parse_document

        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as tmp:
            tmp.write(b"# Test document\nHello world")
            tmp_path = tmp.name

        try:
            with patch("app.backend.services.parser.asyncio.wait_for") as mock_wait_for:
                mock_wait_for.side_effect = asyncio.TimeoutError()

                with pytest.raises(RuntimeError, match="timed out"):
                    await parse_document(tmp_path, "text/markdown")
        finally:
            os.unlink(tmp_path)


class TestParseResult:
    """Tests for the ParseResult dataclass."""

    def test_default_values(self):
        result = ParseResult(title="Test", text_content="Hello")
        assert result.confidence == 1.0
        assert result.modality == "text"
        assert result.sections == []
        assert result.page_mapping == {}
        assert result.warnings == []
        assert result.page_count is None

    def test_ocr_result(self):
        result = ParseResult(
            title="Scanned",
            text_content="OCR text",
            confidence=0.7,
            modality="ocr_text",
        )
        assert result.modality == "ocr_text"
        assert result.confidence < 1.0