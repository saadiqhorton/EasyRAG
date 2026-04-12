"""Unit tests for schema validation: CollectionCreate, SearchRequest, AskRequest."""

import uuid

import pytest
from pydantic import ValidationError

from app.backend.models.schemas import (
    AskRequest,
    CollectionCreate,
    SearchFilters,
    SearchRequest,
)


class TestCollectionCreate:
    """Tests for CollectionCreate schema validation."""

    def test_valid_collection(self):
        """Arrange: name and optional description.
        Act: create CollectionCreate.
        Assert: fields match.
        """
        body = CollectionCreate(name="My Collection", description="A test collection")

        assert body.name == "My Collection"
        assert body.description == "A test collection"

    def test_name_required(self):
        """Arrange: omit the name field.
        Act: create CollectionCreate.
        Assert: raises ValidationError.
        """
        with pytest.raises(ValidationError):
            CollectionCreate()

    def test_name_empty_string_raises(self):
        """Arrange: name as empty string.
        Act: create CollectionCreate.
        Assert: raises ValidationError (min_length=1).
        """
        with pytest.raises(ValidationError):
            CollectionCreate(name="")

    def test_name_too_long_raises(self):
        """Arrange: name exceeding 255 characters.
        Act: create CollectionCreate.
        Assert: raises ValidationError (max_length=255).
        """
        with pytest.raises(ValidationError):
            CollectionCreate(name="x" * 256)

    def test_name_at_max_length(self):
        """Arrange: name of exactly 255 characters.
        Act: create CollectionCreate.
        Assert: succeeds.
        """
        body = CollectionCreate(name="x" * 255)
        assert len(body.name) == 255

    def test_description_optional(self):
        """Arrange: name only, no description.
        Act: create CollectionCreate.
        Assert: description is None.
        """
        body = CollectionCreate(name="Test")

        assert body.description is None

    def test_name_single_char(self):
        """Arrange: name of exactly 1 character.
        Act: create CollectionCreate.
        Assert: succeeds.
        """
        body = CollectionCreate(name="A")
        assert body.name == "A"


class TestSearchRequest:
    """Tests for SearchRequest schema validation."""

    def test_valid_search_request(self):
        """Arrange: query and default limit.
        Act: create SearchRequest.
        Assert: fields match.
        """
        req = SearchRequest(query="test query")

        assert req.query == "test query"
        assert req.limit == 10
        assert req.filters is None

    def test_query_required(self):
        """Arrange: omit query.
        Act: create SearchRequest.
        Assert: raises ValidationError.
        """
        with pytest.raises(ValidationError):
            SearchRequest()

    def test_query_empty_raises(self):
        """Arrange: query as empty string.
        Act: create SearchRequest.
        Assert: raises ValidationError (min_length=1).
        """
        with pytest.raises(ValidationError):
            SearchRequest(query="")

    def test_limit_below_minimum_raises(self):
        """Arrange: limit of 0.
        Act: create SearchRequest.
        Assert: raises ValidationError (ge=1).
        """
        with pytest.raises(ValidationError):
            SearchRequest(query="test", limit=0)

    def test_limit_above_maximum_raises(self):
        """Arrange: limit of 51.
        Act: create SearchRequest.
        Assert: raises ValidationError (le=50).
        """
        with pytest.raises(ValidationError):
            SearchRequest(query="test", limit=51)

    def test_limit_at_minimum(self):
        """Arrange: limit of 1.
        Act: create SearchRequest.
        Assert: succeeds.
        """
        req = SearchRequest(query="test", limit=1)
        assert req.limit == 1

    def test_limit_at_maximum(self):
        """Arrange: limit of 50.
        Act: create SearchRequest.
        Assert: succeeds.
        """
        req = SearchRequest(query="test", limit=50)
        assert req.limit == 50

    def test_with_filters(self):
        """Arrange: query with SearchFilters.
        Act: create SearchRequest.
        Assert: filters are set.
        """
        filters = SearchFilters(modality="ocr", page_number_min=1, page_number_max=10)
        req = SearchRequest(query="test", filters=filters)

        assert req.filters is not None
        assert req.filters.modality == "ocr"
        assert req.filters.page_number_min == 1
        assert req.filters.page_number_max == 10


class TestSearchFilters:
    """Tests for SearchFilters schema."""

    def test_empty_filters(self):
        """Arrange: no filter values.
        Act: create SearchFilters.
        Assert: all fields are None.
        """
        filters = SearchFilters()

        assert filters.modality is None
        assert filters.section_path_prefix is None
        assert filters.page_number_min is None
        assert filters.page_number_max is None

    def test_all_filters(self):
        """Arrange: all filter fields set.
        Act: create SearchFilters.
        Assert: all fields match.
        """
        filters = SearchFilters(
            modality="text",
            section_path_prefix="Chapter 1",
            page_number_min=5,
            page_number_max=20,
        )

        assert filters.modality == "text"
        assert filters.section_path_prefix == "Chapter 1"
        assert filters.page_number_min == 5
        assert filters.page_number_max == 20


class TestAskRequest:
    """Tests for AskRequest schema validation."""

    def test_valid_ask_request(self):
        """Arrange: query only.
        Act: create AskRequest.
        Assert: fields match.
        """
        req = AskRequest(query="What is RAG?")

        assert req.query == "What is RAG?"
        assert req.filters is None

    def test_query_required(self):
        """Arrange: omit query.
        Act: create AskRequest.
        Assert: raises ValidationError.
        """
        with pytest.raises(ValidationError):
            AskRequest()

    def test_query_empty_raises(self):
        """Arrange: empty query.
        Act: create AskRequest.
        Assert: raises ValidationError (min_length=1).
        """
        with pytest.raises(ValidationError):
            AskRequest(query="")

    def test_query_single_char(self):
        """Arrange: query of one character.
        Act: create AskRequest.
        Assert: succeeds.
        """
        req = AskRequest(query="X")
        assert req.query == "X"

    def test_with_filters(self):
        """Arrange: query with SearchFilters.
        Act: create AskRequest.
        Assert: filters are set.
        """
        filters = SearchFilters(modality="ocr")
        req = AskRequest(query="test", filters=filters)

        assert req.filters is not None
        assert req.filters.modality == "ocr"