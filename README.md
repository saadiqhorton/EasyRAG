# EasyRAG

Upload your documents, ask questions, get answers with citations.

## Quick Start

```bash
curl -fsSL https://raw.githubusercontent.com/saadiqhorton/EasyRAG/main/install.sh | bash
```

Then start the app:

```bash
bash ~/.easyrag/start.sh
```

Open **http://localhost:3000** in your browser.

No Docker. No Node. No Python setup. Just one command.

## Platform Support

| Platform | Method | Status |
|----------|--------|--------|
| **Linux AMD64** | One-command install | ✅ Supported |
| **Windows** | WSL2 + Ubuntu | ✅ Supported |
| **macOS** | Docker | ✅ Available |
| **macOS** | One-command install | ⏳ Coming soon |

### What you need

- **Linux AMD64** — Nothing else. Python is bundled. Bundle size is ~3.1GB compressed / ~6.2GB installed.
- **Windows** — WSL2 + Ubuntu (free from Microsoft Store)
- **AI Provider** — Ollama (free, local) or a cloud API key

### Windows Users

EasyRAG runs on Windows via **WSL2** (Windows Subsystem for Linux). This is the supported Windows path — native Windows packaging is not yet available.

**Quick WSL setup:**
1. Install WSL2: `wsl --install` in PowerShell (Admin)
2. Open Ubuntu
3. Run the install command above
4. Open http://localhost:3000 in your Windows browser

See [INSTALL.md](INSTALL.md) for detailed WSL instructions.

## After install

1. Open http://localhost:3000
2. Create a collection
3. Upload documents (PDF, Markdown, Word, text, HTML)
4. Ask questions — every answer includes source citations

## AI Providers

| Provider | API Key | Example Models |
|----------|---------|----------------|
| **Ollama** | No | llama3.2, mistral |
| **OpenAI** | Yes | gpt-4o, gpt-4o-mini |
| **Anthropic** | Yes | claude-sonnet-4-20250514 |
| **Gemini** | Yes | gemini-2.0-flash |
| **Custom** | Optional | Any OpenAI-compatible |

Pick one during install. Switch any time by editing `~/.easyrag/.env`.

## Commands

```bash
bash ~/.easyrag/start.sh      # Start all services
bash ~/.easyrag/stop.sh       # Stop all services
bash ~/.easyrag/doctor.sh     # Diagnose issues
bash ~/.easyrag/uninstall.sh  # Remove EasyRAG
```

## Switching providers

Edit `~/.easyrag/.env`:

```
LLM_PROVIDER=openai
ANSWER_LLM_BASE_URL=https://api.openai.com/v1
ANSWER_LLM_MODEL=gpt-4o
ANSWER_LLM_API_KEY=sk-...
```

Then restart: `bash ~/.easyrag/stop.sh && bash ~/.easyrag/start.sh`

## Docker install

If you prefer Docker, see [INSTALL.md](INSTALL.md) for the Docker-based install path.

## How it works

EasyRAG uses **hybrid search** (semantic + keyword) to find relevant parts of your documents, then sends them to a language model to generate an answer. If evidence is weak, it says so instead of making things up.

Local services:
- **API** — FastAPI on port 8000
- **Worker** — Background document processing
- **Qdrant** — Vector search engine on port 6333
- **Frontend** — Next.js on port 3000
- **Database** — SQLite (local file, no setup needed)

The Linux AMD64 bundle includes a complete Python runtime. No system Python required.

## License

MIT
