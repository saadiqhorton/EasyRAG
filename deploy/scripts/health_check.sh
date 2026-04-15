#!/bin/bash
# RAG Knowledge Base - Health Check Script
# Usage: ./health_check.sh [--wait]
# Options:
#   --wait    Wait for services to become healthy instead of failing immediately

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Configuration
POSTGRES_URL="${POSTGRES_URL:-postgresql+asyncpg://ragkb:local_dev_password@localhost:5432/ragkb}"
QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
API_URL="${API_URL:-http://localhost:8000}"
MAX_WAIT_TIME="${MAX_WAIT_TIME:-120}"
POLL_INTERVAL="${POLL_INTERVAL:-5}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track failures
FAILURES=0
CHECK_TOTAL=0

log_ok() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    FAILURES=$((FAILURES + 1))
}

log_info() {
    echo -e "${YELLOW}[INFO]${NC} $1"
}

# Check if curl is available
if ! command -v curl &> /dev/null; then
    echo "Error: curl is required but not installed"
    exit 1
fi

check_postgres() {
    CHECK_TOTAL=$((CHECK_TOTAL + 1))
    log_info "Checking PostgreSQL..."

    if curl -s --max-time 5 "${API_URL}/health/ready" 2>/dev/null | grep -q '"postgres":true'; then
        log_ok "PostgreSQL is healthy (via API readiness check)"
        return 0
    fi

    # Try direct pg_isready if available
    if command -v pg_isready &> /dev/null; then
        if pg_isready -h localhost -p 5432 &>/dev/null; then
            log_ok "PostgreSQL is accepting connections"
            return 0
        fi
    fi

    # Try Docker health check
    if docker ps &>/dev/null && docker compose -f "${PROJECT_ROOT}/deploy/docker-compose.yml" ps postgres &>/dev/null 2>&1; then
        STATUS=$(docker inspect --format='{{.State.Health.Status}}' ragkb-postgres 2>/dev/null || echo "unknown")
        if [ "$STATUS" = "healthy" ]; then
            log_ok "PostgreSQL container is healthy"
            return 0
        else
            log_fail "PostgreSQL container status: $STATUS"
            return 1
        fi
    fi

    log_fail "PostgreSQL is not responding"
    return 1
}

check_qdrant() {
    CHECK_TOTAL=$((CHECK_TOTAL + 1))
    log_info "Checking Qdrant..."

    if curl -s --max-time 5 "${API_URL}/health/ready" 2>/dev/null | grep -q '"qdrant":true'; then
        log_ok "Qdrant is healthy (via API readiness check)"
        return 0
    fi

    # Try direct Qdrant health endpoint
    if curl -s --max-time 5 "${QDRANT_URL}/healthz" 2>/dev/null | grep -q "healthz check passed"; then
        log_ok "Qdrant is responding"
        return 0
    fi

    # Try Docker health check
    if docker ps &>/dev/null 2>&1 && docker compose -f "${PROJECT_ROOT}/deploy/docker-compose.yml" ps qdrant &>/dev/null 2>&1; then
        STATUS=$(docker inspect --format='{{.State.Health.Status}}' ragkb-qdrant 2>/dev/null || echo "unknown")
        if [ "$STATUS" = "healthy" ]; then
            log_ok "Qdrant container is healthy"
            return 0
        else
            log_fail "Qdrant container status: $STATUS"
            return 1
        fi
    fi

    log_fail "Qdrant is not responding"
    return 1
}

check_api() {
    CHECK_TOTAL=$((CHECK_TOTAL + 1))
    log_info "Checking API..."

    local RESPONSE
    RESPONSE=$(curl -s --max-time 10 "${API_URL}/health" 2>/dev/null)

    if echo "$RESPONSE" | grep -q '"status":"healthy"'; then
        log_ok "API is responding"
        local VERSION
        VERSION=$(echo "$RESPONSE" | grep -o '"version":"[^"]*"' | cut -d'"' -f4)
        log_info "API version: ${VERSION:-unknown}"
        return 0
    fi

    log_fail "API is not responding at ${API_URL}/health"
    return 1
}

