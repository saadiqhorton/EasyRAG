# Changelog

All notable changes to EasyRAG are documented here.

## [0.2.0] - 2026-04-15

### Added
- **Multi-provider AI support** — EasyRAG now supports 5 AI providers:
  - **Ollama** (local, free, default)
  - **OpenAI** (GPT-4o, GPT-4o-mini, etc.)
  - **Anthropic** (Claude Sonnet, Claude Haiku)
  - **Google Gemini** (Gemini 2.0 Flash, Gemini 1.5 Pro)
  - **Custom OpenAI-compatible** (vLLM, LiteLLM, LocalAI, etc.)
- Provider selection during install with prompts tailored to each provider
- `LLM_PROVIDER` environment variable (default: `ollama`)
- `llm_provider.py` — Provider abstraction with adapters per API format
- `LLMProviderError` — Actionable error messages for auth, model, and connectivity issues
- Provider-specific checks in `doctor.sh` (validates API key requirements)
- Linux note in Ollama installer prompt about `host.docker.internal` vs `172.17.0.1`

### Changed
- `generator.py` now routes all LLM calls through the provider abstraction instead of direct httpx calls
- Error messages include the provider name for easier debugging
- `install.sh` shows configured provider on success screen
- `install.sh` shows existing provider on rerun
- `docker-compose.yml` passes `LLM_PROVIDER` env var with `ollama` default
- `.env.example` updated with provider reference table and `LLM_PROVIDER` field
- `VERSION` bumped to 0.2.0

### Fixed
- Error messages in Anthropic/Gemini providers now reference `ANSWER_LLM_API_KEY` (was `LLM_API_KEY`)
- Provider selection on rerun now preserves existing non-Ollama provider config
- Added Linux Ollama base URL note in installer

## [0.1.0] - 2026-04-15

### Added
- One-command installer (`install.sh`)
- Diagnostics script (`doctor.sh`)
- Uninstall script (`uninstall.sh`)
- Frontend Dockerfile for Next.js standalone build
- `.env.example` at repo root with minimal config
- `VERSION` file for release tracking
- User-facing README (one-command install at the top)
- `INSTALL.md` with per-provider setup docs
- `.gitignore` updated for safety (model caches, runtime data, secrets)

### Changed
- `next.config.ts` — added `output: "standalone"` for Docker builds
- `docker-compose.yml` — `POSTGRES_USER` defaults to `ragkb`
- README rewritten for new users (not dev setup)

### Provider verification note

All five providers (Ollama, OpenAI, Anthropic, Gemini, Custom) are implemented
with dedicated adapters following each provider's documented API format. Code-level
validation includes: factory tests, API key validation, error message mapping (401,
403, 404, 429), request payload structure verification, and URL construction tests.

Live API calls have not been tested from this build environment due to network
restrictions. The adapters should work correctly with real API keys. If you encounter
issues with a specific provider, please file an issue at:
https://github.com/saadiqhorton/EasyRAG/issues
