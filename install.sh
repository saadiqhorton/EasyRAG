#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────
# EasyRAG — One-command installer
# Usage:  curl -fsSL https://raw.githubusercontent.com/saadiqhorton/EasyRAG/main/install.sh | bash
# ────────────────────────────────────────────────────────────────
set -euo pipefail

EASYRAG_VERSION="0.2.0"
REPO_URL="https://github.com/saadiqhorton/EasyRAG.git"
INSTALL_DIR="${EASYRAG_DIR:-$HOME/.easyrag}"
COMPOSE_FILE="app/infra/docker-compose.yml"
MAX_WAIT=120

# ── Colors ──────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

step()   { printf "${BLUE}▸${NC} %s\n" "$1"; }
ok()     { printf "${GREEN}✔${NC} %s\n" "$1"; }
warn()   { printf "${YELLOW}⚠${NC} %s\n" "$1"; }
fail()   { printf "${RED}✘${NC} %s\n" "$1" >&2; exit 1; }
banner() { printf "\n${BOLD}%s${NC}\n" "$1"; }

# ── Preflight checks ────────────────────────────────────────────
banner "EasyRAG v${EASYRAG_VERSION} Installer"
echo ""

step "Checking Docker..."
if ! command -v docker &>/dev/null; then
  fail "Docker is not installed.
  Install it: https://docs.docker.com/get-docker/"
fi
if ! docker info &>/dev/null 2>&1; then
  fail "Docker is not running. Start it first."
fi
ok "Docker is available"

step "Checking Docker Compose..."
if ! docker compose version &>/dev/null 2>&1; then
  fail "Docker Compose v2 is not available.
  Install it: https://docs.docker.com/compose/install/"
fi
ok "Docker Compose v2 is available"

step "Checking ports..."
for port in 3000 8000 5432 6333; do
  if command -v ss &>/dev/null && ss -tlnp 2>/dev/null | grep -q ":${port} "; then
    warn "Port ${port} is already in use — EasyRAG may fail to start"
  elif command -v lsof &>/dev/null && lsof -i :"${port}" &>/dev/null 2>&1; then
    warn "Port ${port} is already in use — EasyRAG may fail to start"
  fi
done
ok "Port check done"

# ── Clone or update ──────────────────────────────────────────────
step "Setting up EasyRAG at ${INSTALL_DIR}"
if [ -d "${INSTALL_DIR}/.git" ]; then
  step "Updating existing install..."
  (cd "${INSTALL_DIR}" && git pull --ff-only) || warn "Could not pull latest — continuing with local copy"
else
  step "Cloning EasyRAG..."
  mkdir -p "${INSTALL_DIR}"
  git clone --depth 1 "${REPO_URL}" "${INSTALL_DIR}"
fi
ok "Code is ready"

# ── Environment file ────────────────────────────────────────────
ENV_FILE="${INSTALL_DIR}/.env"
if [ ! -f "${ENV_FILE}" ]; then
  step "Creating .env from template..."
  cp "${INSTALL_DIR}/.env.example" "${ENV_FILE}"

  # Generate a random postgres password
  GENERATED_PW=$(openssl rand -hex 16 2>/dev/null || head -c 32 /dev/urandom | xxd -p | head -c 32)
  if [ "$(uname)" = "Darwin" ]; then
    sed -i '' "s/^POSTGRES_PASSWORD=changeme$/POSTGRES_PASSWORD=${GENERATED_PW}/" "${ENV_FILE}"
  else
    sed -i "s/^POSTGRES_PASSWORD=changeme$/POSTGRES_PASSWORD=${GENERATED_PW}/" "${ENV_FILE}"
  fi
  ok "Generated secure POSTGRES_PASSWORD"
else
  step "Using existing .env"
fi

