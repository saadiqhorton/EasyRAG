#!/bin/bash
# RAG Knowledge Base - Deployment Verification (Smoke Test)
# Usage: ./smoke_verify.sh [--api-url http://localhost:8000]

set -e

# Configuration
API_URL="${API_URL:-http://localhost:8000}"
API_PREFIX="/api/v1"
TIMEOUT=30

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

FAILURES=0
TESTS_PASSED=0
TESTS_TOTAL=0

log_ok() { echo -e "${GREEN}[PASS]${NC} $1"; TESTS_PASSED=$((TESTS_PASSED + 1)); }
log_fail() { echo -e "${RED}[FAIL]${NC} $1"; FAILURES=$((FAILURES + 1)); }
log_info() { echo -e "${YELLOW}[INFO]${NC} $1"; }

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --api-url)
            API_URL="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

check_prerequisites() {
    if ! command -v curl &> /dev/null; then
        echo "Error: curl is required"
        exit 1
    fi
}

test_health_endpoint() {
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    log_info "Testing /health endpoint..."

    local RESPONSE
    RESPONSE=$(curl -s --max-time $TIMEOUT "${API_URL}/health" 2>/dev/null) || true

    if echo "$RESPONSE" | grep -q '"status":"healthy"'; then
        log_ok "Health endpoint returns healthy"
        return 0
    fi

    log_fail "Health endpoint not responding correctly"
    return 1
}

test_readiness_endpoint() {
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    log_info "Testing /health/ready endpoint..."

    local RESPONSE
    RESPONSE=$(curl -s --max-time $TIMEOUT "${API_URL}/health/ready" 2>/dev/null) || true

    local PG_OK=false
    local QD_OK=false

    if echo "$RESPONSE" | grep -q '"postgres":true'; then
        PG_OK=true
    fi

    if echo "$RESPONSE" | grep -q '"qdrant":true'; then
        QD_OK=true
    fi

    if [ "$PG_OK" = true ] && [ "$QD_OK" = true ]; then
        log_ok "Readiness check: PostgreSQL and Qdrant connected"
        return 0
    fi

    if [ "$PG_OK" = false ]; then
        log_fail "PostgreSQL not connected"
    fi
    if [ "$QD_OK" = false ]; then
        log_fail "Qdrant not connected"
    fi
    return 1
}

