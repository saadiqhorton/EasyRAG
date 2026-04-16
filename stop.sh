#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────
# EasyRAG — Stop all services (no-Docker)
# ────────────────────────────────────────────────────────────────
set -euo pipefail

EASYRAG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="${EASYRAG_DIR}/.pids"

stop_service() {
  local name="$1"
  local pid_file="${PID_DIR}/${name}.pid"

  if [ ! -f "$pid_file" ]; then
    echo "  ${name}: not running"
    return
  fi

  local pid
  pid=$(cat "$pid_file")

  if kill -0 "$pid" 2>/dev/null; then
    echo "  Stopping ${name} (PID ${pid})..."
    kill "$pid" 2>/dev/null || true
    # Wait up to 10s for graceful shutdown
    for i in $(seq 1 10); do
      if ! kill -0 "$pid" 2>/dev/null; then
        break
      fi
      sleep 1
    done
    # Force kill if still running
    if kill -0 "$pid" 2>/dev/null; then
      kill -9 "$pid" 2>/dev/null || true
    fi
    echo "  ${name}: stopped"
  else
    echo "  ${name}: already stopped (stale PID)"
  fi
  rm -f "$pid_file"
}

echo "Stopping EasyRAG..."
stop_service frontend
stop_service worker
stop_service api
stop_service qdrant
echo ""
echo "All services stopped."
