# EasyRAG

Upload your documents, ask questions, get answers with citations.

## Quick Start

```bash
curl -fsSL https://raw.githubusercontent.com/saadiqhorton/EasyRAG/main/install.sh | bash
```

The installer walks you through choosing an AI provider, then starts everything.

## Supported AI Providers

| Provider | Requires API Key | Example Models | Notes |
|----------|-----------------|----------------|-------|
| **Ollama** | No | llama3.2, mistral | Free, runs locally |
| **OpenAI** | Yes | gpt-4o, gpt-4o-mini | Best quality |
| **Anthropic** | Yes | claude-sonnet-4-20250514 | Strong at long documents |
| **Gemini** | Yes | gemini-2.0-flash | Fast and affordable |
| **Custom** | Optional | Any OpenAI-compatible | vLLM, LiteLLM, etc. |

During install, you pick a provider and enter only the settings it needs.

## Prerequisites

- **Docker** — [Install Docker](https://docs.docker.com/get-docker/)
- **Docker Compose v2** — included with Docker Desktop
- **An AI provider** — pick one during install, or configure manually

## After Install

1. Open http://localhost:3000
2. Create a collection
3. Upload documents (PDF, Markdown, Word, text, HTML)
4. Ask questions — every answer includes source citations

## Switching Providers

Edit `~/.easyrag/.env` and change the provider settings:

```bash
# Change provider
LLM_PROVIDER=openai        # ollama | openai | anthropic | gemini | openai_compatible

# Update the corresponding URL, model, and API key
ANSWER_LLM_BASE_URL=https://api.openai.com/v1
ANSWER_LLM_MODEL=gpt-4o
ANSWER_LLM_API_KEY=sk-...

# Then restart
docker compose -f app/infra/docker-compose.yml down
docker compose -f app/infra/docker-compose.yml up -d
```

See [INSTALL.md](INSTALL.md) for detailed setup per provider.

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

```bash
bash doctor.sh
```

Common issues:

- **Docker not running** — Start Docker Desktop or the Docker daemon
- **Port in use** — Stop whatever is using port 3000, 8000, 5432, or 6333
- **LLM not responding** — For Ollama: `ollama serve`. For others: check your API key and base URL
- **API key errors** — Run `doctor.sh` to verify your key is set
- **First build is slow** — Docker builds images on first run

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

## License

MIT
