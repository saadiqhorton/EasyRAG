#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────
# EasyRAG — Uninstall
# Works for both no-Docker and Docker installs
# ────────────────────────────────────────────────────────────────
set -euo pipefail

EASYRAG_DIR="${EASYRAG_DIR:-$HOME/.easyrag}"
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'

echo ""; printf "${BOLD}EasyRAG Uninstall${NC}\n\n"

if [ ! -d "${EASYRAG_DIR}" ]; then
  printf "${YELLOW}EasyRAG not found at ${EASYRAG_DIR}.${NC}\nNothing to uninstall.\n\n"
  exit 0
fi

# Stop services first
if [ -f "${EASYRAG_DIR}/stop.sh" ]; then
  echo "Stopping services..."
  bash "${EASYRAG_DIR}/stop.sh" 2>/dev/null || true
fi

# Also stop Docker services if running
if [ -f "${EASYRAG_DIR}/app/infra/docker-compose.yml" ]; then
  docker compose -f "${EASYRAG_DIR}/app/infra/docker-compose.yml" down 2>/dev/null || true
fi

echo ""
printf "${RED}Remove all EasyRAG data?${NC} This deletes documents, database, and vector index.\n"
read -r -p "Type 'yes' to confirm, anything else to keep data: " confirm < /dev/tty

if [ "${confirm}" = "yes" ]; then
  # Remove Docker volumes if they exist
  if [ -f "${EASYRAG_DIR}/app/infra/docker-compose.yml" ]; then
    docker compose -f "${EASYRAG_DIR}/app/infra/docker-compose.yml" down -v 2>/dev/null || true
  fi
  rm -rf "${EASYRAG_DIR}"
  printf "${GREEN}EasyRAG completely removed.${NC}\n\n"
else
  printf "${GREEN}Data preserved at ${EASYRAG_DIR}${NC}\n"
  echo "  Start again: bash ${EASYRAG_DIR}/start.sh"
fi

echo ""; printf "${BOLD}Uninstall complete.${NC}\n\n"
