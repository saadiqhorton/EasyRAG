#!/bin/bash
# RAG KB Backup Verification Script
# Verifies backup integrity without restoring

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"; }
error() { echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"; }

BACKUP_DIR=""
VERBOSE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose) VERBOSE=true; shift ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS] <backup-directory>"
            echo ""
            echo "Options:"
            echo "  -v, --verbose    Show detailed information"
            echo "  -h, --help       Show this help"
            exit 0
            ;;
        *) BACKUP_DIR="$1"; shift ;;
    esac
done

if [ -z "$BACKUP_DIR" ]; then
    error "No backup directory specified"
    exit 1
fi

if [ ! -d "$BACKUP_DIR" ]; then
    error "Backup directory not found: $BACKUP_DIR"
    exit 1
fi

log "Verifying backup: $BACKUP_DIR"

VERIFICATION_PASSED=true
ISSUES=()

# =============================================================================
# Check Manifest
# =============================================================================
if [ -f "$BACKUP_DIR/manifest.json" ]; then
    log "✓ Manifest file present"

    if $VERBOSE; then
        cat "$BACKUP_DIR/manifest.json" | python3 -m json.tool 2>/dev/null || cat "$BACKUP_DIR/manifest.json"
    fi

    # Validate JSON
    if python3 -c "import json; json.load(open('$BACKUP_DIR/manifest.json'))" 2>/dev/null; then
        log "✓ Manifest JSON valid"
    else
        error "✗ Manifest JSON invalid"
        ISSUES+=("manifest_json_invalid")
        VERIFICATION_PASSED=false
    fi
else
    warn "✗ Manifest file missing"
    ISSUES+=("manifest_missing")
fi

# =============================================================================
# Check PostgreSQL Backup
# =============================================================================
if [ -f "$BACKUP_DIR/postgres.sql.gz" ]; then
    log "✓ PostgreSQL backup present"

    # Check file is valid gzip
    if gzip -t "$BACKUP_DIR/postgres.sql.gz" 2>/dev/null; then
        log "✓ PostgreSQL backup is valid gzip"
    else
        error "✗ PostgreSQL backup is corrupted (invalid gzip)"
        ISSUES+=("postgres_corrupted")
        VERIFICATION_PASSED=false
    fi

    # Check file size
    PG_SIZE=$(stat -f%z "$BACKUP_DIR/postgres.sql.gz" 2>/dev/null || stat -c%s "$BACKUP_DIR/postgres.sql.gz" 2>/dev/null || echo "0")
    if [ "$PG_SIZE" -lt 100 ]; then
        warn "✗ PostgreSQL backup suspiciously small (${PG_SIZE} bytes)"
        ISSUES+=("postgres_too_small")
    else
        log "✓ PostgreSQL backup size: $(numfmt --to=iec $PG_SIZE 2>/dev/null || echo ${PG_SIZE} bytes)"
    fi
else
    warn "✗ PostgreSQL backup missing"
    ISSUES+=("postgres_missing")
fi

# =============================================================================
# Check Qdrant Backup
# =============================================================================
if [ -f "$BACKUP_DIR/qdrant.snapshot" ]; then
    log "✓ Qdrant snapshot present"

    # Check file is valid (Qdrant snapshots are tar archives)
    if file "$BACKUP_DIR/qdrant.snapshot" | grep -qE "(tar|POSIX|data)"; then
        log "✓ Qdrant snapshot file type valid"
    else
        warn "✗ Qdrant snapshot file type unexpected"
        ISSUES+=("qdrant_filetype_unexpected")
    fi

    QD_SIZE=$(stat -f%z "$BACKUP_DIR/qdrant.snapshot" 2>/dev/null || stat -c%s "$BACKUP_DIR/qdrant.snapshot" 2>/dev/null || echo "0")
    if [ "$QD_SIZE" -lt 100 ]; then
        warn "✗ Qdrant snapshot suspiciously small (${QD_SIZE} bytes)"
        ISSUES+=("qdrant_too_small")
    else
        log "✓ Qdrant snapshot size: $(numfmt --to=iec $QD_SIZE 2>/dev/null || echo ${QD_SIZE} bytes)"
    fi
else
    warn "✗ Qdrant snapshot missing"
    ISSUES+=("qdrant_missing")
fi

# =============================================================================
# Check Storage Backup
# =============================================================================
if [ -f "$BACKUP_DIR/storage.tar.gz" ]; then
    log "✓ Storage backup present"

    # Check file is valid gzip
    if gzip -t "$BACKUP_DIR/storage.tar.gz" 2>/dev/null; then
        log "✓ Storage backup is valid gzip"
    else
        error "✗ Storage backup is corrupted (invalid gzip)"
        ISSUES+=("storage_corrupted")
        VERIFICATION_PASSED=false
    fi

    ST_SIZE=$(stat -f%z "$BACKUP_DIR/storage.tar.gz" 2>/dev/null || stat -c%s "$BACKUP_DIR/storage.tar.gz" 2>/dev/null || echo "0")
    log "✓ Storage backup size: $(numfmt --to=iec $ST_SIZE 2>/dev/null || echo ${ST_SIZE} bytes)"
else
    warn "✗ Storage backup missing"
    ISSUES+=("storage_missing")
fi

# =============================================================================
# Check Log File
# =============================================================================
if [ -f "$BACKUP_DIR/backup.log" ]; then
    log "✓ Backup log present"

    if grep -q "BACKUP COMPLETED SUCCESSFULLY" "$BACKUP_DIR/backup.log"; then
        log "✓ Backup log indicates successful completion"
    elif grep -q "BACKUP COMPLETED WITH ERRORS" "$BACKUP_DIR/backup.log"; then
        error "✗ Backup log indicates errors during backup"
        ISSUES+=("backup_had_errors")
    fi
else
    warn "✗ Backup log missing"
fi

# =============================================================================
# Summary
# =============================================================================
echo ""
if $VERIFICATION_PASSED; then
    log "=========================================="
    log "VERIFICATION PASSED"
    log "=========================================="
    if [ ${#ISSUES[@]} -gt 0 ]; then
        warn "Warnings (non-critical): ${ISSUES[*]}"
    fi
    exit 0
else
    error "=========================================="
    error "VERIFICATION FAILED"
    error "=========================================="
    error "Issues found: ${ISSUES[*]}"
    exit 1
fi
