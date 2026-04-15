"""LLM provider abstraction for answer generation.

Supports multiple providers through a normalized interface:
- ollama: Local Ollama (OpenAI-compatible)
- openai: OpenAI API
- anthropic: Anthropic Claude API
- gemini: Google Gemini API
- openai_compatible: Any OpenAI-compatible endpoint

Each provider adapts the request/response format to the common
chat/completion interface used by the generator.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

import httpx

logger = logging.getLogger(__name__)


class LLMProviderType(str, Enum):
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OPENAI_COMPATIBLE = "openai_compatible"


@dataclass
class LLMResponse:
    """Normalized LLM response."""
    content: str
    model: str


class LLMProviderError(Exception):
    """Base error for LLM provider issues with actionable context."""

    def __init__(self, provider: str, message: str, status_code: int | None = None):
        self.provider = provider
        self.status_code = status_code
        super().__init__(f"[{provider}] {message}")


class BaseLLMProvider(ABC):
    """Abstract base for LLM providers."""

    def __init__(self, base_url: str, model: str, api_key: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> LLMResponse:
        """Generate a completion from the LLM."""
        ...

    def _describe_http_error(self, status_code: int, provider: str) -> str:
        """Return a human-readable description of common HTTP errors."""
        descriptions = {
            401: "Authentication failed. Check your API key (ANSWER_LLM_API_KEY).",
            403: "Access forbidden. Your API key may not have permission for this model.",
            404: f"Model '{self.model}' not found. Check that the model name is correct for {provider}.",
            429: "Rate limit exceeded. Wait a moment and try again.",
        }
        return descriptions.get(
            status_code,
            f"HTTP {status_code} error from {provider}. Check your configuration and try again.",
        )


class OpenAICompatibleProvider(BaseLLMProvider):
    """Provider for Ollama, OpenAI, and any OpenAI-compatible endpoint.

    All three provider types (ollama, openai, openai_compatible) use the
    same /chat/completions API format. The only differences are default
    base URLs and whether an API key is required.
    """

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> LLMResponse:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        url = f"{self.base_url}/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            message = self._describe_http_error(status, "OpenAI-compatible")
            raise LLMProviderError("openai-compatible", message, status) from e
        except httpx.ConnectError as e:
            raise LLMProviderError(
                "openai-compatible",
                f"Cannot connect to {self.base_url}. Is the server running?",
            ) from e
        except httpx.TimeoutException as e:
            raise LLMProviderError(
                "openai-compatible",
                f"Request to {self.base_url} timed out after 60s.",
            ) from e

        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        if not content.strip():
            raise LLMProviderError(
                "openai-compatible",
                f"Model '{self.model}' returned empty content. The model may not support system prompts or may be misconfigured.",
            )

        return LLMResponse(content=content, model=self.model)


class AnthropicProvider(BaseLLMProvider):
    """Provider for Anthropic Claude API.

    Uses the /v1/messages endpoint with the Anthropic message format.
    """

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> LLMResponse:
        if not self.api_key:
            raise LLMProviderError(
                "anthropic",
                "Anthropic requires an API key. Set ANSWER_LLM_API_KEY in your .env file.",
            )

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt},
            ],
        }

        url = f"{self.base_url}/v1/messages"

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            message = self._describe_http_error(status, "Anthropic")
            raise LLMProviderError("anthropic", message, status) from e
        except httpx.ConnectError as e:
            raise LLMProviderError(
                "anthropic",
                f"Cannot connect to {self.base_url}. Check ANSWER_LLM_BASE_URL.",
            ) from e
        except httpx.TimeoutException as e:
            raise LLMProviderError(
                "anthropic",
                f"Request to Anthropic timed out after 60s.",
            ) from e

        content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")

        if not content.strip():
            raise LLMProviderError(
                "anthropic",
                f"Model '{self.model}' returned empty content. The model may be misconfigured.",
            )

        return LLMResponse(content=content, model=data.get("model", self.model))


class GeminiProvider(BaseLLMProvider):
    """Provider for Google Gemini API.

    Uses the /v1beta/models/{model}:generateContent endpoint.
    """

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> LLMResponse:
        if not self.api_key:
            raise LLMProviderError(
                "gemini",
                "Gemini requires an API key. Set ANSWER_LLM_API_KEY in your .env file.",
            )

        headers = {"Content-Type": "application/json"}

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}],
                }
            ],
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            },
        }

        url = (
            f"{self.base_url}/v1beta/models/{self.model}"
            f":generateContent?key={self.api_key}"
        )

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            message = self._describe_http_error(status, "Gemini")
            raise LLMProviderError("gemini", message, status) from e
        except httpx.ConnectError as e:
            raise LLMProviderError(
                "gemini",
                f"Cannot connect to {self.base_url}. Check ANSWER_LLM_BASE_URL.",
            ) from e
        except httpx.TimeoutException as e:
            raise LLMProviderError(
                "gemini",
                f"Request to Gemini timed out after 60s.",
            ) from e

        content = ""
        for candidate in data.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                if "text" in part:
                    content += part["text"]

        if not content.strip():
            # Gemini may return safety blocks instead of content
            block_reason = None
            for candidate in data.get("candidates", []):
                if "finishReason" in candidate:
                    block_reason = candidate["finishReason"]
            if block_reason:
                raise LLMProviderError(
                    "gemini",
                    f"Model '{self.model}' did not generate content (finishReason: {block_reason}). "
                    f"This may be due to safety filters. Try rephrasing your query.",
                )
            raise LLMProviderError(
                "gemini",
                f"Model '{self.model}' returned empty content.",
            )

        return LLMResponse(content=content, model=self.model)


# ── Provider registry ──────────────────────────────────────────────

PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "ollama": {
        "base_url": "http://host.docker.internal:11434/v1",
        "model": "llama3.2",
        "requires_api_key": "false",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
        "requires_api_key": "true",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com",
        "model": "claude-sonnet-4-20250514",
        "requires_api_key": "true",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com",
        "model": "gemini-2.0-flash",
        "requires_api_key": "true",
    },
    "openai_compatible": {
        "base_url": "",
        "model": "",
        "requires_api_key": "false",
    },
}


def create_provider(
    provider_type: str,
    base_url: str,
    model: str,
    api_key: str | None = None,
) -> BaseLLMProvider:
    """Factory function to create the appropriate LLM provider.

    Args:
        provider_type: One of 'ollama', 'openai', 'anthropic', 'gemini',
                       'openai_compatible'.
        base_url: The base URL for the LLM API.
        model: The model name/identifier.
        api_key: Optional API key for providers that require one.

    Returns:
        An LLM provider instance.

    Raises:
        ValueError: If the provider type is unknown.
    """
    provider_map = {
        LLMProviderType.OLLAMA: OpenAICompatibleProvider,
        LLMProviderType.OPENAI: OpenAICompatibleProvider,
        LLMProviderType.OPENAI_COMPATIBLE: OpenAICompatibleProvider,
        LLMProviderType.ANTHROPIC: AnthropicProvider,
        LLMProviderType.GEMINI: GeminiProvider,
    }

    # Accept both enum values and string names
    normalized = provider_type.lower().replace("-", "_")
    try:
        provider_enum = LLMProviderType(normalized)
    except ValueError:
        valid = ", ".join(p.value for p in LLMProviderType)
        raise ValueError(
            f"Unknown LLM provider: '{provider_type}'. Valid providers: {valid}"
        ) from None

    provider_class = provider_map[provider_enum]
    return provider_class(base_url=base_url, model=model, api_key=api_key)
