# Changelog

## [0.3.0] - 2026-04-15

### Added
- **No-Docker default install** — EasyRAG now runs without Docker as the primary path
- `install.sh` rewritten — downloads Qdrant binary, creates Python venv, builds frontend
- `start.sh` — starts Qdrant, API, worker, and frontend as local processes
- `stop.sh` — gracefully stops all services
- SQLite support — replaces PostgreSQL for local installs (no DB server needed)
- `DATABASE_URL` config — supports both `sqlite+aiosqlite://` and `postgresql+asyncpg://`
- `aiosqlite` moved to main dependencies (was dev-only)
- `effective_database_url` property in Settings for backward compatibility

### Changed
- **Default install is now no-Docker** — Docker remains as fallback/advanced option
- `README.md` — quick start shows one-command install + start.sh
- `INSTALL.md` — restructured with no-Docker as primary, Docker as alternative
- `config.py` — supports DATABASE_URL with fallback to POSTGRES_URL
- `database.py` — handles SQLite (no connection pooling) vs PostgreSQL
- `alembic/env.py` — uses effective_database_url
- `.env.example` — SQLite as default, clearer comments
- `VERSION` bumped to 0.3.0

### Fixed
- Database adapter now correctly handles both SQLite and PostgreSQL backends

## [0.2.0] - 2026-04-15

### Added
- **Multi-provider AI support** — Ollama, OpenAI, Anthropic, Gemini, Custom
- Provider selection during install with prompts per provider
- Provider abstraction layer (`llm_provider.py`) with adapters per API format
- `LLM_PROVIDER` environment variable (default: `ollama`)
- `LLMProviderError` class with actionable error messages

### Changed
- `generator.py` — routes LLM calls through provider abstraction
- Error messages include provider name for debugging
- `install.sh` — interactive provider selection
- `doctor.sh` — validates API key per provider type
- `README.md` — provider table with verification status
- `CHANGELOG.md` — created

## [0.1.0] - 2026-04-15

### Added
- One-command installer with Docker
- `doctor.sh` and `uninstall.sh`
- Frontend Dockerfile
- User-facing README
