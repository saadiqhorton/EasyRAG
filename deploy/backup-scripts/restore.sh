#!/bin/bash
# RAG KB Restore Script
# Restores from a backup created by backup.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration defaults
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-ragkb}"
POSTGRES_DB="${POSTGRES_DB:-ragkb}"
QDRANT_HOST="${QDRANT_HOST:-localhost}"
QDRANT_PORT="${QDRANT_PORT:-6333}"
QDRANT_COLLECTION="${QDRANT_COLLECTION:-rag_kb_chunks}"
STORAGE_PATH="${STORAGE_PATH:-/var/lib/ragkb/storage}"

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] INFO:${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARN:${NC} $1"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

info() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')] INFO:${NC} $1"
}

# =============================================================================
# Usage
# =============================================================================
usage() {
    cat << EOF
RAG KB Restore Script

Usage: $0 [OPTIONS] <backup-directory|backup-timestamp>

Options:
    -c, --component COMPONENT    Restore only specific component (postgres|qdrant|storage|all)
    -f, --force                  Skip confirmation prompts (DANGEROUS)
    -d, --dry-run                Show what would be restored without doing it
    -h, --help                   Show this help message

Examples:
    $0 20240115_120000           # Restore from specific backup
    $0 /var/backups/ragkb/20240115_120000
    $0 --component postgres 20240115_120000
    $0 --dry-run 20240115_120000

Components:
    postgres    - Database contents (destructive - replaces current data)
    qdrant      - Vector index (destructive - replaces current collection)
    storage     - Document files (merges with existing, overwrites conflicts)
    all         - Everything (default)

WARNING: This script can DESTROY data. Always verify backups before restoring.
EOF
}

# =============================================================================
# Parse Arguments
# =============================================================================
COMPONENT="all"
FORCE=false
DRY_RUN=false
BACKUP_INPUT=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--component)
            COMPONENT="$2"
            shift 2
            ;;
        -f|--force)
            FORCE=true
            shift
            ;;
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        -*)
            error "Unknown option: $1"
            usage
            exit 1
            ;;
        *)
            BACKUP_INPUT="$1"
            shift
            ;;
    esac
done

if [ -z "$BACKUP_INPUT" ]; then
    error "No backup specified"
    usage
    exit 1
fi

# Resolve backup directory
if [ -d "$BACKUP_INPUT" ]; then
    BACKUP_DIR="$BACKUP_INPUT"
else
    # Assume it's a timestamp in the default location
    BACKUP_DIR="/var/backups/ragkb/$BACKUP_INPUT"
fi

if [ ! -d "$BACKUP_DIR" ]; then
    error "Backup directory not found: $BACKUP_DIR"
    exit 1
fi

# Check for manifest
if [ ! -f "$BACKUP_DIR/manifest.json" ]; then
    warn "No manifest found in backup. Proceeding with caution."
