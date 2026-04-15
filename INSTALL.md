# Installation Guide

## One-command install

```bash
curl -fsSL https://raw.githubusercontent.com/saadiqhorton/EasyRAG/main/install.sh | bash
```

## What the installer does

1. Checks that Docker and Docker Compose are installed and running
2. Checks that required ports (3000, 8000, 5432, 6333) are available
3. Clones the EasyRAG repo into `~/.easyrag` (or updates if already present)
4. Creates a `.env` file from the template with a generated database password
5. Prompts for your LLM base URL and model name (defaults to local Ollama)
6. Builds and starts all containers
7. Waits for health checks and prints the access URL

## Assumptions

- You have Docker and Docker Compose v2 installed
- You have an LLM available (Ollama locally, or a remote API like OpenAI)
- You are on Linux or macOS

## Install options

```bash
# Custom install directory
EASYRAG_DIR=/opt/easyrag curl -fsSL https://raw.githubusercontent.com/saadiqhorton/EasyRAG/main/install.sh | bash

# Update an existing install (just re-run the same command)
curl -fsSL https://raw.githubusercontent.com/saadiqhorton/EasyRAG/main/install.sh | bash
```

## LLM configuration

EasyRAG needs a language model to generate answers. The default assumes [Ollama](https://ollama.ai) running locally.

| LLM Provider | ANSWER_LLM_BASE_URL | ANSWER_LLM_MODEL | ANSWER_LLM_API_KEY |
|---------------|---------------------|-------------------|--------------------|
| Ollama (local) | `http://host.docker.internal:11434/v1` | `llama3.2` | (leave empty) |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` | `sk-...` |
| Anthropic | `https://api.anthropic.com/v1` | `claude-sonnet-4-20250514` | Your API key |

## Diagnostics

If something isn't working:

```bash
bash doctor.sh
```

This checks Docker, ports, environment, and service health.

## Uninstall

```bash
bash uninstall.sh
```

Stops containers and optionally removes all data.

## Release-based install (future)

The installer currently always pulls from `main`. For release-based installs:

```bash
# Install a specific version (future)
EASYRAG_VERSION=0.2.0 curl -fsSL https://raw.githubusercontent.com/saadiqhorton/EasyRAG/main/install.sh | bash
```

The `VERSION` file at the repo root tracks the current release. The installer reads `EASYRAG_VERSION` to optionally pin to a specific tag.
