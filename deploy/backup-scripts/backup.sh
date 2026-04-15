#!/bin/bash
# RAG KB Full Backup Script
# Backs up PostgreSQL, Qdrant snapshots, and document storage

set -e

# Configuration
BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/ragkb}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-ragkb}"
POSTGRES_DB="${POSTGRES_DB:-ragkb}"
QDRANT_HOST="${QDRANT_HOST:-localhost}"
QDRANT_PORT="${QDRANT_PORT:-6333}"
QDRANT_COLLECTION="${QDRANT_COLLECTION:-rag_kb_chunks}"
STORAGE_PATH="${STORAGE_PATH:-/var/lib/ragkb/storage}"

# Timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$BACKUP_ROOT/$TIMESTAMP"

# Logging
LOG_FILE="$BACKUP_DIR/backup.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] INFO:${NC} $1" | tee -a "$LOG_FILE"
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARN:${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" | tee -a "$LOG_FILE"
}

# Create backup directory
mkdir -p "$BACKUP_DIR"
touch "$LOG_FILE"

log "Starting backup to $BACKUP_DIR"

# Track success/failure
BACKUP_SUCCESS=true
BACKUP_COMPONENTS=()

# =============================================================================
# 1. PostgreSQL Backup
# =============================================================================
log "Backing up PostgreSQL database..."

if command -v pg_dump &> /dev/null; then
    PGDUMP_CMD="pg_dump"
elif command -v docker &> /dev/null && docker ps | grep -q postgres; then
    PGDUMP_CMD="docker exec -i ragkb-postgres-1 pg_dump"
else
    error "pg_dump not found and no Docker PostgreSQL container detected"
    BACKUP_SUCCESS=false
fi

if [ -n "$PGDUMP_CMD" ]; then
    $PGDUMP_CMD -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
        --verbose --blobs 2>> "$LOG_FILE" | gzip > "$BACKUP_DIR/postgres.sql.gz"

    if [ $? -eq 0 ]; then
        log "PostgreSQL backup completed: postgres.sql.gz"
        BACKUP_COMPONENTS+=("postgres")
    else
        error "PostgreSQL backup failed"
        BACKUP_SUCCESS=false
    fi
fi

# =============================================================================
# 2. Qdrant Snapshot
# =============================================================================
log "Creating Qdrant snapshot..."

if curl -s "http://$QDRANT_HOST:$QDRANT_PORT/collections" > /dev/null; then
    # Create snapshot
    SNAPSHOT_RESPONSE=$(curl -s -X POST "http://$QDRANT_HOST:$QDRANT_PORT/collections/$QDRANT_COLLECTION/snapshots")

    if echo "$SNAPSHOT_RESPONSE" | grep -q "snapshot_name"; then
        SNAPSHOT_NAME=$(echo "$SNAPSHOT_RESPONSE" | grep -o '"snapshot_name":"[^"]*"' | cut -d'"' -f4)
        log "Qdrant snapshot created: $SNAPSHOT_NAME"

        # Download snapshot
        sleep 2  # Wait for snapshot to be ready
        curl -s -o "$BACKUP_DIR/qdrant.snapshot" \
            "http://$QDRANT_HOST:$QDRANT_PORT/collections/$QDRANT_COLLECTION/snapshots/$SNAPSHOT_NAME"

        if [ -f "$BACKUP_DIR/qdrant.snapshot" ] && [ -s "$BACKUP_DIR/qdrant.snapshot" ]; then
            log "Qdrant snapshot downloaded: qdrant.snapshot"
            BACKUP_COMPONENTS+=("qdrant")
        else
            error "Failed to download Qdrant snapshot"
            rm -f "$BACKUP_DIR/qdrant.snapshot"
            BACKUP_SUCCESS=false
        fi
    else
        error "Qdrant snapshot creation failed: $SNAPSHOT_RESPONSE"
        BACKUP_SUCCESS=false
    fi
else
    warn "Qdrant not available at $QDRANT_HOST:$QDRANT_PORT, skipping Qdrant backup"
    BACKUP_SUCCESS=false
