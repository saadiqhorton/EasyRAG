#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────
# EasyRAG — Diagnostics (doctor.sh)
# Usage:  bash doctor.sh
# ────────────────────────────────────────────────────────────────
set -euo pipefail

EASYRAG_DIR="${EASYRAG_DIR:-$HOME/.easyrag}"
COMPOSE_FILE="app/infra/docker-compose.yml"
PASSED=0; FAILED=0; WARNINGS=0; TOTAL=0

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'

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

# 4. .env file
if [ -f "${EASYRAG_DIR}/.env" ]; then
  ok ".env file exists"
  # 5. Required vars
  for var in ANSWER_LLM_BASE_URL ANSWER_LLM_MODEL POSTGRES_PASSWORD; do
    if grep -q "^${var}=" "${EASYRAG_DIR}/.env" && ! grep -q "^${var}=$" "${EASYRAG_DIR}/.env" && ! grep -q "^${var}=changeme$" "${EASYRAG_DIR}/.env"; then
      ok "${var} is set"
    else
      if [ "${var}" = "POSTGRES_PASSWORD" ]; then
        warn "${var} is not set or still has default value"
      else
        fail "${var} is not set"
      fi
    fi
  done
else
  fail ".env file not found"; info "Run install.sh or copy .env.example to .env"
fi

# 6. Ports
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

# 7. Containers
if [ -f "${EASYRAG_DIR}/${COMPOSE_FILE}" ]; then
  running=$(cd "${EASYRAG_DIR}" && docker compose -f "${COMPOSE_FILE}" ps --format '{{.Status}}' 2>/dev/null | grep -c "Up\|running" || true)
  expected=5
  if [ "$running" -ge "$expected" ]; then ok "All ${expected} containers are running"; else warn "${running}/${expected} containers running"; fi
else
  fail "docker-compose.yml not found at ${EASYRAG_DIR}/${COMPOSE_FILE}"
fi

# 8. API health
if curl -sf --max-time 5 http://localhost:8000/health &>/dev/null; then ok "API is healthy (/health)"; else fail "API is not responding at :8000"; fi

# 9. Qdrant health
if curl -sf --max-time 5 http://localhost:6333/healthz &>/dev/null; then ok "Qdrant is healthy (/healthz)"; else fail "Qdrant is not responding at :6333"; fi

# 10. Frontend
code=$(curl -sf --max-time 5 -o /dev/null -w "%{http_code}" http://localhost:3000 2>/dev/null || echo "000")
if [ "$code" -ge 200 ] && [ "$code" -lt 400 ]; then ok "Frontend is responding at :3000 (HTTP ${code})"; else fail "Frontend is not responding at :3000 (HTTP ${code})"; fi

# 11. Disk space
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
