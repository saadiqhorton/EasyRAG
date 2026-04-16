#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────
# EasyRAG — One-command installer (no Docker required)
# Usage:  curl -fsSL https://raw.githubusercontent.com/saadiqhorton/EasyRAG/main/install.sh | bash
# ────────────────────────────────────────────────────────────────
set -euo pipefail

EASYRAG_VERSION="0.3.0"
INSTALL_DIR="${EASYRAG_DIR:-$HOME/.easyrag}"
DATA_DIR="${INSTALL_DIR}/data"
LOG_DIR="${INSTALL_DIR}/logs"
PID_DIR="${INSTALL_DIR}/.pids"
BIN_DIR="${INSTALL_DIR}/bin"
VENV_DIR="${INSTALL_DIR}/.venv"
QDRANT_VERSION="v1.12.1"

# ── Colors ──────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

step()   { printf "${BLUE}▸${NC} %s\n" "$1"; }
ok()     { printf "${GREEN}✔${NC} %s\n" "$1"; }
warn()   { printf "${YELLOW}⚠${NC} %s\n" "$1"; }
fail()   { printf "${RED}✘${NC} %s\n" "$1" >&2; exit 1; }
banner() { printf "\n${BOLD}%s${NC}\n" "$1"; }

# ── Detect OS and architecture ──────────────────────────────────
detect_platform() {
  OS="$(uname -s)"
  ARCH="$(uname -m)"

  case "${OS}" in
    Linux)  OS="linux";;
    Darwin) OS="macos";;
    *)      fail "Unsupported OS: ${OS}. EasyRAG requires Linux or macOS.";;
  esac

  case "${ARCH}" in
    x86_64|amd64) ARCH="amd64";;
    aarch64|arm64) ARCH="arm64";;
    *)            fail "Unsupported architecture: ${ARCH}";;
  esac

  ok "Platform: ${OS}-${ARCH}"
}

# ── Preflight checks ────────────────────────────────────────────
banner "EasyRAG v${EASYRAG_VERSION} Installer"
echo ""

detect_platform

step "Checking Python..."
if command -v python3 &>/dev/null; then
  PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
  PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
  PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
  if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 11 ]; then
    ok "Python ${PY_VERSION} found"
  else
    fail "Python 3.11+ required, found ${PY_VERSION}.
  Install: https://www.python.org/downloads/"
  fi
else
  fail "Python 3 not found.
  Install: https://www.python.org/downloads/"
fi

step "Checking pip..."
if python3 -m pip &>/dev/null 2>&1; then
  ok "pip available"
else
  fail "pip not found. Install it: https://pip.pypa.io/en/stable/installation/"
fi

step "Checking Node.js (for frontend build)..."
if command -v node &>/dev/null; then
  NODE_VERSION=$(node -v | sed 's/v//')
  NODE_MAJOR=$(echo "$NODE_VERSION" | cut -d. -f1)
  if [ "$NODE_MAJOR" -ge 20 ]; then
    ok "Node.js ${NODE_VERSION} found"
  else
    warn "Node.js 20+ recommended, found ${NODE_VERSION}"
    echo "  Frontend build may fail. Install Node 20+: https://nodejs.org/"
  fi
else
  warn "Node.js not found — frontend will not be built"
  echo "  Install Node 20+ for the web UI: https://nodejs.org/"
  echo "  Or use Docker: see INSTALL.md"
fi

step "Checking ports..."
for port in 3000 8000 6333; do
  if command -v ss &>/dev/null && ss -tlnp 2>/dev/null | grep -q ":${port} "; then
    warn "Port ${port} is already in use"
  elif command -v lsof &>/dev/null && lsof -i :"${port}" &>/dev/null 2>&1; then
    warn "Port ${port} is already in use"
  fi
done
ok "Port check done"

# ── Set up install directory ────────────────────────────────────
step "Setting up EasyRAG at ${INSTALL_DIR}"
mkdir -p "${INSTALL_DIR}" "${DATA_DIR}" "${LOG_DIR}" "${PID_DIR}" "${BIN_DIR}"

# ── Clone or update repo ───────────────────────────────────────
if [ -d "${INSTALL_DIR}/.git" ]; then
  step "Updating existing install..."
  (cd "${INSTALL_DIR}" && git pull --ff-only) || warn "Could not pull — continuing with local copy"
else
  step "Cloning EasyRAG..."
  git clone --depth 1 "https://github.com/saadiqhorton/EasyRAG.git" "${INSTALL_DIR}"
