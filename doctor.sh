#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────
# EasyRAG — Diagnostics (doctor.sh)
# Usage:  bash doctor.sh
# ────────────────────────────────────────────────────────────────
set -euo pipefail

EASYRAG_DIR="${EASYRAG_DIR:-$HOME/.easyrag}"
COMPOSE_FILE="app/infra/docker-compose.yml"
PASSED=0; FAILED=0; WARNINGS=0; TOTAL=0

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

ok()     { PASSED=$((PASSED+1)); TOTAL=$((TOTAL+1)); printf "  ${GREEN}[OK]${NC}   %s\n" "$1"; }
fail()   { FAILED=$((FAILED+1)); TOTAL=$((TOTAL+1)); printf "  ${RED}[FAIL]${NC} %s\n" "$1"; }
warn()   { WARNINGS=$((WARNINGS+1)); TOTAL=$((TOTAL+1)); printf "  ${YELLOW}[WARN]${NC} %s\n" "$1"; }
info()   { printf "         %s\n" "$1"; }

echo ""; printf "${BOLD}EasyRAG Doctor${NC}\n\n"

# 1. Docker
if command -v docker &>/dev/null; then
  if docker info &>/dev/null 2>&1; then ok "Docker is installed and running"; else fail "Docker is installed but not running"; fi
else
  fail "Docker is not installed"; info "Install: https://docs.docker.com/get-docker/"
fi

# 2. Docker Compose
if docker compose version &>/dev/null 2>&1; then ok "Docker Compose v2 is available"; else fail "Docker Compose v2 is not available"; fi

# 3. Install directory
if [ -d "${EASYRAG_DIR}" ]; then ok "Install directory exists (${EASYRAG_DIR})"; else fail "Install directory not found (${EASYRAG_DIR})"; fi

# 4. .env file and config
if [ -f "${EASYRAG_DIR}/.env" ]; then
  ok ".env file exists"

  # 5. LLM Provider
  LLM_PROVIDER=$(grep "^LLM_PROVIDER=" "${EASYRAG_DIR}/.env" 2>/dev/null | cut -d= -f2 || echo "ollama")
  if [ -n "${LLM_PROVIDER}" ]; then
    ok "LLM provider: ${LLM_PROVIDER}"
  else
    warn "LLM_PROVIDER not set (defaulting to ollama)"
  fi

  # 6. Required vars per provider
  for var in ANSWER_LLM_BASE_URL ANSWER_LLM_MODEL; do
    if grep -q "^${var}=." "${EASYRAG_DIR}/.env" 2>/dev/null; then
      ok "${var} is set"
    else
      fail "${var} is not set"
    fi
  done

  # 7. API key check for providers that require it
  if [ "${LLM_PROVIDER}" = "openai" ] || [ "${LLM_PROVIDER}" = "anthropic" ] || [ "${LLM_PROVIDER}" = "gemini" ]; then
    if grep -q "^ANSWER_LLM_API_KEY=.\+" "${EASYRAG_DIR}/.env" 2>/dev/null; then
      ok "API key is set for ${LLM_PROVIDER}"
    else
      fail "ANSWER_LLM_API_KEY is required for ${LLM_PROVIDER} but not set"
      info "Set it in ${EASYRAG_DIR}/.env"
    fi
  elif [ "${LLM_PROVIDER}" = "ollama" ]; then
    ok "Ollama does not require an API key"
  fi

  # 8. Postgres password
  if grep -q "^POSTGRES_PASSWORD=changeme$" "${EASYRAG_DIR}/.env" 2>/dev/null; then
    warn "POSTGRES_PASSWORD is still set to default 'changeme'"
    info "Generate a secure one with: openssl rand -hex 16"
  else
    ok "POSTGRES_PASSWORD is set"
  fi
else
  fail ".env file not found"; info "Run install.sh or copy .env.example to .env"
fi

# 9. Ports
for port in 3000 8000 5432 6333; do
  if command -v ss &>/dev/null; then
    listening=$(ss -tlnp 2>/dev/null | grep -c ":${port} " || true)
  elif command -v lsof &>/dev/null; then
    listening=$(lsof -i :"${port}" 2>/dev/null | grep -c LISTEN || true)
  else
    listening=0
  fi
  if [ "$listening" -gt 0 ]; then warn "Port ${port} is in use"; else ok "Port ${port} is free"; fi
done

# 10. Containers
if [ -f "${EASYRAG_DIR}/${COMPOSE_FILE}" ]; then
  running=$(cd "${EASYRAG_DIR}" && docker compose -f "${COMPOSE_FILE}" ps --format '{{.Status}}' 2>/dev/null | grep -c "Up\|running" || true)
  expected=5
  if [ "$running" -ge "$expected" ]; then ok "All ${expected} containers are running"; else warn "${running}/${expected} containers running"; fi
else
  fail "docker-compose.yml not found at ${EASYRAG_DIR}/${COMPOSE_FILE}"
fi

# 11-13. Service health
if curl -sf --max-time 5 http://localhost:8000/health &>/dev/null; then ok "API is healthy (/health)"; else fail "API is not responding at :8000"; fi
if curl -sf --max-time 5 http://localhost:6333/healthz &>/dev/null; then ok "Qdrant is healthy (/healthz)"; else fail "Qdrant is not responding at :6333"; fi
code=$(curl -sf --max-time 5 -o /dev/null -w "%{http_code}" http://localhost:3000 2>/dev/null || echo "000")
if [ "$code" -ge 200 ] && [ "$code" -lt 400 ]; then ok "Frontend is responding at :3000 (HTTP ${code})"; else fail "Frontend is not responding at :3000 (HTTP ${code})"; fi

# 14. Disk space
if command -v df &>/dev/null; then
  usage=$(df -h / | awk 'NR==2{print $5}' | sed 's/%//')
  if [ "${usage:-0}" -lt 85 ]; then ok "Disk usage at ${usage}%"; else warn "Disk usage at ${usage}% — may cause issues"; fi
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
