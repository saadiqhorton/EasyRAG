#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────
# EasyRAG — Diagnostics (doctor.sh)
# Works for both no-Docker and Docker installs
# ────────────────────────────────────────────────────────────────
set -euo pipefail

EASYRAG_DIR="${EASYRAG_DIR:-$HOME/.easyrag}"
PASSED=0; FAILED=0; WARNINGS=0; TOTAL=0

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

ok()     { PASSED=$((PASSED+1)); TOTAL=$((TOTAL+1)); printf "  ${GREEN}[OK]${NC}   %s\n" "$1"; }
fail()   { FAILED=$((FAILED+1)); TOTAL=$((TOTAL+1)); printf "  ${RED}[FAIL]${NC} %s\n" "$1"; }
warn()   { WARNINGS=$((WARNINGS+1)); TOTAL=$((TOTAL+1)); printf "  ${YELLOW}[WARN]${NC} %s\n" "$1"; }
info()   { printf "         %s\n" "$1"; }

# Detect WSL
IS_WSL=false
if grep -q "microsoft" /proc/version 2>/dev/null || grep -q "WSL" /proc/version 2>/dev/null; then
  IS_WSL=true
fi

echo ""; printf "${BOLD}EasyRAG Doctor${NC}"
if [ "$IS_WSL" = true ]; then
  printf " ${CYAN}(WSL2 detected)${NC}"
fi
printf "\n\n"

# 1. Python
if command -v python3 &>/dev/null; then
  PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "?")
  if [ "${PY_VER%%.*}" -ge 3 ] && [ "${PY_VER#*.}" -ge 11 ] 2>/dev/null; then
    ok "Python ${PY_VER}"
  else
    warn "Python ${PY_VER} — need 3.11+"
  fi
else
  fail "Python 3 not found"
fi

# 2. Virtual environment
if [ -d "${EASYRAG_DIR}/.venv" ]; then
  ok "Virtual environment exists"
else
  fail "Virtual environment not found — run install.sh"
fi

# 3. Qdrant binary
if [ -f "${EASYRAG_DIR}/bin/qdrant" ]; then
  ok "Qdrant binary present"
elif command -v docker &>/dev/null && docker ps &>/dev/null 2>&1; then
  ok "Docker available (Qdrant may run in container)"
else
  fail "Qdrant binary not found and Docker not available"
fi

# 4. Frontend build
if [ -d "${EASYRAG_DIR}/frontend/.next/standalone" ]; then
  ok "Frontend built (standalone)"
else
  warn "Frontend not built — API-only mode"
fi

# 5. Install directory
if [ -d "${EASYRAG_DIR}" ]; then ok "Install dir: ${EASYRAG_DIR}"; else fail "Install dir not found"; fi

# 6. .env file
if [ -f "${EASYRAG_DIR}/.env" ]; then
  ok ".env exists"

  # 7. LLM Provider
  LLM_PROVIDER=$(grep "^LLM_PROVIDER=" "${EASYRAG_DIR}/.env" 2>/dev/null | cut -d= -f2 || echo "ollama")
  ok "LLM provider: ${LLM_PROVIDER}"

  # 8. API key for providers that need it
  if [ "${LLM_PROVIDER}" = "openai" ] || [ "${LLM_PROVIDER}" = "anthropic" ] || [ "${LLM_PROVIDER}" = "gemini" ]; then
    if grep -q "^ANSWER_LLM_API_KEY=.\+" "${EASYRAG_DIR}/.env" 2>/dev/null; then
      ok "API key set for ${LLM_PROVIDER}"
    else
      fail "ANSWER_LLM_API_KEY required for ${LLM_PROVIDER} but not set"
    fi
  fi

  # 9. Database
  DB_URL=$(grep "^DATABASE_URL=" "${EASYRAG_DIR}/.env" 2>/dev/null | cut -d= -f2 || echo "")
  if [ -n "$DB_URL" ]; then
    ok "DATABASE_URL set"
  else
    ok "Using default SQLite database"
  fi
else
  fail ".env not found"
fi

# 10. Ports
for port in 3000 8000 6333; do
  if command -v ss &>/dev/null && ss -tlnp 2>/dev/null | grep -q ":${port} "; then
    warn "Port ${port} in use"
  elif command -v lsof &>/dev/null && lsof -i :"${port}" &>/dev/null 2>&1; then
    warn "Port ${port} in use"
  else
    ok "Port ${port} free"
  fi
done

# 11-13. Service health
if curl -sf --max-time 5 http://localhost:8000/health &>/dev/null; then ok "API healthy"; else warn "API not responding"; fi
if curl -sf --max-time 5 http://localhost:6333/healthz &>/dev/null; then ok "Qdrant healthy"; else warn "Qdrant not responding"; fi
code=$(curl -sf --max-time 5 -o /dev/null -w "%{http_code}" http://localhost:3000 2>/dev/null || echo "000")
if [ "$code" -ge 200 ] && [ "$code" -lt 400 ]; then ok "Frontend responding"; else warn "Frontend not responding"; fi

# 14. Disk space
usage=$(df -h / | awk 'NR==2{print $5}' | sed 's/%//')
if [ "${usage:-0}" -lt 85 ]; then ok "Disk: ${usage}%"; else warn "Disk: ${usage}%"; fi

# 15. WSL-specific checks
if [ "$IS_WSL" = true ]; then
  # Check if Windows host can reach WSL
  WINDOWS_HOST=$(ip route | grep default | awk '{print $3}' 2>/dev/null || echo "")
  if [ -n "$WINDOWS_HOST" ]; then
    ok "WSL network gateway: ${WINDOWS_HOST}"
    info "Access EasyRAG from Windows at: http://localhost:3000"
  else
    warn "WSL network gateway not detected"
  fi
else
  TOTAL=$((TOTAL-1))  # Skip this check on non-WSL
fi

# Summary
echo ""; printf "${BOLD}──────────────────────────────────${NC}\n"
if [ "$FAILED" -eq 0 ]; then
  printf "${GREEN}${PASSED}/${TOTAL} checks passed${NC} (${WARNINGS} warnings)\n\n"
  exit 0
else
  printf "${RED}${PASSED}/${TOTAL} checks passed${NC} (${FAILED} failures, ${WARNINGS} warnings)\n\n"
  exit 1
fi