fi
ok "Code is ready"

# ── Create Python virtual environment ───────────────────────────
if [ ! -d "${VENV_DIR}" ]; then
  step "Creating Python virtual environment..."
  python3 -m venv "${VENV_DIR}"
  ok "Virtual environment created"
fi

step "Installing Python dependencies..."
"${VENV_DIR}/bin/pip" install -q --upgrade pip 2>/dev/null || true
"${VENV_DIR}/bin/pip" install -q -e "${INSTALL_DIR}/app/backend" 2>&1 | tail -1
ok "Python dependencies installed"

# ── Download Qdrant binary ──────────────────────────────────────
if [ ! -f "${BIN_DIR}/qdrant" ]; then
  step "Downloading Qdrant ${QDRANT_VERSION}..."
  case "${OS}-${ARCH}" in
    linux-amd64)  QDRANT_TARGET="qdrant-x86_64-unknown-linux-musl" ;;
    linux-arm64) QDRANT_TARGET="qdrant-aarch64-unknown-linux-musl" ;;
    macos-amd64) QDRANT_TARGET="qdrant-x86_64-apple-darwin" ;;
    macos-arm64) QDRANT_TARGET="qdrant-aarch64-apple-darwin" ;;
    *)           fail "No Qdrant binary for ${OS}-${ARCH}" ;;
  esac

  QDRANT_URL="https://github.com/qdrant/qdrant/releases/download/${QDRANT_VERSION}/${QDRANT_TARGET}.tar.gz"
  TMPDIR=$(mktemp -d)

  if curl -fSL --progress-bar -o "${TMPDIR}/qdrant.tar.gz" "${QDRANT_URL}" 2>&1; then
    tar xzf "${TMPDIR}/qdrant.tar.gz" -C "${TMPDIR}"
    # Find the binary (may be in a subdirectory)
    QDRANT_BIN=$(find "${TMPDIR}" -name "qdrant" -type f | head -1)
    if [ -n "$QDRANT_BIN" ]; then
      cp "$QDRANT_BIN" "${BIN_DIR}/qdrant"
      chmod +x "${BIN_DIR}/qdrant"
      ok "Qdrant installed"
    else
      warn "Could not find Qdrant binary in download — you may need to install it manually"
    fi
    rm -rf "${TMPDIR}"
  else
    warn "Could not download Qdrant — skipping"
    echo "  Download manually from: https://github.com/qdrant/qdrant/releases"
    echo "  Place the binary at: ${BIN_DIR}/qdrant"
  fi
else
  ok "Qdrant binary already present"
fi

# ── Build frontend ──────────────────────────────────────────────
if command -v node &>/dev/null && command -v npm &>/dev/null; then
  if [ ! -d "${INSTALL_DIR}/app/frontend/.next/standalone" ]; then
    step "Building frontend (this may take a few minutes)..."
    cd "${INSTALL_DIR}/app/frontend"
    npm install --silent 2>&1 | tail -1
    npm run build 2>&1 | tail -3
    cd "${INSTALL_DIR}"
    if [ -d "${INSTALL_DIR}/app/frontend/.next/standalone" ]; then
      ok "Frontend built"
    else
      warn "Frontend build did not produce standalone output"
    fi
  else
    ok "Frontend already built"
  fi
else
  warn "Skipping frontend build (no Node.js). API-only mode."
  echo "  Install Node.js 20+ and run: cd ${INSTALL_DIR}/app/frontend && npm install && npm run build"
fi