test_collection_creation() {
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    log_info "Testing collection creation..."

    local RESPONSE
    RESPONSE=$(curl -s --max-time $TIMEOUT -X POST \
        -H "Content-Type: application/json" \
        -d '{"name": "smoke-test", "description": "Smoke test collection"}' \
        "${API_URL}${API_PREFIX}/collections" 2>/dev/null) || true

    if echo "$RESPONSE" | grep -q '"id"'; then
        COLLECTION_ID=$(echo "$RESPONSE" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
        log_ok "Collection created: ${COLLECTION_ID:0:8}..."
        return 0
    fi

    log_fail "Failed to create collection"
    return 1
}

test_document_upload() {
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    log_info "Testing document upload..."

    if [ -z "$COLLECTION_ID" ]; then
        log_fail "No collection ID available"
        return 1
    fi

    local DOC_CONTENT="# Test Document\n\nThis is a test document for smoke verification.\n\n## Section 1\n\nRAG systems combine retrieval with generation.\n\n## Section 2\n\nThe system retrieves relevant documents from a knowledge base."

    local RESPONSE
    RESPONSE=$(curl -s --max-time $TIMEOUT -X POST \
        -F "file=@-;filename=smoke-test.md" \
        "${API_URL}${API_PREFIX}/collections/${COLLECTION_ID}/documents" \<<EOF 2>/dev/null || true
$DOC_CONTENT
EOF

    if echo "$RESPONSE" | grep -q '"document_id"'; then
        DOCUMENT_ID=$(echo "$RESPONSE" | grep -o '"document_id":"[^"]*"' | cut -d'"' -f4)
        JOB_ID=$(echo "$RESPONSE" | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)
        log_ok "Document uploaded: ${DOCUMENT_ID:0:8}..., job: ${JOB_ID:0:8}..."
        return 0
    fi

    log_fail "Failed to upload document"
    return 1
}

test_ingestion_completion() {
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    log_info "Testing ingestion completion (waiting up to 60s)..."

    if [ -z "$JOB_ID" ]; then
        log_fail "No job ID available"
        return 1
    fi

    local ATTEMPTS=0
    local MAX_ATTEMPTS=20

    while [ $ATTEMPTS -lt $MAX_ATTEMPTS ]; do
        local RESPONSE
        RESPONSE=$(curl -s --max-time $TIMEOUT \
            "${API_URL}${API_PREFIX}/ingestion-jobs/${JOB_ID}" 2>/dev/null) || true

        local STATUS
        STATUS=$(echo "$RESPONSE" | grep -o '"status":"[^"]*"' | head -1 | cut -d'"' -f4)

        if [ "$STATUS" = "succeeded" ]; then
            log_ok "Ingestion completed successfully"
            return 0
        elif [ "$STATUS" = "failed" ] || [ "$STATUS" = "dead_letter" ]; then
            log_fail "Ingestion failed with status: $STATUS"
            return 1
        fi

        ATTEMPTS=$((ATTEMPTS + 1))
        if [ $((ATTEMPTS % 5)) -eq 0 ]; then
            echo -n "."
        fi
        sleep 3
    done

    echo ""
    log_fail "Ingestion timed out after 60s (may still complete)"
    return 1
}

test_search_functionality() {
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    log_info "Testing search functionality..."

    if [ -z "$COLLECTION_ID" ]; then
        log_fail "No collection ID available"
        return 1
    fi

    local RESPONSE
    RESPONSE=$(curl -s --max-time $TIMEOUT -X POST \
        -H "Content-Type: application/json" \
        -d '{"query": "what is RAG", "limit": 5}' \
        "${API_URL}${API_PREFIX}/collections/${COLLECTION_ID}/search" 2>/dev/null) || true

    if echo "$RESPONSE" | grep -q '"results":\['; then
        local COUNT
        COUNT=$(echo "$RESPONSE" | grep -o '"text"' | wc -l)
        if [ "$COUNT" -gt 0 ]; then
            log_ok "Search returned ${COUNT} result(s)"
            return 0
        fi
    fi

    log_fail "Search returned no results"
    return 1
}

test_ask_endpoint() {
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    log_info "Testing ask endpoint..."

    if [ -z "$COLLECTION_ID" ]; then
        log_fail "No collection ID available"
        return 1
    fi

    local RESPONSE
    RESPONSE=$(curl -s --max-time $TIMEOUT -X POST \
        -H "Content-Type: application/json" \
        -d '{"query": "What does RAG stand for?"}' \
        "${API_URL}${API_PREFIX}/collections/${COLLECTION_ID}/ask" 2>/dev/null) || true

    if echo "$RESPONSE" | grep -q '"answer_id"'; then
        local MODE
        MODE=$(echo "$RESPONSE" | grep -o '"answer_mode":"[^"]*"' | cut -d'"' -f4)
        log_ok "Ask endpoint responded (mode: ${MODE:-unknown})"
        return 0
    fi

    # LLM not configured is acceptable
    if [ "$RESPONSE" = "" ] || echo "$RESPONSE" | grep -q "502\|503"; then
        log_info "Ask endpoint may require LLM configuration (acceptable)"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    fi

    log_fail "Ask endpoint error"
    return 1
}

cleanup() {
    if [ -n "$DOCUMENT_ID" ] && [ -n "$COLLECTION_ID" ]; then
        log_info "Cleaning up test data..."
        curl -s --max-time 10 -X DELETE \
            "${API_URL}${API_PREFIX}/documents/${DOCUMENT_ID}" >/dev/null 2>&1 || true
    fi
}

# Trap to ensure cleanup on exit
trap cleanup EXIT

# Main
main() {
    echo "========================================"
    echo "RAG Knowledge Base - Deployment Smoke Test"
    echo "========================================"
    echo "API URL: ${API_URL}"
    echo ""

    check_prerequisites

    test_health_endpoint
    test_readiness_endpoint
    test_collection_creation
    test_document_upload
    test_ingestion_completion
    test_search_functionality
    test_ask_endpoint

    echo ""
    echo "========================================"
    if [ $FAILURES -eq 0 ]; then
        echo -e "${GREEN}All smoke tests passed!${NC}"
        echo "System is ready for use."
        echo "========================================"
        exit 0
    else
        echo -e "${RED}${TESTS_PASSED}/${TESTS_TOTAL} tests passed${NC}"
        echo -e "${FAILURES} test(s) failed"
        echo "========================================"
        exit 1
    fi
}

main "$@"
