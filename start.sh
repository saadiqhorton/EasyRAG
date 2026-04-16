#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────
# EasyRAG — Start all services (no-Docker)
# ────────────────────────────────────────────────────────────────
set -euo pipefail

EASYRAG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${EASYRAG_DIR}"

# Load .env if present
if [ -f .env ]; then
  set -a; source .env; set +a
fi

# Resolve key settings
QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
API_PORT="${API_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
DATA_DIR="${EASYRAG_DIR}/data"
LOG_DIR="${EASYRAG_DIR}/logs"
PID_DIR="${EASYRAG_DIR}/.pids"

mkdir -p "${DATA_DIR}" "${LOG_DIR}" "${PID_DIR}"

# ── Functions ──────────────────────────────────────────────────
is_running() {
  local pid_file="$1"
  [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null
}

start_qdrant() {
  local pid_file="${PID_DIR}/qdrant.pid"
  if is_running "$pid_file"; then
    echo "Qdrant already running (PID $(cat "$pid_file"))"
    return
  fi

  local qdrant_bin="${EASYRAG_DIR}/bin/qdrant"
  if [ ! -f "$qdrant_bin" ]; then
    echo "ERROR: Qdrant binary not found at ${qdrant_bin}"
    echo "Run install.sh first, or place the qdrant binary in ${EASYRAG_DIR}/bin/"
    return 1
  fi

  echo "Starting Qdrant..."
  QDRANT__STORAGE__STORAGE_PATH="${DATA_DIR}/qdrant" \
    QDRANT__SERVICE__HTTP_PORT=6333 \
    QDRANT__SERVICE__GRPC_PORT=6334 \
    "$qdrant_bin" &> "${LOG_DIR}/qdrant.log" &
  echo $! > "$pid_file"

  # Wait for Qdrant health
  for i in $(seq 1 30); do
    if curl -sf --max-time 2 http://localhost:6333/healthz &>/dev/null; then
      echo "Qdrant ready on :6333"
      return
    fi
    sleep 1
  done
  echo "WARNING: Qdrant not healthy after 30s — check ${LOG_DIR}/qdrant.log"
}

start_api() {
  local pid_file="${PID_DIR}/api.pid"
  if is_running "$pid_file"; then
    echo "API already running (PID $(cat "$pid_file"))"
    return
  fi

  echo "Starting API..."
  cd "${EASYRAG_DIR}/app/backend"

  # Build DATABASE_URL for SQLite if not set
  export DATABASE_URL="${DATABASE_URL:-sqlite+aiosqlite:///${EASYRAG_DIR}/easyrag.db}"
  export QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
  export STORAGE_PATH="${EASYRAG_DIR}/data/storage"
  export CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:${FRONTEND_PORT}}"

  # Run migrations first
  "${EASYRAG_DIR}/.venv/bin/python" -m alembic upgrade head 2>> "${LOG_DIR}/api.log" || true

  # Start API
  "${EASYRAG_DIR}/.venv/bin/uvicorn" app.backend.main:app \
    --host 0.0.0.0 --port "${API_PORT}" \
    &>> "${LOG_DIR}/api.log" &
  echo $! > "$pid_file"
  cd "${EASYRAG_DIR}"

  # Wait for API health
  for i in $(seq 1 60); do
    if curl -sf --max-time 2 "http://localhost:${API_PORT}/health" &>/dev/null; then
      echo "API ready on :${API_PORT}"
      return
    fi
    sleep 1
  done
  echo "WARNING: API not healthy after 60s — check ${LOG_DIR}/api.log"
}

start_worker() {
  local pid_file="${PID_DIR}/worker.pid"
  if is_running "$pid_file"; then
    echo "Worker already running (PID $(cat "$pid_file"))"
    return
  fi

  echo "Starting worker..."
  cd "${EASYRAG_DIR}/app/backend"

  export DATABASE_URL="${DATABASE_URL:-sqlite+aiosqlite:///${EASYRAG_DIR}/easyrag.db}"
  export QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
  export STORAGE_PATH="${EASYRAG_DIR}/data/storage"

  "${EASYRAG_DIR}/.venv/bin/python" -m app.backend.workers.ingestion_worker \
    &>> "${LOG_DIR}/worker.log" &
  echo $! > "$pid_file"
  cd "${EASYRAG_DIR}"
  echo "Worker started"
}

start_frontend() {
  local pid_file="${PID_DIR}/frontend.pid"
  if is_running "$pid_file"; then
    echo "Frontend already running (PID $(cat "$pid_file"))"
    return
  fi

  local frontend_dir="${EASYRAG_DIR}/app/frontend"
  if [ -d "${frontend_dir}/.next/standalone" ]; then
    echo "Starting frontend (standalone)..."
    cd "${frontend_dir}"
    PORT="${FRONTEND_PORT}" HOSTNAME="0.0.0.0" \
      node .next/standalone/server.js \
      &>> "${LOG_DIR}/frontend.log" &
    echo $! > "$pid_file"
    cd "${EASYRAG_DIR}"
  elif [ -d "${frontend_dir}" ] && command -v npm &>/dev/null; then
    echo "Starting frontend (dev mode)..."
    cd "${frontend_dir}"
    PORT="${FRONTEND_PORT}" npm start \
      &>> "${LOG_DIR}/frontend.log" &
    echo $! > "$pid_file"
    cd "${EASYRAG_DIR}"
  else
    echo "WARNING: Frontend not available — skipping"
    return
  fi

  # Wait for frontend
  for i in $(seq 1 30); do
    if curl -sf --max-time 2 -o /dev/null "http://localhost:${FRONTEND_PORT}" &>/dev/null; then
      echo "Frontend ready on :${FRONTEND_PORT}"
      return
    fi
    sleep 1
  done
  echo "WARNING: Frontend not responding after 30s — check ${LOG_DIR}/frontend.log"
}

# ── Main ────────────────────────────────────────────────────────
echo ""
echo "Starting EasyRAG..."
echo ""

start_qdrant
start_api
start_worker
start_frontend

echo ""
echo "EasyRAG is running."
echo "  Frontend:  http://localhost:${FRONTEND_PORT}"
echo "  API:       http://localhost:${API_PORT}"
echo ""
echo "  Logs:       ${LOG_DIR}/"
echo "  Stop:       bash ${EASYRAG_DIR}/stop.sh"
echo ""
