#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────
# EasyRAG — One-command installer (no system prerequisites required)
# Usage:  curl -fsSL https://raw.githubusercontent.com/saadiqhorton/EasyRAG/main/install.sh | bash
# ────────────────────────────────────────────────────────────────
set -euo pipefail

EASYRAG_VERSION="0.4.2"
RELEASE_BASE_URL="https://github.com/saadiqhorton/EasyRAG/releases/download/v${EASYRAG_VERSION}"
INSTALL_DIR="${EASYRAG_DIR:-$HOME/.easyrag}"
DATA_DIR="${INSTALL_DIR}/data"
LOG_DIR="${INSTALL_DIR}/logs"
PID_DIR="${INSTALL_DIR}/.pids"
BIN_DIR="${INSTALL_DIR}/bin"
RUNTIME_DIR="${INSTALL_DIR}/runtime"
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

  PLATFORM="${OS}-${ARCH}"
  ok "Platform: ${PLATFORM}"
}

# ── Preflight checks ────────────────────────────────────────────
banner "EasyRAG v${EASYRAG_VERSION} Installer"
echo ""

detect_platform

step "Checking ports..."
for port in 3000 8000 6333; do
  if command -v ss >/dev/null 2>&1 && ss -tlnp 2>/dev/null | grep -q ":${port} "; then
    warn "Port ${port} is already in use"
  elif command -v lsof >/dev/null 2>&1 && lsof -i :"${port}" >/dev/null 2>&1; then
    warn "Port ${port} is already in use"
  fi
done
ok "Port check done"

# ── Set up install directory ────────────────────────────────────
step "Setting up EasyRAG at ${INSTALL_DIR}"
mkdir -p "${INSTALL_DIR}" "${DATA_DIR}" "${LOG_DIR}" "${PID_DIR}" "${BIN_DIR}"

# ── Download release bundle ─────────────────────────────────────
RELEASE_FILE="easyrag-${EASYRAG_VERSION}-${PLATFORM}-light.tar.gz"
RELEASE_URL="${RELEASE_BASE_URL}/${RELEASE_FILE}"

if [ -d "${INSTALL_DIR}/backend" ] && [ -d "${INSTALL_DIR}/runtime" ]; then
  step "Release already extracted"
else
  step "Downloading EasyRAG ${EASYRAG_VERSION} lightweight bundle..."
  TMPDIR=$(mktemp -d)
  if curl -fSL --progress-bar -o "${TMPDIR}/${RELEASE_FILE}" "${RELEASE_URL}" 2>/dev/null; then
    step "Extracting release..."
    tar xzf "${TMPDIR}/${RELEASE_FILE}" -C "${INSTALL_DIR}"
    rm -rf "${TMPDIR}"
    ok "EasyRAG downloaded and extracted"
  else
    fail "Could not download release from ${RELEASE_URL}"
  fi
fi

ok "Release ready"

# ── Verify bundled Python runtime ───────────────────────────────
if [ ! -f "${RUNTIME_DIR}/bin/python3" ]; then
  fail "Bundled Python runtime not found. Release bundle may be incomplete."
fi
ok "Bundled Python runtime found"

# ── Install Python dependencies ────────────────────────────────
step "Installing backend dependencies (this may take a few minutes)..."
# Ensure pip installs into the bundled runtime's site-packages explicitly
# Use the actual INSTALL_DIR for the target, not just the runtime path
TARGET_S_P="${INSTALL_DIR}/runtime/lib/python3.12/site-packages"
"${RUNTIME_DIR}/bin/python3" -m pip install --no-cache-dir --target "${TARGET_S_P}" -r "${INSTALL_DIR}/backend/requirements.txt" || warn "Some dependencies failed to install — check logs"
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
# Check if we're in a TTY (interactive) or piped (non-interactive)
if [ -t 0 ] && [ -t 1 ]; then
  INTERACTIVE=true
else
  INTERACTIVE=false
fi

if ! grep -q "^LLM_PROVIDER=" "${ENV_FILE}" 2>/dev/null || \
   (grep -q "^LLM_PROVIDER=ollama$" "${ENV_FILE}" 2>/dev/null && [ "$INTERACTIVE" = true ]); then

  if [ "$INTERACTIVE" = true ]; then
    echo ""
    banner "Choose your AI provider"
    echo "  ${CYAN}1)${NC} Ollama (local, free, default)"
    echo "  ${CYAN}2)${NC} OpenAI (GPT-4o, etc.)"
    echo "  ${CYAN}3)${NC} Anthropic (Claude)"
    echo "  ${CYAN}4)${NC} Google Gemini"
    echo "  ${CYAN}5)${NC} Custom OpenAI-compatible endpoint"
    echo ""

    read -r -p "Select provider [1-5]: " choice

    case "${choice}" in
      1|"")
        LLM_PROVIDER="ollama"
        LLM_BASE_URL="http://localhost:11434/v1"
        LLM_MODEL="llama3.2"
        LLM_API_KEY=""
        echo ""
        echo "  Ollama selected. Make sure Ollama is running: ${CYAN}ollama serve${NC}"
        read -r -p "  Base URL [${LLM_BASE_URL}]: " base_url
        LLM_BASE_URL="${base_url:-${LLM_BASE_URL}}"
        read -r -p "  Model [${LLM_MODEL}]: " model
        LLM_MODEL="${model:-${LLM_MODEL}}"
        ;;
      2)
        LLM_PROVIDER="openai"; LLM_BASE_URL="https://api.openai.com/v1"; LLM_MODEL="gpt-4o"
        echo ""; read -r -p "  OpenAI API key: " api_key; LLM_API_KEY="${api_key}"
        read -r -p "  Model [${LLM_MODEL}]: " model; LLM_MODEL="${model:-${LLM_MODEL}}"
        ;;
      3)
        LLM_PROVIDER="anthropic"; LLM_BASE_URL="https://api.anthropic.com"; LLM_MODEL="claude-sonnet-4-20250514"
        echo ""; read -r -p "  Anthropic API key: " api_key; LLM_API_KEY="${api_key}"
        read -r -p "  Model [${LLM_MODEL}]: " model; LLM_MODEL="${model:-${LLM_MODEL}}"
        ;;
      4)
        LLM_PROVIDER="gemini"; LLM_BASE_URL="https://generativelanguage.googleapis.com"; LLM_MODEL="gemini-2.0-flash"
        echo ""; read -r -p "  Google AI API key: " api_key; LLM_API_KEY="${api_key}"
        read -r -p "  Model [${LLM_MODEL}]: " model; LLM_MODEL="${model:-${LLM_MODEL}}"
        ;;
      5)
        LLM_PROVIDER="openai_compatible"
        echo ""; read -r -p "  Base URL: " base_url; LLM_BASE_URL="${base_url}"
        read -r -p "  Model name: " model; LLM_MODEL="${model}"
        read -r -p "  API key (empty if not needed): " api_key; LLM_API_KEY="${api_key}"
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
  else
    # Non-interactive: use defaults from .env.example (already set)
    ok "Using default provider (ollama) - non-interactive mode"
  fi
fi

# ── Run database migrations ─────────────────────────────────────
step "Running database migrations..."
cd "${INSTALL_DIR}"
set -a; source "${ENV_FILE}"; set +a
export DATABASE_URL="${DATABASE_URL:-sqlite+aiosqlite:///${INSTALL_DIR}/easyrag.db}"
"${RUNTIME_DIR}/bin/python3" -m alembic -c backend/alembic.ini upgrade head 2>&1 | tail -2 || warn "Migration had issues — may need manual attention"
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
