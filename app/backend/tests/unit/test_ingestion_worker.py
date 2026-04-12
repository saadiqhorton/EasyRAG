"""Unit tests for ingestion_worker: _get_suffix, _guess_mime, STAGES order, TERMINAL_STATES."""

import pytest

from app.backend.workers.ingestion_worker import (
    STAGES,
    TERMINAL_STATES,
    _get_suffix,
    _guess_mime,
)


class TestGetSuffix:
    """Tests for _get_suffix."""

    def test_pdf_suffix(self):
        """Arrange: storage key ending with .pdf.
        Act: get suffix.
        Assert: returns '.pdf'.
        """
        result = _get_suffix("col1/doc1/ver1/report.pdf")
        assert result == ".pdf"

    def test_markdown_suffix(self):
        """Arrange: storage key ending with .md.
        Act: get suffix.
        Assert: returns '.md'.
        """
        result = _get_suffix("col1/doc1/ver1/readme.md")
        assert result == ".md"

    def test_docx_suffix(self):
        """Arrange: storage key ending with .docx.
        Act: get suffix.
        Assert: returns '.docx'.
        """
        result = _get_suffix("col1/doc1/ver1/document.docx")
        assert result == ".docx"

    def test_txt_suffix(self):
        """Arrange: storage key ending with .txt.
        Act: get suffix.
        Assert: returns '.txt'.
        """
        result = _get_suffix("col1/doc1/ver1/notes.txt")
        assert result == ".txt"

    def test_html_suffix(self):
        """Arrange: storage key ending with .html.
        Act: get suffix.
        Assert: returns '.html'.
        """
        result = _get_suffix("col1/doc1/ver1/page.html")
        assert result == ".html"

    def test_no_suffix(self):
        """Arrange: storage key with filename having no dot.
        Act: get suffix.
        Assert: returns empty string.
        """
        result = _get_suffix("col1/doc1/ver1/noextension")
        assert result == ""

    def test_multiple_dots(self):
        """Arrange: filename with multiple dots.
        Act: get suffix.
        Assert: returns the last dot-suffix.
        """
        result = _get_suffix("col1/doc1/ver1/archive.tar.gz")
        assert result == ".gz"

    def test_dot_at_start_of_filename(self):
        """Arrange: filename starting with a dot (hidden file).
        Act: get suffix.
        Assert: returns the dot-prefixed suffix.
        """
        result = _get_suffix("col1/doc1/ver1/.hidden")
        assert result == ".hidden"


class TestGuessMime:
    """Tests for _guess_mime."""

    def test_markdown(self):
        """Arrange: key ending in .md.
        Act: guess mime.
        Assert: returns 'text/markdown'.
        """
        assert _guess_mime("col/doc/ver/file.md") == "text/markdown"

    def test_pdf(self):
        """Arrange: key ending in .pdf.
        Act: guess mime.
        Assert: returns 'application/pdf'.
        """
        assert _guess_mime("col/doc/ver/file.pdf") == "application/pdf"

    def test_docx(self):
        """Arrange: key ending in .docx.
        Act: guess mime.
        Assert: returns the docx mime type.
        """
        expected = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert _guess_mime("col/doc/ver/file.docx") == expected

    def test_txt(self):
        """Arrange: key ending in .txt.
        Act: guess mime.
        Assert: returns 'text/plain'.
        """
        assert _guess_mime("col/doc/ver/file.txt") == "text/plain"

    def test_html(self):
        """Arrange: key ending in .html.
        Act: guess mime.
        Assert: returns 'text/html'.
        """
        assert _guess_mime("col/doc/ver/file.html") == "text/html"

    def test_unknown_suffix_defaults_to_text(self):
        """Arrange: key ending in .xyz (unknown).
        Act: guess mime.
        Assert: returns 'text/plain' as fallback.
        """
        assert _guess_mime("col/doc/ver/file.xyz") == "text/plain"

    def test_no_suffix_defaults_to_text(self):
        """Arrange: key with no extension.
        Act: guess mime.
        Assert: returns 'text/plain'.
        """
        assert _guess_mime("col/doc/ver/noext") == "text/plain"

    def test_case_insensitive(self):
        """Arrange: key with uppercase extension .PDF.
        Act: guess mime.
        Assert: returns 'application/pdf'.
        """
        assert _guess_mime("col/doc/ver/file.PDF") == "application/pdf"


class TestStages:
    """Tests for the STAGES constant."""

    def test_stages_order(self):
        """Arrange: STAGES list.
        Act: inspect.
        Assert: stages are in the correct pipeline order.
        """
        assert STAGES == ["parsing", "chunking", "embedding", "indexing"]

    def test_stages_length(self):
        """Arrange: STAGES list.
        Act: count.
        Assert: there are exactly 4 stages.
        """
        assert len(STAGES) == 4

    def test_first_stage_is_parsing(self):
        """Arrange: STAGES list.
        Act: get first element.
        Assert: it is 'parsing'.
        """
        assert STAGES[0] == "parsing"

    def test_last_stage_is_indexing(self):
        """Arrange: STAGES list.
        Act: get last element.
        Assert: it is 'indexing'.
        """
        assert STAGES[-1] == "indexing"


class TestTerminalStates:
    """Tests for the TERMINAL_STATES constant."""

    def test_terminal_states_contains_succeeded(self):
        """Arrange: TERMINAL_STATES set.
        Act: check membership.
        Assert: 'succeeded' is in the set.
        """
        assert "succeeded" in TERMINAL_STATES

    def test_terminal_states_contains_failed(self):
        """Arrange: TERMINAL_STATES set.
        Act: check membership.
        Assert: 'failed' is in the set.
        """
        assert "failed" in TERMINAL_STATES

    def test_terminal_states_excludes_intermediate(self):
        """Arrange: TERMINAL_STATES set.
        Act: check non-terminal stages.
        Assert: intermediate states are not terminal.
        """
        for stage in STAGES:
            assert stage not in TERMINAL_STATES

    def test_terminal_states_excludes_queued(self):
        """Arrange: TERMINAL_STATES set.
        Act: check 'queued'.
        Assert: 'queued' is not terminal.
        """
        assert "queued" not in TERMINAL_STATES