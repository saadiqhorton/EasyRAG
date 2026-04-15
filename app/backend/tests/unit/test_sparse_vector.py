"""Tests for BM25 sparse vector generation."""

import pytest

from app.backend.services.sparse_vector import (
    _term_to_index,
    _tokenize,
    text_to_sparse_vector,
    texts_to_sparse_vectors,
)


class TestTokenize:
    """Tests for the _tokenize helper."""

    def test_basic_tokenization(self):
        tokens = _tokenize("Machine learning models")
        assert "machine" in tokens
        assert "learning" in tokens
        assert "models" in tokens

    def test_lowercase(self):
        tokens = _tokenize("UPPERCASE Text")
        assert "uppercase" in tokens
        assert "text" in tokens

    def test_stop_words_removed(self):
        tokens = _tokenize("the quick brown fox is in the box")
        assert "the" not in tokens
        assert "is" not in tokens
        assert "in" not in tokens
        assert "quick" in tokens
        assert "brown" in tokens

    def test_short_tokens_filtered(self):
        tokens = _tokenize("a I am ok")
        # Single-char tokens (< 2 chars) should be filtered
        assert "a" not in tokens
        assert "I" not in tokens
        # "am" is 2 chars and not a stop word
        assert "am" in tokens

    def test_punctuation_stripped(self):
        tokens = _tokenize("hello, world! test-case")
        assert "hello" in tokens
        assert "world" in tokens
        assert "test" in tokens
        assert "case" in tokens

    def test_empty_string(self):
        assert _tokenize("") == []

    def test_only_stop_words(self):
        assert _tokenize("the a an is are") == []


class TestTermToIndex:
    """Tests for the _term_to_index helper."""

    def test_deterministic(self):
        idx1 = _term_to_index("machine")
        idx2 = _term_to_index("machine")
        assert idx1 == idx2

    def test_different_terms_different_indices(self):
        idx1 = _term_to_index("machine")
        idx2 = _term_to_index("learning")
        assert idx1 != idx2

    def test_non_negative(self):
        idx = _term_to_index("anyterm")
        assert idx >= 0


class TestTextToSparseVector:
    """Tests for text_to_sparse_vector."""

    def test_basic_output(self):
        sv = text_to_sparse_vector("machine learning models")
        assert "indices" in sv
        assert "values" in sv
        assert len(sv["indices"]) > 0
        assert len(sv["indices"]) == len(sv["values"])

    def test_sorted_by_index(self):
        sv = text_to_sparse_vector("machine learning models training data")
        indices = sv["indices"]
        assert indices == sorted(indices)

    def test_empty_text(self):
        sv = text_to_sparse_vector("")
        assert sv["indices"] == []
        assert sv["values"] == []

    def test_duplicate_terms_counted(self):
        sv = text_to_sparse_vector("test test test")
        # "test" appears 3 times, should have 1 index entry with higher tf
        assert len(sv["indices"]) == 1
        assert sv["values"][0] > 1.0  # tf weighting > 1 for repeated terms

    def test_deterministic(self):
        sv1 = text_to_sparse_vector("machine learning models")
        sv2 = text_to_sparse_vector("machine learning models")
        assert sv1 == sv2

    def test_different_texts_different_vectors(self):
        sv1 = text_to_sparse_vector("machine learning")
        sv2 = text_to_sparse_vector("database query")
        assert sv1 != sv2

    def test_values_are_floats(self):
        sv = text_to_sparse_vector("test document")
        for v in sv["values"]:
            assert isinstance(v, float)


class TestTextsToSparseVectors:
    """Tests for texts_to_sparse_vectors."""

    def test_batch(self):
        texts = ["machine learning", "database query", ""]
        result = texts_to_sparse_vectors(texts)
        assert len(result) == 3
        assert len(result[0]["indices"]) > 0
        assert len(result[1]["indices"]) > 0
        assert len(result[2]["indices"]) == 0  # empty text

    def test_preserves_order(self):
        texts = ["alpha", "beta", "gamma"]
        result = texts_to_sparse_vectors(texts)
        # Each text should produce a different sparse vector
        assert result[0] != result[1] != result[2]