# ── Provider selection ───────────────────────────────────────────
if grep -q "^LLM_PROVIDER=ollama$" "${ENV_FILE}" 2>/dev/null || ! grep -q "^LLM_PROVIDER=" "${ENV_FILE}" 2>/dev/null; then
  echo ""
  banner "Choose your AI provider"
  echo "  ${CYAN}1)${NC} Ollama (local, free, default)"
  echo "  ${CYAN}2)${NC} OpenAI (GPT-4o, etc.)"
  echo "  ${CYAN}3)${NC} Anthropic (Claude)"
  echo "  ${CYAN}4)${NC} Google Gemini"
  echo "  ${CYAN}5)${NC} Custom OpenAI-compatible endpoint"
  echo ""

  read -r -p "Select provider [1-5]: " choice < /dev/tty

  case "${choice}" in
    1|"")
      # Ollama — default
      LLM_PROVIDER="ollama"
      LLM_BASE_URL="http://host.docker.internal:11434/v1"
      LLM_MODEL="llama3.2"
      LLM_API_KEY=""
      echo ""
      echo "  Ollama selected. Make sure Ollama is running with: ${CYAN}ollama serve${NC}"
      echo ""
      read -r -p "Ollama base URL [${LLM_BASE_URL}]: " base_url < /dev/tty
      LLM_BASE_URL="${base_url:-${LLM_BASE_URL}}"
      read -r -p "Model name [${LLM_MODEL}]: " model < /dev/tty
      LLM_MODEL="${model:-${LLM_MODEL}}"
      ;;
    2)
      # OpenAI
      LLM_PROVIDER="openai"
      LLM_BASE_URL="https://api.openai.com/v1"
      LLM_MODEL="gpt-4o"
      echo ""
      read -r -p "OpenAI API key: " api_key < /dev/tty
      LLM_API_KEY="${api_key}"
      read -r -p "Model [${LLM_MODEL}]: " model < /dev/tty
      LLM_MODEL="${model:-${LLM_MODEL}}"
      ;;
    3)
      # Anthropic
      LLM_PROVIDER="anthropic"
      LLM_BASE_URL="https://api.anthropic.com"
      LLM_MODEL="claude-sonnet-4-20250514"
      echo ""
      read -r -p "Anthropic API key: " api_key < /dev/tty
      LLM_API_KEY="${api_key}"
      read -r -p "Model [${LLM_MODEL}]: " model < /dev/tty
      LLM_MODEL="${model:-${LLM_MODEL}}"
      ;;
    4)
      # Gemini
      LLM_PROVIDER="gemini"
      LLM_BASE_URL="https://generativelanguage.googleapis.com"
      LLM_MODEL="gemini-2.0-flash"
      echo ""
      read -r -p "Google AI API key: " api_key < /dev/tty
      LLM_API_KEY="${api_key}"
      read -r -p "Model [${LLM_MODEL}]: " model < /dev/tty
      LLM_MODEL="${model:-${LLM_MODEL}}"
      ;;
    5)
      # OpenAI-compatible custom
      LLM_PROVIDER="openai_compatible"
      echo ""
      read -r -p "Base URL (e.g. http://your-server:8080/v1): " base_url < /dev/tty
      LLM_BASE_URL="${base_url}"
      read -r -p "Model name: " model < /dev/tty
      LLM_MODEL="${model}"
      read -r -p "API key (leave empty if not needed): " api_key < /dev/tty
      LLM_API_KEY="${api_key}"
      ;;
    *)
      LLM_PROVIDER="ollama"
      LLM_BASE_URL="http://host.docker.internal:11434/v1"
      LLM_MODEL="llama3.2"
      LLM_API_KEY=""
      warn "Invalid choice, defaulting to Ollama"
      ;;
  esac

  # Write provider config to .env
  if [ "$(uname)" = "Darwin" ]; then
    sed -i '' "s|^LLM_PROVIDER=.*|LLM_PROVIDER=${LLM_PROVIDER}|" "${ENV_FILE}"
    sed -i '' "s|^ANSWER_LLM_BASE_URL=.*|ANSWER_LLM_BASE_URL=${LLM_BASE_URL}|" "${ENV_FILE}"
    sed -i '' "s|^ANSWER_LLM_MODEL=.*|ANSWER_LLM_MODEL=${LLM_MODEL}|" "${ENV_FILE}"
    sed -i '' "s|^ANSWER_LLM_API_KEY=.*|ANSWER_LLM_API_KEY=${LLM_API_KEY}|" "${ENV_FILE}"
  else
    sed -i "s|^LLM_PROVIDER=.*|LLM_PROVIDER=${LLM_PROVIDER}|" "${ENV_FILE}"
    sed -i "s|^ANSWER_LLM_BASE_URL=.*|ANSWER_LLM_BASE_URL=${LLM_BASE_URL}|" "${ENV_FILE}"
    sed -i "s|^ANSWER_LLM_MODEL=.*|ANSWER_LLM_MODEL=${LLM_MODEL}|" "${ENV_FILE}"
    sed -i "s|^ANSWER_LLM_API_KEY=.*|ANSWER_LLM_API_KEY=${LLM_API_KEY}|" "${ENV_FILE}"
  fi
  ok "Provider configured: ${LLM_PROVIDER} (${LLM_MODEL})"