# ── Environment file ────────────────────────────────────────────
ENV_FILE="${INSTALL_DIR}/.env"
if [ ! -f "${ENV_FILE}" ]; then
  step "Creating .env from template..."
  cp "${INSTALL_DIR}/.env.example" "${ENV_FILE}"

  # Set SQLite as default database for local installs
  if [ "$(uname)" = "Darwin" ]; then
    sed -i '' 's|^ANSWER_LLM_BASE_URL=.*|ANSWER_LLM_BASE_URL=http://localhost:11434/v1|' "${ENV_FILE}"
  else
    sed -i 's|^ANSWER_LLM_BASE_URL=.*|ANSWER_LLM_BASE_URL=http://localhost:11434/v1|' "${ENV_FILE}"
  fi
  ok ".env created with SQLite default"
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
      LLM_PROVIDER="ollama"
      LLM_BASE_URL="http://localhost:11434/v1"
      LLM_MODEL="llama3.2"
      LLM_API_KEY=""
      echo ""
      echo "  Ollama selected. Make sure Ollama is running: ${CYAN}ollama serve${NC}"
      read -r -p "  Base URL [${LLM_BASE_URL}]: " base_url < /dev/tty
      LLM_BASE_URL="${base_url:-${LLM_BASE_URL}}"
      read -r -p "  Model [${LLM_MODEL}]: " model < /dev/tty
      LLM_MODEL="${model:-${LLM_MODEL}}"
      ;;
    2)
      LLM_PROVIDER="openai"; LLM_BASE_URL="https://api.openai.com/v1"; LLM_MODEL="gpt-4o"
      echo ""; read -r -p "  OpenAI API key: " api_key < /dev/tty; LLM_API_KEY="${api_key}"
      read -r -p "  Model [${LLM_MODEL}]: " model < /dev/tty; LLM_MODEL="${model:-${LLM_MODEL}}"
      ;;
    3)
      LLM_PROVIDER="anthropic"; LLM_BASE_URL="https://api.anthropic.com"; LLM_MODEL="claude-sonnet-4-20250514"
      echo ""; read -r -p "  Anthropic API key: " api_key < /dev/tty; LLM_API_KEY="${api_key}"
      read -r -p "  Model [${LLM_MODEL}]: " model < /dev/tty; LLM_MODEL="${model:-${LLM_MODEL}}"
      ;;
    4)
      LLM_PROVIDER="gemini"; LLM_BASE_URL="https://generativelanguage.googleapis.com"; LLM_MODEL="gemini-2.0-flash"
      echo ""; read -r -p "  Google AI API key: " api_key < /dev/tty; LLM_API_KEY="${api_key}"
      read -r -p "  Model [${LLM_MODEL}]: " model < /dev/tty; LLM_MODEL="${model:-${LLM_MODEL}}"
      ;;
    5)
      LLM_PROVIDER="openai_compatible"
      echo ""; read -r -p "  Base URL: " base_url < /dev/tty; LLM_BASE_URL="${base_url}"
      read -r -p "  Model name: " model < /dev/tty; LLM_MODEL="${model}"
      read -r -p "  API key (empty if not needed): " api_key < /dev/tty; LLM_API_KEY="${api_key}"
      ;;
    *)
      LLM_PROVIDER="ollama"; LLM_BASE_URL="http://localhost:11434/v1"; LLM_MODEL="llama3.2"; LLM_API_KEY=""
      warn "Invalid choice, defaulting to Ollama"
      ;;
  esac

  # Write to .env
  SED_CMD="sed -i"
  [ "$(uname)" = "Darwin" ] && SED_CMD="sed -i ''"
  $SED_CMD "s|^LLM_PROVIDER=.*|LLM_PROVIDER=${LLM_PROVIDER}|" "${ENV_FILE}"
  $SED_CMD "s|^ANSWER_LLM_BASE_URL=.*|ANSWER_LLM_BASE_URL=${LLM_BASE_URL}|" "${ENV_FILE}"
  $SED_CMD "s|^ANSWER_LLM_MODEL=.*|ANSWER_LLM_MODEL=${LLM_MODEL}|" "${ENV_FILE}"
  $SED_CMD "s|^ANSWER_LLM_API_KEY=.*|ANSWER_LLM_API_KEY=${LLM_API_KEY}|" "${ENV_FILE}"
  ok "Provider: ${LLM_PROVIDER} (${LLM_MODEL})"
fi

# ── Run database migrations ─────────────────────────────────────
step "Running database migrations..."
cd "${INSTALL_DIR}"
set -a; source "${ENV_FILE}"; set +a
export DATABASE_URL="${DATABASE_URL:-sqlite+aiosqlite:///${INSTALL_DIR}/easyrag.db}"
"${VENV_DIR}/bin/python" -m alembic -c app/backend/alembic.ini upgrade head 2>&1 | tail -2 || warn "Migration had issues — may need manual attention"
ok "Database initialized"

# ── Success ─────────────────────────────────────────────────────
echo ""
banner "✓ EasyRAG installed!"
echo ""
echo "  Start:      bash ${INSTALL_DIR}/start.sh"
echo "  Stop:       bash ${INSTALL_DIR}/stop.sh"
echo "  Diagnose:   bash ${INSTALL_DIR}/doctor.sh"
echo "  Uninstall:  bash ${INSTALL_DIR}/uninstall.sh"
echo ""
echo "  After starting, open: ${BOLD}http://localhost:3000${NC}"
echo ""
echo "  Docker fallback: see INSTALL.md for Docker-based install"
echo ""
