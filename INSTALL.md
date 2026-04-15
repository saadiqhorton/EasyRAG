# Installation Guide

## One-command install

```bash
curl -fsSL https://raw.githubusercontent.com/saadiqhorton/EasyRAG/main/install.sh | bash
```

The installer will prompt you to choose an AI provider and enter the required settings.

## What the installer does

1. Checks that Docker and Docker Compose are installed and running
2. Checks that required ports (3000, 8000, 5432, 6333) are available
3. Clones the EasyRAG repo into `~/.easyrag` (or updates if already present)
4. Creates a `.env` file from the template with a generated database password
5. Prompts for your AI provider and writes the config
6. Builds and starts all containers
7. Waits for health checks and prints the access URL

## Provider verification status

All five providers are **supported** with dedicated adapters. The adapters are implemented against each provider's documented API format and tested at the code level (factory, validation, error handling, payload structure).

**Live API calls have not been tested from this build environment.** We recommend running a quick smoke test after configuring your provider:

```bash
# After install, test that the LLM provider responds
curl -sf http://localhost:8000/health
```

If the health check passes but answers fail, check the API logs:
```bash
docker compose -f app/infra/docker-compose.yml logs api | grep llm_
```

## Provider setup

### Ollama (default, free, local)

1. Install [Ollama](https://ollama.ai)
2. Run: `ollama pull llama3.2`
3. During install, select option 1 (Ollama)
4. Default base URL: `http://host.docker.internal:11434/v1`

**Required env vars:**
```
LLM_PROVIDER=ollama
ANSWER_LLM_BASE_URL=http://host.docker.internal:11434/v1
ANSWER_LLM_MODEL=llama3.2
```

**Note for Linux users:** Use `http://172.17.0.1:11434/v1` as the base URL instead of `host.docker.internal`, or add the host Docker gateway IP.

### OpenAI

1. Get an API key from [platform.openai.com](https://platform.openai.com)
2. During install, select option 2 (OpenAI)
3. Enter your API key when prompted

**Required env vars:**
```
LLM_PROVIDER=openai
ANSWER_LLM_BASE_URL=https://api.openai.com/v1
ANSWER_LLM_MODEL=gpt-4o
ANSWER_LLM_API_KEY=sk-...
```

Popular models: `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`

### Anthropic

1. Get an API key from [console.anthropic.com](https://console.anthropic.com)
2. During install, select option 3 (Anthropic)
3. Enter your API key when prompted

**Required env vars:**
```
LLM_PROVIDER=anthropic
ANSWER_LLM_BASE_URL=https://api.anthropic.com
ANSWER_LLM_MODEL=claude-sonnet-4-20250514
ANSWER_LLM_API_KEY=sk-ant-...
```

Popular models: `claude-sonnet-4-20250514`, `claude-haiku-4-20250414`

### Google Gemini

1. Get an API key from [aistudio.google.com](https://aistudio.google.com)
2. During install, select option 4 (Gemini)
3. Enter your API key when prompted

**Required env vars:**
```
LLM_PROVIDER=gemini
ANSWER_LLM_BASE_URL=https://generativelanguage.googleapis.com
ANSWER_LLM_MODEL=gemini-2.0-flash
ANSWER_LLM_API_KEY=AIza...
```

Popular models: `gemini-2.0-flash`, `gemini-1.5-pro`

### Custom OpenAI-compatible

For self-hosted models via vLLM, LiteLLM, LocalAI, or any server that exposes an OpenAI-compatible `/chat/completions` endpoint:

**Required env vars:**
```
LLM_PROVIDER=openai_compatible
ANSWER_LLM_BASE_URL=http://your-server:8080/v1
ANSWER_LLM_MODEL=your-model-name
ANSWER_LLM_API_KEY=              # optional, leave empty if not needed
```

## Diagnostics

```bash
bash doctor.sh
```

Checks Docker, ports, environment, provider config, and service health.

## Uninstall

```bash
bash uninstall.sh
```

Stops containers and optionally removes all data.

## Install options

```bash
# Custom install directory
EASYRAG_DIR=/opt/easyrag curl -fsSL https://raw.githubusercontent.com/saadiqhorton/EasyRAG/main/install.sh | bash

# Update an existing install (just re-run)
curl -fsSL https://raw.githubusercontent.com/saadiqhorton/EasyRAG/main/install.sh | bash
```
