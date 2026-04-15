"""Tests for file content validation (magic byte signatures)."""

import pytest

from app.backend.services.file_validation import (
    MAGIC_SIGNATURES,
    TEXT_MIME_TYPES,
    _detect_actual_type,
    validate_file_signature,
)


class TestValidateFileSignature:
    """Tests for validate_file_signature."""

    # --- Empty content ---

    def test_empty_content_rejected(self):
        ok, reason = validate_file_signature(b"", "application/pdf")
        assert not ok
        assert "empty" in reason.lower()

    # --- PDF validation ---

    def test_pdf_valid_signature(self):
        content = b"%PDF-1.4 rest of document"
        ok, reason = validate_file_signature(content, "application/pdf")
        assert ok
        assert "application/pdf" in reason  # Reason includes MIME type name

    def test_pdf_spoofed_mime_actually_png(self):
        """A PNG uploaded with a PDF MIME type should be rejected."""
        png_header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        ok, reason = validate_file_signature(png_header, "application/pdf")
        assert not ok
        assert "PNG" in reason or "signature" in reason.lower()

    def test_pdf_spoofed_mime_actually_text(self):
        """Plain text uploaded as PDF should be rejected."""
        ok, reason = validate_file_signature(b"Hello world", "application/pdf")
        assert not ok

    # --- DOCX validation ---

    def test_docx_valid_signature(self):
        content = b"PK\x03\x04" + b"\x00" * 100
        ok, reason = validate_file_signature(content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        assert ok
        assert "signature" in reason.lower()

    def test_docx_spoofed_mime_actually_pdf(self):
        """A PDF uploaded with a DOCX MIME type should be rejected."""
        content = b"%PDF-1.4 rest of document"
        ok, reason = validate_file_signature(
            content,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        assert not ok
        assert "PDF" in reason or "signature" in reason.lower()

    # --- Text MIME types ---

    def test_markdown_valid_utf8(self):
        ok, reason = validate_file_signature(b"# Hello\n\nWorld", "text/markdown")
        assert ok

    def test_plain_text_valid_utf8(self):
        ok, reason = validate_file_signature(b"Just plain text", "text/plain")
        assert ok

    def test_html_valid_utf8(self):
        ok, reason = validate_file_signature(b"<html><body>Hello</body></html>", "text/html")
        assert ok

    def test_text_type_invalid_binary(self):
        """Binary content uploaded as text/markdown should be rejected."""
        binary = b"\x80\x81\x82\x83\x84"
        ok, reason = validate_file_signature(binary, "text/markdown")
        assert not ok
        assert "UTF-8" in reason or "binary" in reason.lower()

    def test_text_type_x_markdown(self):
        ok, reason = validate_file_signature(b"Hello", "text/x-markdown")
        assert ok

    # --- Unknown MIME type ---

    def test_unknown_mime_type_accepted(self):
        """Unknown MIME types are accepted without signature validation."""
        ok, reason = validate_file_signature(b"\xff\xfe\xfd", "application/x-unknown")
        assert ok
        assert "no signature" in reason.lower() or "not available" in reason.lower()

    # --- Edge cases ---

    def test_short_content_pdf(self):
        """Very short content that is still valid PDF."""
        ok, reason = validate_file_signature(b"%PDF", "application/pdf")
        assert ok

    def test_short_content_not_pdf(self):
        """Very short content that doesn't match PDF."""
        ok, reason = validate_file_signature(b"ABCD", "application/pdf")
        assert not ok


class TestDetectActualType:
    """Tests for _detect_actual_type."""

    def test_detect_pdf(self):
        assert "PDF" in _detect_actual_type(b"%PDF-1.4")

    def test_detect_zip(self):
        assert "ZIP" in _detect_actual_type(b"PK\x03\x04\x00")

    def test_detect_png(self):
        assert "PNG" in _detect_actual_type(b"\x89PNG\r\n\x1a\n\x00")

    def test_detect_jpeg(self):
        assert "JPEG" in _detect_actual_type(b"\xff\xd8\xff\xe0")

    def test_detect_gif(self):
        assert "GIF" in _detect_actual_type(b"GIF89a\x00")

    def test_detect_riff(self):
        assert "RIFF" in _detect_actual_type(b"RIFF\x00\x00\x00\x00AVI")

    def test_detect_xml(self):
        assert "XML" in _detect_actual_type(b"<?xml version=\"1.0\"?>")

    def test_detect_json(self):
        assert "JSON" in _detect_actual_type(b'{"key": "value"}')

    def test_detect_gzip(self):
        # GZIP detection checks 2-byte header: 0x1f 0x8b
        assert "GZIP" in _detect_actual_type(b"\x1f\x8b\x08\x00extra")

    def test_detect_text(self):
        assert "text" in _detect_actual_type(b"Hello world").lower()

    def test_detect_empty(self):
        assert "empty" in _detect_actual_type(b"").lower()

    def test_detect_unknown_binary(self):
        result = _detect_actual_type(b"\x00\x01\x02\xff")
        assert "unknown" in result.lower() or "binary" in result.lower()


class TestMimeCoverage:
    """Ensure all supported MIME types have validation coverage."""

    def test_all_binary_mimes_have_signatures(self):
        """Every MIME type in MAGIC_SIGNATURES should have at least one signature."""
        for mime, sigs in MAGIC_SIGNATURES.items():
            assert len(sigs) > 0, f"{mime} has no magic signatures"

    def test_text_mimes_are_valid_utf8_checkable(self):
        """Text MIME types should be checkable via UTF-8 decode."""
        for mime in TEXT_MIME_TYPES:
            assert mime not in MAGIC_SIGNATURES, (
                f"{mime} is in both TEXT_MIME_TYPES and MAGIC_SIGNATURES"
            )