check_api_ready() {
    CHECK_TOTAL=$((CHECK_TOTAL + 1))
    log_info "Checking API readiness..."

    local RESPONSE
    RESPONSE=$(curl -s --max-time 10 "${API_URL}/health/ready" 2>/dev/null)

    if echo "$RESPONSE" | grep -q '"postgres":true' && echo "$RESPONSE" | grep -q '"qdrant":true'; then
        log_ok "API is ready (all dependencies connected)"
        return 0
    fi

    log_fail "API is not ready"
    return 1
}

check_worker() {
    CHECK_TOTAL=$((CHECK_TOTAL + 1))
    log_info "Checking worker..."

    # Check if worker process exists
    if docker ps &>/dev/null 2>&1; then
        if docker compose -f "${PROJECT_ROOT}/deploy/docker-compose.yml" ps worker &>/dev/null 2>&1; then
            local STATUS
            STATUS=$(docker inspect --format='{{.State.Status}}' ragkb-worker 2>/dev/null || echo "unknown")
            if [ "$STATUS" = "running" ]; then
                log_ok "Worker container is running"
                return 0
            else
                log_fail "Worker container status: $STATUS"
                return 1
            fi
        fi
    fi

    # Check if worker process is running on host
    if pgrep -f "ingestion_worker" &>/dev/null; then
        log_ok "Worker process is running"
        return 0
    fi

    log_fail "Worker is not running"
    return 1
}

check_disk_space() {
    CHECK_TOTAL=$((CHECK_TOTAL + 1))
    log_info "Checking disk space..."

    local USAGE
    USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')

    if [ "$USAGE" -lt 85 ]; then
        log_ok "Disk usage: ${USAGE}%"
        return 0
    else
        log_fail "Disk usage critical: ${USAGE}%"
        return 1
    fi
}

wait_for_services() {
    log_info "Waiting up to ${MAX_WAIT_TIME}s for services to become healthy..."

    local ELAPSED=0
    local ALL_HEALTHY=0

    while [ $ELAPSED -lt $MAX_WAIT_TIME ]; do
        ALL_HEALTHY=1

        if ! check_postgres &>/dev/null; then
            ALL_HEALTHY=0
        fi

        if ! check_qdrant &>/dev/null; then
            ALL_HEALTHY=0
        fi

        if ! check_api &>/dev/null; then
            ALL_HEALTHY=0
        fi

        if [ $ALL_HEALTHY -eq 1 ]; then
            log_ok "All services are healthy"
            return 0
        fi

        sleep $POLL_INTERVAL
        ELAPSED=$((ELAPSED + POLL_INTERVAL))
        echo -n "."
    done

    echo ""
    log_fail "Timeout waiting for services"
    return 1
}

# Main
main() {
    echo "========================================"
    echo "RAG Knowledge Base - Health Check"
    echo "========================================"
    echo ""

    local WAIT_MODE=false

    # Parse arguments
    for arg in "$@"; do
        case $arg in
            --wait)
                WAIT_MODE=true
                shift
                ;;
            *)
                # Unknown argument
                ;;
        esac
    done

    if [ "$WAIT_MODE" = true ]; then
        wait_for_services
        exit $?
    fi

    # Run all checks
    check_postgres
    check_qdrant
    check_api
    check_api_ready
    check_worker
    check_disk_space

    echo ""
    echo "========================================"
    if [ $FAILURES -eq 0 ]; then
        echo -e "${GREEN}All checks passed${NC}"
        echo "========================================"
        exit 0
    else
        echo -e "${RED}${FAILURES}/${CHECK_TOTAL} checks failed${NC}"
        echo "========================================"
        exit 1
    fi
}

main "$@"
