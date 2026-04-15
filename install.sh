#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────
# EasyRAG — One-command installer
# Usage:  curl -fsSL https://raw.githubusercontent.com/saadiqhorton/EasyRAG/main/install.sh | bash
# ────────────────────────────────────────────────────────────────
set -euo pipefail

EASYRAG_VERSION="0.1.0"
REPO_URL="https://github.com/saadiqhorton/EasyRAG.git"
INSTALL_DIR="${EASYRAG_DIR:-$HOME/.easyrag}"
COMPOSE_FILE="app/infra/docker-compose.yml"
MAX_WAIT=120

# ── Colors ──────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

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
  sed -i.bak "s/^POSTGRES_PASSWORD=changeme$/POSTGRES_PASSWORD=${GENERATED_PW}/" "${ENV_FILE}" && rm -f "${ENV_FILE}.bak"
  ok "Generated secure POSTGRES_PASSWORD"
else
  step "Using existing .env"
fi

# ── Prompt for LLM if needed ────────────────────────────────────
if grep -q "^ANSWER_LLM_BASE_URL=http://host.docker.internal:11434/v1$" "${ENV_FILE}" 2>/dev/null; then
  echo ""
  banner "LLM Configuration"
  echo "EasyRAG needs an LLM to generate answers."
  echo "If you have Ollama running locally, the defaults work."
  echo ""

  read -r -p "LLM base URL [http://host.docker.internal:11434/v1]: " llm_url < /dev/tty
  llm_url="${llm_url:-http://host.docker.internal:11434/v1}"

  read -r -p "LLM model name [llama3.2]: " llm_model < /dev/tty
  llm_model="${llm_model:-llama3.2}"

  # Update .env
  if [ "$(uname)" = "Darwin" ]; then
    sed -i '' "s|^ANSWER_LLM_BASE_URL=.*|ANSWER_LLM_BASE_URL=${llm_url}|" "${ENV_FILE}"
    sed -i '' "s|^ANSWER_LLM_MODEL=.*|ANSWER_LLM_MODEL=${llm_model}|" "${ENV_FILE}"
  else
    sed -i "s|^ANSWER_LLM_BASE_URL=.*|ANSWER_LLM_BASE_URL=${llm_url}|" "${ENV_FILE}"
    sed -i "s|^ANSWER_LLM_MODEL=.*|ANSWER_LLM_MODEL=${llm_model}|" "${ENV_FILE}"
  fi
  ok "LLM configured: ${llm_model} @ ${llm_url}"
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
echo "  Useful commands:"
echo "    View logs:   docker compose -f ${COMPOSE_FILE} logs -f"
echo "    Stop:        docker compose -f ${COMPOSE_FILE} down"
echo "    Diagnose:    bash ${INSTALL_DIR}/doctor.sh"
echo "    Uninstall:   bash ${INSTALL_DIR}/uninstall.sh"
echo ""
