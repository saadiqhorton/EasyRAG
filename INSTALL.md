# Installation Guide

## No-Docker install (recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/saadiqhorton/EasyRAG/main/install.sh | bash
bash ~/.easyrag/start.sh
```

Open http://localhost:3000.

The installer:
- Checks Python 3.11+ and Node.js 20+
- Creates a virtual environment and installs Python packages
- Downloads Qdrant (vector search engine) as a local binary
- Builds the Next.js frontend
- Generates `.env` with sensible defaults (SQLite database, no PostgreSQL needed)
- Prompts for your AI provider
- Runs database migrations

### Requirements

| Dependency | Version | Why |
|-----------|---------|-----|
| Python | 3.11+ | Backend runtime |
| Node.js | 20+ | Frontend build |
| pip | any | Package install |
| curl | any | Downloads |

### What runs locally

- **SQLite** — database, stored in `~/.easyrag/easyrag.db` (no install needed)
- **Qdrant** — vector search, runs as a local binary in `~/.easyrag/bin/`
- **FastAPI** — API server on port 8000
- **Worker** — background document processing
- **Next.js** — frontend on port 3000

### Lifecycle

```bash
bash ~/.easyrag/start.sh       # Start all services
bash ~/.easyrag/stop.sh         # Stop all services
bash ~/.easyrag/doctor.sh       # Diagnose issues
bash ~/.easyrag/uninstall.sh    # Remove EasyRAG
```

Logs: `~/.easyrag/logs/`

### Updating

Re-run the installer. It preserves your `.env` and data:

```bash
curl -fsSL https://raw.githubusercontent.com/saadiqhorton/EasyRAG/main/install.sh | bash
bash ~/.easyrag/start.sh
```

### Provider setup

The installer asks which AI provider to use. For details per provider:

**Ollama (default, free, local):**
1. Install [Ollama](https://ollama.ai)
2. Run: `ollama pull llama3.2`
3. Select option 1 during install

**OpenAI:**
- Get key from [platform.openai.com](https://platform.openai.com)
- Select option 2 during install

**Anthropic:**
- Get key from [console.anthropic.com](https://console.anthropic.com)
- Select option 3 during install

**Gemini:**
- Get key from [aistudio.google.com](https://aistudio.google.com)
- Select option 4 during install

**Custom OpenAI-compatible:**
- Any server with `/chat/completions` endpoint
- Select option 5 during install

---

## Docker install (alternative)

If you prefer Docker, the original Docker Compose path still works:

```bash
curl -fsSL https://raw.githubusercontent.com/saadiqhorton/EasyRAG/main/install.sh | bash
# The installer detects Docker and can use it
# Or manually:
cd ~/.easyrag
docker compose -f app/infra/docker-compose.yml --env-file .env up -d --build
```

Docker uses PostgreSQL instead of SQLite. Both paths support all 5 AI providers.

### Docker commands

```bash
docker compose -f app/infra/docker-compose.yml logs -f    # Logs
docker compose -f app/infra/docker-compose.yml down        # Stop
docker compose -f app/infra/docker-compose.yml down -v    # Stop + remove data
```