fi

# ── Docker Compose up ────────────────────────────────────────────
echo ""
banner "Starting EasyRAG..."
step "Building and starting containers (this may take a few minutes on first run)..."
cd "${INSTALL_DIR}"
docker compose -f "${COMPOSE_FILE}" --env-file .env up -d --build 2>&1 || fail "Docker Compose failed to start. Run 'doctor.sh' for diagnostics."

# ── Wait for health ──────────────────────────────────────────────
step "Waiting for services to become healthy (up to ${MAX_WAIT}s)..."
elapsed=0
while [ $elapsed -lt $MAX_WAIT ]; do
  api_ok=false; qdrant_ok=false; frontend_ok=false

  if curl -sf --max-time 3 http://localhost:8000/health &>/dev/null; then api_ok=true; fi
  if curl -sf --max-time 3 http://localhost:6333/healthz &>/dev/null; then qdrant_ok=true; fi
  if curl -sf --max-time 3 -o /dev/null http://localhost:3000 &>/dev/null; then frontend_ok=true; fi

  if $api_ok && $qdrant_ok && $frontend_ok; then
    break
  fi

  sleep 5
  elapsed=$((elapsed + 5))
  printf "  %ds...\r" "$elapsed"
done

if $api_ok && $qdrant_ok && $frontend_ok; then
  ok "All services are healthy"
else
  warn "Some services may still be starting (waited ${MAX_WAIT}s)"
  if ! $api_ok; then warn "API at :8000 is not responding yet"; fi
  if ! $qdrant_ok; then warn "Qdrant at :6333 is not responding yet"; fi
  if ! $frontend_ok; then warn "Frontend at :3000 is not responding yet"; fi
  echo "  Check status: docker compose -f ${COMPOSE_FILE} ps"
fi

# ── Success ──────────────────────────────────────────────────────
echo ""
banner "🚀 EasyRAG is running!"
echo ""
echo "  Open in browser:  ${BOLD}http://localhost:3000${NC}"
echo ""
echo "  Next steps:"
echo "    • Create a collection and upload documents"
echo "    • Ask questions and get cited answers"
echo ""
echo "  Provider: ${CYAN}${LLM_PROVIDER:-ollama}${NC}"
echo ""
echo "  Useful commands:"
echo "    View logs:   docker compose -f ${COMPOSE_FILE} logs -f"
echo "    Stop:        docker compose -f ${COMPOSE_FILE} down"
echo "    Diagnose:    bash ${INSTALL_DIR}/doctor.sh"
echo "    Uninstall:   bash ${INSTALL_DIR}/uninstall.sh"
echo ""
