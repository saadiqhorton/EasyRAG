# Production Paths and Infrastructure

## Overview

This document defines the standard production paths for the RAG Knowledge Base Framework and provides guidance for production deployment.

## Directory Structure

```
/opt/ragkb/                    # Application installation
├── .env                       # Environment configuration (secrets)
├── app/                       # Application code
├── venv/                      # Python virtual environment
└── scripts/                   # Operational scripts

/var/lib/qdrant/               # Qdrant vector database data
├── storage/                   # Collection data
└── snapshots/                 # Backup snapshots

/var/lib/ragkb/storage/        # Document uploads and derived assets
├── {collection_id}/           # Collection-scoped storage
│   └── {document_id}/         # Document-scoped storage
│       └── {version_id}/       # Version-scoped storage
│           └── {filename}      # Original file
│           └── _derived/       # Normalized exports

/var/cache/ragkb/models/       # HuggingFace model cache
├── sentence-transformers/     # Embedding models
└── cross-encoder/              # Reranker models

/var/log/ragkb/                # Application logs
├── api.log                    # API server logs
├── worker.log                 # Ingestion worker logs
└── qdrant.log                 # Qdrant logs (if not using systemd journal)

/etc/ragkb/                    # Configuration files
└── qdrant_config.yaml        # Qdrant configuration

/usr/local/bin/                # System binaries
└── qdrant                     # Qdrant binary

/etc/systemd/system/           # Systemd services
├── ragkb-api.service         # API service unit
├── ragkb-worker.service      # Worker service unit
└── qdrant.service            # Qdrant service unit
```

## Environment Variables

### Storage Paths

| Variable | Development | Production |
|----------|-------------|------------|
| `STORAGE_PATH` | `./storage` | `/var/lib/ragkb/storage` |
| `QDRANT_STORAGE` | `/tmp/qdrant` | `/var/lib/qdrant` |
| `MODEL_CACHE` | `~/.cache/huggingface` | `/var/cache/ragkb/models` |
| `LOG_DIR` | `./logs` | `/var/log/ragkb` |

### Path Configuration

Production `.env` file:

```bash
# Storage - production paths
STORAGE_PATH=/var/lib/ragkb/storage

# Qdrant - configured in /etc/qdrant/config.yaml
# The systemd service sets --config-path

# Model cache - use persistent location
HF_HOME=/var/cache/ragkb/models
TRANSFORMERS_CACHE=/var/cache/ragkb/models
```

## Migration from Development to Production

### 1. Move Qdrant Binary

```bash
# Development (temporary)
/tmp/qdrant

# Production (persistent)
sudo mv /tmp/qdrant /usr/local/bin/qdrant
sudo chmod +x /usr/local/bin/qdrant
sudo chown root:root /usr/local/bin/qdrant
```

### 2. Move Qdrant Data

```bash
# Create persistent storage
sudo mkdir -p /var/lib/qdrant
sudo chown -R qdrant:qdrant /var/lib/qdrant

# Migrate data (if any existing)
sudo cp -r /tmp/qdrant-storage/* /var/lib/qdrant/ 2>/dev/null || true
```

### 3. Move Application Storage

```bash
# Create persistent storage
sudo mkdir -p /var/lib/ragkb/storage
sudo chown -R ragkb:ragkb /var/lib/ragkb/storage

# Update app environment
# STORAGE_PATH=/var/lib/ragkb/storage
```

### 4. Setup Model Cache

```bash
# Create persistent cache
sudo mkdir -p /var/cache/ragkb/models
sudo chown -R ragkb:ragkb /var/cache/ragkb/models

# Pre-download models
sudo -u ragkb HF_HOME=/var/cache/ragkb/models \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"
```

## Service Startup Dependencies

### Correct Startup Order

1. **PostgreSQL** - Database must be ready first
2. **Qdrant** - Vector store must be available
3. **API Server** - Depends on both PostgreSQL and Qdrant
4. **Worker** - Depends on PostgreSQL, Qdrant, and API (for health)

### Systemd Dependency Configuration

```ini
# ragkb-api.service
[Unit]
After=network.target postgresql.service qdrant.service
Wants=postgresql.service qdrant.service

# ragkb-worker.service
[Unit]
After=network.target postgresql.service qdrant.service ragkb-api.service
Wants=postgresql.service qdrant.service ragkb-api.service
```

## Backup Strategy

### What to Backup

| Path | Priority | Frequency |
|------|----------|-----------|
| `/var/lib/qdrant` | Critical | Daily |
| `/var/lib/ragkb/storage` | High | Daily |
| PostgreSQL database | Critical | Hourly |
| `/var/cache/ragkb/models` | Low | Weekly |

### Automated Backup Script

```bash
#!/bin/bash
# /etc/cron.daily/ragkb-backup

BACKUP_DIR="/var/backups/ragkb/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

# PostgreSQL backup
docker compose exec -T postgres pg_dump -U ragkb ragkb \
  | gzip > "$BACKUP_DIR/postgres.sql.gz"

# Qdrant snapshot
curl -X POST http://localhost:6333/collections/rag_kb_chunks/snapshots

# Storage backup
tar czf "$BACKUP_DIR/storage.tar.gz" /var/lib/ragkb/storage

# Cleanup old backups (keep 7 days)
find /var/backups/ragkb -type d -mtime +7 -exec rm -rf {} + 2>/dev/null
```

## Security Hardening

### File Permissions

```bash
# Application files
chown -R root:ragkb /opt/ragkb
chmod -R u=rwX,go=rX /opt/ragkb

# Data directories
chown -R ragkb:ragkb /var/lib/ragkb
chmod -R u=rwX,go= /var/lib/ragkb

# Log directories
chown -R ragkb:ragkb /var/log/ragkb
chmod -R u=rwX,go= /var/log/ragkb

# Qdrant data
chown -R qdrant:qdrant /var/lib/qdrant
chmod -R u=rwX,go= /var/lib/qdrant
```

### Process Security

Systemd service hardening:

```ini
[Service]
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/ragkb/storage /var/log/ragkb /var/cache/ragkb/models
```

## Troubleshooting

### Permission Denied Errors

```bash
# Check ownership
ls -la /var/lib/ragkb/storage

# Fix ownership
sudo chown -R ragkb:ragkb /var/lib/ragkb/storage
```

### Qdrant Not Starting

```bash
# Check data directory
ls -la /var/lib/qdrant

# Check logs
journalctl -u qdrant -f

# Verify config
cat /etc/qdrant/config.yaml
```

### Model Download Failing

```bash
# Check cache permissions
ls -la /var/cache/ragkb/models

# Check disk space
df -h /var/cache
```

## Quick Reference

```bash
# Check service status
sudo systemctl status ragkb-api ragkb-worker qdrant

# View logs
sudo journalctl -u ragkb-api -f
sudo tail -f /var/log/ragkb/api.log

# Disk usage
df -h /var/lib/qdrant /var/lib/ragkb

# Qdrant data size
du -sh /var/lib/qdrant

# Storage size
du -sh /var/lib/ragkb/storage
```
