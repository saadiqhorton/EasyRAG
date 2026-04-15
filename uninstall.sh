#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────
# EasyRAG — Uninstall
# Usage:  bash uninstall.sh
# ────────────────────────────────────────────────────────────────
set -euo pipefail

EASYRAG_DIR="${EASYRAG_DIR:-$HOME/.easyrag}"
COMPOSE_FILE="app/infra/docker-compose.yml"
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'

step() { printf "${YELLOW}▸${NC} %s\n" "$1"; }
ok()   { printf "${GREEN}✔${NC} %s\n" "$1"; }

echo ""; printf "${BOLD}EasyRAG Uninstall${NC}\n\n"

if [ ! -d "${EASYRAG_DIR}" ]; then
  printf "${YELLOW}EasyRAG directory not found at ${EASYRAG_DIR}.${NC}\nNothing to uninstall.\n\n"
  exit 0
fi

# Stop containers
step "Stopping EasyRAG containers..."
cd "${EASYRAG_DIR}"
if [ -f "${COMPOSE_FILE}" ]; then
  docker compose -f "${COMPOSE_FILE}" down 2>&1 || true
  ok "Containers stopped"
else
  printf "  docker-compose.yml not found — skipping container stop\n"
fi

# Ask about data removal
echo ""
printf "${RED}Remove all EasyRAG data?${NC} This deletes your documents, vector index, and database.\n"
read -r -p "Type 'yes' to confirm, anything else to keep data: " confirm < /dev/tty

if [ "${confirm}" = "yes" ]; then
  step "Removing Docker volumes..."
  if [ -f "${COMPOSE_FILE}" ]; then
    docker compose -f "${COMPOSE_FILE}" down -v 2>&1 || true
    ok "Volumes removed"
  fi

  step "Removing install directory..."
  rm -rf "${EASYRAG_DIR}"
  ok "Directory removed"
else
  ok "Data preserved at ${EASYRAG_DIR}"
  echo "  To start again: cd ${EASYRAG_DIR} && docker compose -f ${COMPOSE_FILE} up -d"
fi

echo ""; printf "${BOLD}Uninstall complete.${NC}\n\n"
