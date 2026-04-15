"""Unit tests for LLM provider abstraction."""

import pytest

from app.backend.services.llm_provider import (
    AnthropicProvider,
    BaseLLMProvider,
    GeminiProvider,
    LLMProviderError,
    LLMProviderType,
    OpenAICompatibleProvider,
    PROVIDER_DEFAULTS,
    create_provider,
)


class TestCreateProvider:
    """Tests for the create_provider factory function."""

    def test_ollama_creates_openai_compatible(self):
        provider = create_provider("ollama", "http://localhost:11434/v1", "llama3.2")
        assert isinstance(provider, OpenAICompatibleProvider)
        assert provider.base_url == "http://localhost:11434/v1"
        assert provider.model == "llama3.2"
        assert provider.api_key is None

    def test_openai_creates_openai_compatible(self):
        provider = create_provider("openai", "https://api.openai.com/v1", "gpt-4o", "sk-test")
        assert isinstance(provider, OpenAICompatibleProvider)
        assert provider.api_key == "sk-test"

    def test_anthropic_creates_anthropic_provider(self):
        provider = create_provider("anthropic", "https://api.anthropic.com", "claude-sonnet-4-20250514", "sk-ant-test")
        assert isinstance(provider, AnthropicProvider)

    def test_gemini_creates_gemini_provider(self):
        provider = create_provider("gemini", "https://generativelanguage.googleapis.com", "gemini-2.0-flash", "AIza-test")
        assert isinstance(provider, GeminiProvider)

    def test_openai_compatible_creates_openai_compatible(self):
        provider = create_provider("openai_compatible", "http://localhost:8080/v1", "my-model")
        assert isinstance(provider, OpenAICompatibleProvider)

    def test_hyphenated_provider_name_works(self):
        """openai-compatible should normalize to openai_compatible."""
        provider = create_provider("openai-compatible", "http://test/v1", "model")
        assert isinstance(provider, OpenAICompatibleProvider)

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            create_provider("unknown", "http://test", "model")

    def test_all_provider_types_are_supported(self):
        for provider_type in LLMProviderType:
            provider = create_provider(provider_type.value, "http://test/v1", "model")
            assert isinstance(provider, BaseLLMProvider)


class TestProviderDefaults:
    """Tests for the PROVIDER_DEFAULTS registry."""

    def test_all_providers_have_defaults(self):
        for ptype in LLMProviderType:
            assert ptype.value in PROVIDER_DEFAULTS

    def test_ollama_defaults(self):
        d = PROVIDER_DEFAULTS["ollama"]
        assert d["base_url"] == "http://host.docker.internal:11434/v1"
        assert d["model"] == "llama3.2"
        assert d["requires_api_key"] == "false"

    def test_openai_defaults(self):
        d = PROVIDER_DEFAULTS["openai"]
        assert d["base_url"] == "https://api.openai.com/v1"
        assert d["model"] == "gpt-4o"
        assert d["requires_api_key"] == "true"

    def test_anthropic_defaults(self):
        d = PROVIDER_DEFAULTS["anthropic"]
        assert d["base_url"] == "https://api.anthropic.com"
        assert d["model"] == "claude-sonnet-4-20250514"
        assert d["requires_api_key"] == "true"

    def test_gemini_defaults(self):
        d = PROVIDER_DEFAULTS["gemini"]
        assert d["base_url"] == "https://generativelanguage.googleapis.com"
        assert d["model"] == "gemini-2.0-flash"
        assert d["requires_api_key"] == "true"


class TestProviderValidation:
    """Tests for provider validation (API key requirements, etc.)."""

    @pytest.mark.asyncio
    async def test_anthropic_requires_api_key(self):
        provider = AnthropicProvider(
            base_url="https://api.anthropic.com",
            model="claude-sonnet-4-20250514",
            api_key=None,
        )
        with pytest.raises(LLMProviderError, match="API key"):
            await provider.generate("system", "user")

    @pytest.mark.asyncio
    async def test_gemini_requires_api_key(self):
        provider = GeminiProvider(
            base_url="https://generativelanguage.googleapis.com",
            model="gemini-2.0-flash",
            api_key=None,
        )
        with pytest.raises(LLMProviderError, match="API key"):
            await provider.generate("system", "user")

    def test_llm_provider_error_message_format(self):
        err = LLMProviderError("anthropic", "Auth failed", 401)
        assert "[anthropic]" in str(err)
        assert "Auth failed" in str(err)
        assert err.provider == "anthropic"
        assert err.status_code == 401

    def test_describe_http_error_common_codes(self):
        provider = OpenAICompatibleProvider("http://test/v1", "test")
        assert "API key" in provider._describe_http_error(401, "test")
        assert "not found" in provider._describe_http_error(404, "test")
        assert "Rate limit" in provider._describe_http_error(429, "test")
        assert "403" in provider._describe_http_error(403, "test")
