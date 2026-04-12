"""Unit tests for Settings creation and get_settings caching."""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.backend.services.config import Settings, get_settings


def _env_dict(**overrides):
    """Build a minimal env dict with required vars; override as needed."""
    base = {
        "POSTGRES_URL": "postgresql+asyncpg://user:pass@localhost/test",
        "QDRANT_URL": "http://localhost:6333",
        "ANSWER_LLM_BASE_URL": "http://localhost:11434",
        "ANSWER_LLM_MODEL": "test-model",
    }
    base.update(overrides)
    return base


class TestSettingsCreation:
    """Tests for Settings model creation."""

    def test_settings_created_with_required_env(self):
        """Arrange: all required env vars set.
        Act: create Settings.
        Assert: settings instance has correct values.
        """
        env = _env_dict()
        with patch.dict(os.environ, env, clear=True):
            settings = Settings()

        assert settings.postgres_url == env["POSTGRES_URL"]
        assert settings.qdrant_url == env["QDRANT_URL"]
        assert settings.answer_llm_base_url == env["ANSWER_LLM_BASE_URL"]
        assert settings.answer_llm_model == env["ANSWER_LLM_MODEL"]

    def test_settings_missing_required_var_raises(self):
        """Arrange: missing a required env var (POSTGRES_URL).
        Act: create Settings.
        Assert: raises ValidationError.
        """
        env = _env_dict()
        del env["POSTGRES_URL"]
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValidationError):
                Settings()

    def test_settings_defaults_applied(self):
        """Arrange: required vars set, optional vars omitted.
        Act: create Settings.
        Assert: default values are applied.
        """
        env = _env_dict()
        with patch.dict(os.environ, env, clear=True):
            settings = Settings()

        assert settings.embedding_model_name == "sentence-transformers/all-MiniLM-L6-v2"
        assert settings.embedding_dimensions == 384
        assert settings.max_upload_size_mb == 50
        assert settings.storage_path == "/data/storage"
        assert settings.worker_poll_interval == 2.0
        assert settings.abstention_score_threshold == 0.3
        assert settings.ocr_confidence_threshold == 0.5
        assert settings.chunk_max_tokens == 500
        assert settings.chunk_overlap_tokens == 150

    def test_settings_optional_api_key_defaults_none(self):
        """Arrange: qdrant_api_key and answer_llm_api_key not set.
        Act: create Settings.
        Assert: those fields are None.
        """
        env = _env_dict()
        with patch.dict(os.environ, env, clear=True):
            settings = Settings()

        assert settings.qdrant_api_key is None
        assert settings.answer_llm_api_key is None

    def test_settings_overrides_defaults(self):
        """Arrange: set some optional env vars to non-default values.
        Act: create Settings.
        Assert: overrides take effect.
        """
        env = _env_dict(
            MAX_UPLOAD_SIZE_MB="100",
            STORAGE_PATH="/custom/storage",
            ABSTENTION_SCORE_THRESHOLD="0.5",
            CHUNK_MAX_TOKENS="1000",
        )
        with patch.dict(os.environ, env, clear=True):
            settings = Settings()

        assert settings.max_upload_size_mb == 100
        assert settings.storage_path == "/custom/storage"
        assert settings.abstention_score_threshold == 0.5
        assert settings.chunk_max_tokens == 1000

    def test_settings_extra_env_vars_ignored(self):
        """Arrange: an unexpected env var is present.
        Act: create Settings.
        Assert: no error (extra='ignore' in model_config).
        """
        env = _env_dict(UNKNOWN_VAR="should_be_ignored")
        with patch.dict(os.environ, env, clear=True):
            settings = Settings()  # Should not raise

        assert not hasattr(settings, "unknown_var")


class TestGetSettings:
    """Tests for get_settings caching behavior."""

    def test_get_settings_returns_settings(self):
        """Arrange: patch the module-level _settings to None and provide env.
        Act: call get_settings.
        Assert: returns a Settings instance.
        """
        import app.backend.services.config as config_mod

        original = config_mod._settings
        config_mod._settings = None
        try:
            env = _env_dict()
            with patch.dict(os.environ, env, clear=True):
                result = get_settings()
            assert isinstance(result, Settings)
        finally:
            config_mod._settings = original

    def test_get_settings_caches_instance(self):
        """Arrange: call get_settings twice.
        Act: compare the two results.
        Assert: they are the same object (cached).
        """
        import app.backend.services.config as config_mod

        original = config_mod._settings
        config_mod._settings = None
        try:
            env = _env_dict()
            with patch.dict(os.environ, env, clear=True):
                first = get_settings()
                second = get_settings()
            assert first is second
        finally:
            config_mod._settings = original

    def test_get_settings_creates_once(self):
        """Arrange: reset cached settings.
        Act: call get_settings.
        Assert: _settings is set after the call.
        """
        import app.backend.services.config as config_mod

        original = config_mod._settings
        config_mod._settings = None
        try:
            env = _env_dict()
            with patch.dict(os.environ, env, clear=True):
                get_settings()
            assert config_mod._settings is not None
        finally:
            config_mod._settings = original