else
    info "Backup manifest found"
    info "Backup date: $(grep -o '"backup_date_iso":"[^"]*"' "$BACKUP_DIR/manifest.json" | cut -d'"' -f4 || echo 'unknown')"
    info "Components: $(grep -o '"components":\[[^]]*\]' "$BACKUP_DIR/manifest.json" | sed 's/.*\[\(.*\)\].*/\1/' | tr ',' ' ' | sed 's/"//g')"
fi

# =============================================================================
# Dry Run Mode
# =============================================================================
if $DRY_RUN; then
    info "DRY RUN MODE - No changes will be made"
    info "Backup directory: $BACKUP_DIR"
    info "Component to restore: $COMPONENT"

    echo ""
    info "Files in backup:"
    ls -lh "$BACKUP_DIR"

    echo ""
    info "Would restore:"
    if [ "$COMPONENT" = "all" ] || [ "$COMPONENT" = "postgres" ]; then
        if [ -f "$BACKUP_DIR/postgres.sql.gz" ]; then
            info "  - PostgreSQL database (destructive)"
        fi
    fi
    if [ "$COMPONENT" = "all" ] || [ "$COMPONENT" = "qdrant" ]; then
        if [ -f "$BACKUP_DIR/qdrant.snapshot" ]; then
            info "  - Qdrant vector index (destructive)"
        fi
    fi
    if [ "$COMPONENT" = "all" ] || [ "$COMPONENT" = "storage" ]; then
        if [ -f "$BACKUP_DIR/storage.tar.gz" ]; then
            info "  - Document storage (merge mode)"
        fi
    fi

    exit 0
fi

# =============================================================================
# Confirmation Prompts
# =============================================================================
if ! $FORCE; then
    echo ""
    warn "=========================================="
    warn "WARNING: This will restore data from:"
    warn "$BACKUP_DIR"
    warn "=========================================="

    if [ "$COMPONENT" = "all" ] || [ "$COMPONENT" = "postgres" ]; then
        warn "PostgreSQL restore will DESTROY current database data"
    fi
    if [ "$COMPONENT" = "all" ] || [ "$COMPONENT" = "qdrant" ]; then
        warn "Qdrant restore will DESTROY current vector index"
    fi

    echo ""
    read -p "Are you sure you want to continue? [yes/N]: " confirm
    if [ "$confirm" != "yes" ]; then
        info "Restore cancelled"
        exit 0
    fi

    echo ""
    read -p "Have you verified this backup is correct? [yes/N]: " confirm2
    if [ "$confirm2" != "yes" ]; then
        info "Restore cancelled"
        exit 0
    fi
fi

# =============================================================================
# Restore Functions
# =============================================================================

restore_postgres() {
    log "Restoring PostgreSQL database..."

    if [ ! -f "$BACKUP_DIR/postgres.sql.gz" ]; then
        error "PostgreSQL backup not found: $BACKUP_DIR/postgres.sql.gz"
        return 1
    fi

    # Check PostgreSQL connectivity
    if command -v psql &> /dev/null; then
        PSQL_CMD="psql"
    elif command -v docker &> /dev/null; then
        PSQL_CMD="docker exec -i ragkb-postgres-1 psql"
    else
        error "psql not found"
        return 1
    fi

    if ! $PSQL_CMD -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1" > /dev/null 2>&1; then
        error "Cannot connect to PostgreSQL"
        return 1
    fi

    # Confirm destructive operation
    if ! $FORCE; then
        read -p "This will DROP and recreate the database. Continue? [yes/N]: " confirm
        if [ "$confirm" != "yes" ]; then
            warn "PostgreSQL restore skipped"
            return 1
        fi
    fi

    # Drop and recreate database
    log "Dropping and recreating database..."
    $PSQL_CMD -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" postgres << EOF
DROP DATABASE IF EXISTS $POSTGRES_DB;
CREATE DATABASE $POSTGRES_DB OWNER $POSTGRES_USER;
EOF

    # Restore
    log "Restoring database from backup..."
    gunzip -c "$BACKUP_DIR/postgres.sql.gz" | $PSQL_CMD -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB"

    if [ $? -eq 0 ]; then
        log "PostgreSQL restore completed successfully"
        return 0
    else
        error "PostgreSQL restore failed"
        return 1
    fi
}

restore_qdrant() {
    log "Restoring Qdrant vector index..."

    if [ ! -f "$BACKUP_DIR/qdrant.snapshot" ]; then
        error "Qdrant backup not found: $BACKUP_DIR/qdrant.snapshot"
        return 1
    fi

    # Check Qdrant connectivity
    if ! curl -s "http://$QDRANT_HOST:$QDRANT_PORT/collections" > /dev/null; then
        error "Cannot connect to Qdrant"
        return 1
    fi

    # Confirm destructive operation
    if ! $FORCE; then
        read -p "This will DELETE the current collection and recreate it. Continue? [yes/N]: " confirm
        if [ "$confirm" != "yes" ]; then
            warn "Qdrant restore skipped"
            return 1
        fi
    fi

    # Delete existing collection
    log "Deleting existing collection..."
    curl -s -X DELETE "http://$QDRANT_HOST:$QDRANT_PORT/collections/$QDRANT_COLLECTION" > /dev/null

    # Create new collection (will be populated from snapshot)
    log "Creating collection..."
    curl -s -X PUT "http://$QDRANT_HOST:$QDRANT_PORT/collections/$QDRANT_COLLECTION" \
        -H "Content-Type: application/json" \
        -d '{
            "vectors": {
                "size": 384,
                "distance": "Cosine"
            }
        }' > /dev/null

    # Upload and restore snapshot
    log "Uploading snapshot..."
    SNAPSHOT_RESPONSE=$(curl -s -X POST "http://$QDRANT_HOST:$QDRANT_PORT/collections/$QDRANT_COLLECTION/snapshots/upload" \
        -H "Content-Type: multipart/form-data" \
        -F "snapshot=@$BACKUP_DIR/qdrant.snapshot")

    if echo "$SNAPSHOT_RESPONSE" | grep -q "result"; then
        log "Qdrant restore completed successfully"
        return 0
    else
        error "Qdrant restore failed: $SNAPSHOT_RESPONSE"
        return 1
    fi
}

restore_storage() {
    log "Restoring document storage..."

    if [ ! -f "$BACKUP_DIR/storage.tar.gz" ]; then
        error "Storage backup not found: $BACKUP_DIR/storage.tar.gz"
        return 1
    fi

    # Check storage path
    if [ ! -d "$STORAGE_PATH" ]; then
        log "Creating storage directory: $STORAGE_PATH"
        mkdir -p "$STORAGE_PATH"
    fi

    # Extract (merges with existing, overwrites conflicts)
    log "Extracting storage backup..."
    tar xzf "$BACKUP_DIR/storage.tar.gz" -C "$STORAGE_PATH"

    # Fix ownership
    if id "ragkb" &>/dev/null; then
        chown -R ragkb:ragkb "$STORAGE_PATH"
    fi

    log "Storage restore completed successfully"
    return 0
}

# =============================================================================
# Execute Restore
# =============================================================================
RESTORE_SUCCESS=true

if [ "$COMPONENT" = "all" ] || [ "$COMPONENT" = "postgres" ]; then
    if ! restore_postgres; then
        RESTORE_SUCCESS=false
    fi
fi

if [ "$COMPONENT" = "all" ] || [ "$COMPONENT" = "qdrant" ]; then
    if ! restore_qdrant; then
        RESTORE_SUCCESS=false
    fi
fi

if [ "$COMPONENT" = "all" ] || [ "$COMPONENT" = "storage" ]; then
    if ! restore_storage; then
        RESTORE_SUCCESS=false
    fi
fi

# =============================================================================
# Summary
# =============================================================================
echo ""
if $RESTORE_SUCCESS; then
    log "=========================================="
    log "RESTORE COMPLETED SUCCESSFULLY"
    log "=========================================="
    log "Source: $BACKUP_DIR"
    log "Components: $COMPONENT"
    log "=========================================="
    exit 0
else
    error "=========================================="
    error "RESTORE COMPLETED WITH ERRORS"
    error "=========================================="
    error "Some components may not have been restored"
    exit 1
fi
