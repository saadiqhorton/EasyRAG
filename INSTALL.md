# Installation Guide

## Platform Quick Reference

| Platform | Recommended Method | Prerequisites |
|----------|-------------------|---------------|
| Linux AMD64 | One-command install | None — Python is bundled |
| Windows 10/11 | WSL2 + Ubuntu | WSL2 (free from Microsoft) |
| macOS | Docker install | Docker Desktop |
| Other | Docker install | Docker |

---

## One-command install (Linux AMD64)

The easiest way to install EasyRAG on Linux AMD64. No Python or Node required — everything is bundled.

```bash
curl -fsSL https://raw.githubusercontent.com/saadiqhorton/EasyRAG/main/install.sh | bash
bash ~/.easyrag/start.sh
```

Open http://localhost:3000.

The installer:
- Downloads the release bundle (~100 MB) with bundled Python runtime
- Creates a virtual environment
- Installs Python dependencies
- Downloads Qdrant (vector search engine)
- Generates `.env` with sensible defaults
- Prompts for your AI provider (in interactive mode)
- Runs database migrations

### Requirements

| Dependency | Required | Notes |
|-----------|----------|-------|
| Python | **No** | Bundled with EasyRAG |
| curl | Yes | For downloading the installer and bundle |
| Linux AMD64 | Yes | x86_64 architecture |

### What runs locally

- **Python 3.12** — bundled runtime in `~/.easyrag/runtime/`
- **SQLite** — database, stored in `~/.easyrag/easyrag.db`
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

---

## Windows (WSL2)

EasyRAG runs on Windows through **WSL2** (Windows Subsystem for Linux). This is the supported Windows path — native Windows packaging is not yet available.

### Prerequisites

1. **Windows 10 version 2004+** or **Windows 11**
2. **WSL2 with Ubuntu** installed

### Step 1: Install WSL2

Open PowerShell as Administrator and run:

```powershell
wsl --install
```

This installs WSL2 with Ubuntu by default. Restart your computer when prompted.

After restart, Ubuntu will open automatically to finish setup. Create a username and password when asked.

### Step 2: Install EasyRAG in Ubuntu

Open Ubuntu (from the Start menu) and run:

```bash
curl -fsSL https://raw.githubusercontent.com/saadiqhorton/EasyRAG/main/install.sh | bash
```

The installer will:
- Download the Linux AMD64 bundle with bundled Python
- Set up the virtual environment
- Download Qdrant
- Create configuration files

If running interactively, you'll be prompted to select an AI provider.

### Step 3: Start EasyRAG

```bash
bash ~/.easyrag/start.sh
```

### Step 4: Access from Windows

Open your Windows browser and go to:

```
http://localhost:3000
```

WSL2 automatically forwards localhost ports to Windows. No extra configuration needed.

### Where files are stored

Inside WSL:
- **Install location**: `~/.easyrag/` (which is `/home/YOUR_USERNAME/.easyrag/`)
- **Python runtime**: `~/.easyrag/runtime/` (bundled)
- **Database**: `~/.easyrag/easyrag.db`
- **Documents**: `~/.easyrag/data/`
- **Logs**: `~/.easyrag/logs/`

From Windows File Explorer, you can access WSL files at:
```
\\wsl$\Ubuntu\home\YOUR_USERNAME\.easyrag\
```

### WSL-specific commands

All commands work the same as Linux:

```bash
# Inside Ubuntu terminal:
bash ~/.easyrag/start.sh      # Start
bash ~/.easyrag/stop.sh       # Stop
bash ~/.easyrag/doctor.sh     # Check health
bash ~/.easyrag/uninstall.sh  # Remove
```

### Provider notes for WSL

**Option 1: Ollama on Windows host** (recommended)

1. Install Ollama on Windows (not in WSL)
2. Get your Windows host IP in WSL:
   ```bash
   ip route | grep default
   # Example output: default via 172.21.192.1 dev eth0
   # The Windows host is at 172.21.192.1
   ```
3. Edit `~/.easyrag/.env` and set:
   ```
   ANSWER_LLM_BASE_URL=http://172.21.192.1:11434/v1
   ```
4. Restart EasyRAG

**Option 2: Ollama inside WSL**

1. Install Ollama in Ubuntu: `curl -fsSL https://ollama.com/install.sh | sh`
2. Run: `ollama serve` (in a separate terminal)
3. Default config works: `http://localhost:11434/v1`

**Option 3: Cloud providers (OpenAI, Anthropic, Gemini)**

These work the same as on Linux. No WSL-specific configuration needed.

### Troubleshooting WSL

**"localhost:3000" doesn't work from Windows**

1. Check WSL is running: `wsl -l -v` in PowerShell
2. Check EasyRAG is running: `bash ~/.easyrag/doctor.sh`
3. Try accessing via WSL IP instead:
   ```bash
   ip addr | grep eth0
   # Use the IP shown with :3000
   ```

**Permission denied errors**

Make sure you're in your home directory, not a Windows-mounted drive:
```bash
cd ~
bash ~/.easyrag/start.sh
```

**Out of memory**

WSL2 may use too much memory. Create `.wslconfig` in Windows:

```ini
# In C:\Users\YOUR_USERNAME\.wslconfig
[wsl2]
memory=8GB
processors=4
```

Then restart WSL: `wsl --shutdown` in PowerShell.

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

---

## Provider setup

The installer asks which AI provider to use. For details per provider:

### Ollama (default, free, local)

**On Linux/WSL:**
1. Install: `curl -fsSL https://ollama.com/install.sh | sh`
2. Run: `ollama pull llama3.2`
3. Start: `ollama serve` (in a separate terminal)
4. Select option 1 during install

**On Windows:**
1. Install from [ollama.ai](https://ollama.ai)
2. Run: `ollama pull llama3.2` in PowerShell
3. For WSL: use the Windows host IP as base URL

### OpenAI

- Get key from [platform.openai.com](https://platform.openai.com)
- Select option 2 during install

### Anthropic

- Get key from [console.anthropic.com](https://console.anthropic.com)
- Select option 3 during install

### Gemini

- Get key from [aistudio.google.com](https://aistudio.google.com)
- Select option 4 during install

### Custom OpenAI-compatible

- Any server with `/chat/completions` endpoint
- Select option 5 during install

---

## Platform-specific notes

### Linux AMD64

The one-command install is fully tested on Ubuntu 22.04+ and works on any Linux AMD64 distribution. Python is bundled, so no system Python is required.

### Windows

- **One-command**: Use WSL2 + Ubuntu (documented above)
- **Docker**: Works on Windows with Docker Desktop
- **Native**: Not yet supported

### macOS

- **One-command**: Planned but not yet released
- **Docker**: Works with Docker Desktop