fi

# =============================================================================
# 3. Document Storage Backup
# =============================================================================
log "Backing up document storage..."

if [ -d "$STORAGE_PATH" ]; then
    tar czf "$BACKUP_DIR/storage.tar.gz" -C "$STORAGE_PATH" . 2>> "$LOG_FILE"

    if [ $? -eq 0 ]; then
        log "Storage backup completed: storage.tar.gz"
        BACKUP_COMPONENTS+=("storage")
    else
        error "Storage backup failed"
        BACKUP_SUCCESS=false
    fi
else
    warn "Storage path not found: $STORAGE_PATH, skipping storage backup"
fi

# =============================================================================
# 4. Configuration Backup
# =============================================================================
log "Backing up configuration..."

# Backup environment files if they exist
for env_file in /opt/ragkb/.env /opt/ragkb/.env.production; do
    if [ -f "$env_file" ]; then
        cp "$env_file" "$BACKUP_DIR/"
        log "Configuration backed up: $(basename $env_file)"
        BACKUP_COMPONENTS+=("config")
    fi
done

# Backup systemd services if they exist
if [ -d "/etc/systemd/system" ]; then
    tar czf "$BACKUP_DIR/systemd.tar.gz" -C "/etc/systemd/system" ragkb-*.service qdrant.service 2>/dev/null || true
    if [ -f "$BACKUP_DIR/systemd.tar.gz" ]; then
        log "Systemd services backed up"
        BACKUP_COMPONENTS+=("systemd")
    fi
fi

# =============================================================================
# 5. Backup Manifest
# =============================================================================
log "Creating backup manifest..."

cat > "$BACKUP_DIR/manifest.json" << EOF
{
  "backup_timestamp": "$TIMESTAMP",
  "backup_date_iso": "$(date -Iseconds)",
  "components": [$(IFS=,; echo "${BACKUP_COMPONENTS[*]}" | sed 's/[^ ]*/"&"/g')],
  "backup_success": $BACKUP_SUCCESS,
  "hostname": "$(hostname)",
  "version": "$(cat /opt/ragkb/version.txt 2>/dev/null || echo 'unknown')",
  "files": {
    "postgres": "postgres.sql.gz",
    "qdrant": "qdrant.snapshot",
    "storage": "storage.tar.gz",
    "config": ".env*",
    "systemd": "systemd.tar.gz"
  },
  "sizes": {
    "postgres": "$(du -h "$BACKUP_DIR/postgres.sql.gz" 2>/dev/null | cut -f1 || echo 'N/A')",
    "qdrant": "$(du -h "$BACKUP_DIR/qdrant.snapshot" 2>/dev/null | cut -f1 || echo 'N/A')",
    "storage": "$(du -h "$BACKUP_DIR/storage.tar.gz" 2>/dev/null | cut -f1 || echo 'N/A')"
  }
}
EOF

log "Backup manifest created: manifest.json"

# =============================================================================
# 6. Cleanup Old Backups
# =============================================================================
log "Cleaning up backups older than $RETENTION_DAYS days..."

DELETED_COUNT=$(find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -mtime +$RETENTION_DAYS -exec rm -rf {} + 2>/dev/null | wc -l)
log "Cleaned up $DELETED_COUNT old backup(s)"

# =============================================================================
# 7. Summary
# =============================================================================
BACKUP_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)

if $BACKUP_SUCCESS; then
    log "=========================================="
    log "BACKUP COMPLETED SUCCESSFULLY"
    log "=========================================="
    log "Backup location: $BACKUP_DIR"
    log "Backup size: $BACKUP_SIZE"
    log "Components: ${BACKUP_COMPONENTS[*]}"
    log "=========================================="
    exit 0
else
    error "=========================================="
    error "BACKUP COMPLETED WITH ERRORS"
    error "=========================================="
    error "Backup location: $BACKUP_DIR"
    error "Components successful: ${BACKUP_COMPONENTS[*]}"
    error "Check $LOG_FILE for details"
    error "=========================================="
    exit 1
fi
