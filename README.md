# EasyRAG

Upload your documents, ask questions, get answers with citations.

## Quick Start

```bash
curl -fsSL https://raw.githubusercontent.com/saadiqhorton/EasyRAG/main/install.sh | bash
```

Then open **http://localhost:3000** in your browser.

That's it. The installer checks for Docker, downloads EasyRAG, configures defaults, and starts everything.

## What You Need

- **Docker** — [Install Docker](https://docs.docker.com/get-docker/)
- **Docker Compose v2** — included with Docker Desktop
- **An LLM** — EasyRAG needs a language model to answer questions. The easiest option is [Ollama](https://ollama.ai) running locally with `llama3.2`. The installer will prompt for your LLM settings.

## After Install

1. Open http://localhost:3000
2. Create a collection
3. Upload documents (PDF, Markdown, Word, text, HTML)
4. Ask questions — every answer includes source citations

## Useful Commands

```bash
# View logs
docker compose -f app/infra/docker-compose.yml logs -f

# Stop
docker compose -f app/infra/docker-compose.yml down

# Diagnose issues
bash doctor.sh

# Uninstall
bash uninstall.sh
```

## Troubleshooting

Run the diagnostics script:

```bash
bash doctor.sh
```

Common issues:

- **Docker not running** — Start Docker Desktop or the Docker daemon
- **Port in use** — Stop whatever is using port 3000, 8000, 5432, or 6333
- **LLM not responding** — Make sure Ollama (or your LLM server) is running. For Ollama: `ollama serve`
- **First build is slow** — Docker builds images on first run. Subsequent starts are fast.

## Install Options

```bash
# Install to a custom directory
EASYRAG_DIR=/opt/easyrag curl -fsSL https://raw.githubusercontent.com/sadiqhorton/EasyRAG/main/install.sh | bash

# Re-run to update (pulls latest and restarts)
curl -fsSL https://raw.githubusercontent.com/sadiqhorton/EasyRAG/main/install.sh | bash
```

## How It Works

EasyRAG uses **hybrid search** (semantic + keyword) to find the most relevant parts of your documents, then sends them to a language model to generate an answer. If the evidence is weak, it says so instead of making things up.

The stack runs locally in Docker:
- **Frontend** — Next.js on port 3000
- **API** — FastAPI on port 8000
- **Worker** — Background document processing
- **PostgreSQL** — Metadata and job storage
- **Qdrant** — Vector search engine

## Project Structure

```
app/
├── backend/     FastAPI backend (API, worker, models)
├── frontend/    Next.js frontend
└── infra/       Docker Compose and environment config
```

## API Reference

**Base URL:** `http://localhost:8000/api/v1`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/collections` | POST | Create a collection |
| `/collections` | GET | List collections |
| `/collections/{id}` | GET/DELETE | Get or delete a collection |
| `/collections/{id}/documents` | POST | Upload a document |
| `/collections/{id}/search` | POST | Search for relevant chunks |
| `/collections/{id}/ask` | POST | Ask a question with generation |
| `/health` | GET | Service health check |
| `/health/ready` | GET | Readiness check (DB + Qdrant) |

## License

MIT
