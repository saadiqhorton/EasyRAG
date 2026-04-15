"""Unit tests for LLM provider abstraction."""

import pytest

from app.backend.services.llm_provider import (
    AnthropicProvider,
    BaseLLMProvider,
    GeminiProvider,
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
        provider = create_provider("anthropic", "https://api.anthropic.com", "claude-sonnet-4-20250514", "sk-test")
        assert isinstance(provider, AnthropicProvider)

    def test_gemini_creates_gemini_provider(self):
        provider = create_provider("gemini", "https://generativelanguage.googleapis.com", "gemini-2.0-flash", "test-key")
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
        defaults = PROVIDER_DEFAULTS["ollama"]
        assert defaults["base_url"] == "http://host.docker.internal:11434/v1"
        assert defaults["model"] == "llama3.2"
        assert defaults["requires_api_key"] == "false"

    def test_openai_defaults(self):
        defaults = PROVIDER_DEFAULTS["openai"]
        assert defaults["base_url"] == "https://api.openai.com/v1"
        assert defaults["model"] == "gpt-4o"
        assert defaults["requires_api_key"] == "true"

    def test_anthropic_defaults(self):
        defaults = PROVIDER_DEFAULTS["anthropic"]
        assert defaults["base_url"] == "https://api.anthropic.com"
        assert defaults["model"] == "claude-sonnet-4-20250514"
        assert defaults["requires_api_key"] == "true"

    def test_gemini_defaults(self):
        defaults = PROVIDER_DEFAULTS["gemini"]
        assert defaults["base_url"] == "https://generativelanguage.googleapis.com"
        assert defaults["model"] == "gemini-2.0-flash"
        assert defaults["requires_api_key"] == "true"


class TestAnthropicProviderValidation:
    """Tests for Anthropic provider requiring API key."""

    @pytest.mark.asyncio
    async def test_anthropic_requires_api_key(self):
        provider = AnthropicProvider(
            base_url="https://api.anthropic.com",
            model="claude-sonnet-4-20250514",
            api_key=None,
        )
        with pytest.raises(ValueError, match="API key"):
            await provider.generate("system", "user")


class TestGeminiProviderValidation:
    """Tests for Gemini provider requiring API key."""

    @pytest.mark.asyncio
    async def test_gemini_requires_api_key(self):
        provider = GeminiProvider(
            base_url="https://generativelanguage.googleapis.com",
            model="gemini-2.0-flash",
            api_key=None,
        )
        with pytest.raises(ValueError, match="API key"):
            await provider.generate("system", "user")
