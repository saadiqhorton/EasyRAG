# RAG Knowledge Base - Deployment Guide

Complete guide for deploying the RAG Knowledge Base Framework in production environments.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Architecture Overview](#architecture-overview)
3. [Prerequisites](#prerequisites)
4. [Environment Configuration](#environment-configuration)
5. [Deployment Options](#deployment-options)
   - Docker Compose (Recommended)
   - Systemd Services
6. [Post-Deployment Verification](#post-deployment-verification)
7. [Operations](#operations)
8. [Troubleshooting](#troubleshooting)
9. [Rollback Procedure](#rollback-procedure)

---

## Quick Start

```bash
# 1. Clone and enter repository
cd /path/to/rag-kb-project

# 2. Create environment file
cp deploy/config/.env.production .env
# Edit .env with your values

# 3. Start services
docker compose -f deploy/docker-compose.yml up -d

# 4. Verify deployment
./deploy/scripts/health_check.sh
./deploy/scripts/smoke_verify.sh
```

---

## Architecture Overview

The system consists of four main services:

| Service | Purpose | Port | Persistent Storage |
|---------|---------|------|-------------------|
| PostgreSQL | Metadata, jobs, documents | 5432 | `pgdata` volume |
| Qdrant | Vector + sparse search | 6333, 6334 | `qdrant_data` volume |
| API | FastAPI HTTP server | 8000 | `storage_data` volume |
| Worker | Ingestion job processor | N/A | `storage_data` volume |

Optional: Frontend (Next.js on port 3000)

---

## Prerequisites

### Minimum Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 2 cores | 4 cores |
| RAM | 4 GB | 8 GB |
| Disk | 50 GB | 100 GB SSD |
| OS | Linux x86_64 | Ubuntu 22.04+ |

### Software Dependencies

- Docker 24.0+ and Docker Compose v2.0+
- OR: Python 3.11+ and PostgreSQL 16 for systemd deployment
- curl (for health checks)

### Network Requirements

- PostgreSQL: Port 5432 (internal only recommended)
- Qdrant: Ports 6333, 6334 (internal only recommended)
- API: Port 8000 (expose via reverse proxy)
- Optional LLM: Access to Ollama (11434) or OpenAI API

---

## Environment Configuration

### Required Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `POSTGRES_USER` | Database user | `ragkb` |
| `POSTGRES_PASSWORD` | Database password | `secure_random_password` |
| `POSTGRES_DB` | Database name | `ragkb` |
| `ANSWER_LLM_BASE_URL` | LLM API endpoint | `http://ollama:11434/v1` |
| `ANSWER_LLM_MODEL` | LLM model name | `llama3.2` |

### Optional Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `EMBEDDING_MODEL_NAME` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model |
| `RERANKER_MODEL_NAME` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Reranker model |
| `MAX_UPLOAD_SIZE_MB` | `50` | Upload limit |
| `WORKER_POLL_INTERVAL` | `2.0` | Job polling interval (seconds) |
| `CHUNK_MAX_TOKENS` | `500` | Chunk size |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed CORS origins |

### Environment Files

Three templates provided:

- `deploy/config/.env.local` - Local development
- `deploy/config/.env.staging` - Staging environment
- `deploy/config/.env.production` - Production environment

**Security Note:** Never commit `.env` files. Use secrets management for production.

---

## Deployment Options

### Option 1: Docker Compose (Recommended)

#### Step 1: Prepare Environment

```bash
# Create data directories
mkdir -p /var/lib/ragkb/postgres
mkdir -p /var/lib/ragkb/qdrant
mkdir -p /var/lib/ragkb/storage

# Copy and configure environment
cp deploy/config/.env.production .env
nano .env  # Edit with your values
```

#### Step 2: Deploy

```bash
docker compose -f deploy/docker-compose.yml up -d
```

Services start in order:
1. PostgreSQL (waits for healthy)
2. Qdrant (waits for healthy)
3. API and Worker (wait for DBs)

#### Step 3: Verify

```bash
./deploy/scripts/health_check.sh
```

Expected output:
```
[OK] PostgreSQL is healthy
[OK] Qdrant is healthy
[OK] API is responding
[OK] All services operational
```

#### Step 4: Run Smoke Tests

```bash
./deploy/scripts/smoke_verify.sh
```

#### Docker Compose Features

- **Health checks**: All services report health status
- **Restart policy**: Always restart on failure
- **Logging**: JSON format, 10MB per file, 3 files max
- **Resource limits**: Configured for stable operation

### Option 2: Systemd Services (Bare Metal)

For environments where Docker is not available.

#### Prerequisites

```bash
# Install system packages
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip \
    postgresql-16 poppler-utils tesseract-ocr redis-tools

# Create user
sudo useradd -r -s /bin/false ragkb
```

#### Install Application

```bash
# Create directories
sudo mkdir -p /opt/ragkb
sudo chown ragkb:ragkb /opt/ragkb

# Clone application
cd /opt/ragkb
git clone <repository> .

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate
pip install -e "app/backend/"
```

#### Configure PostgreSQL

```bash
sudo -u postgres psql <<EOF
CREATE USER ragkb WITH PASSWORD 'your_secure_password';
CREATE DATABASE ragkb OWNER ragkb;
EOF
```

#### Install Qdrant

```bash
# Download and install Qdrant binary
curl -L -o /tmp/qdrant.tar.gz \
    "https://github.com/qdrant/qdrant/releases/download/v1.12.1/qdrant-x86_64-unknown-linux-musl.tar.gz"
tar xzf /tmp/qdrant.tar.gz -C /usr/local/bin/

# Create service user
sudo useradd -r -s /bin/false qdrant
sudo mkdir -p /var/lib/qdrant
sudo chown qdrant:qdrant /var/lib/qdrant
```

#### Install Services

```bash
# Copy service files
sudo cp deploy/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload

# Enable and start
sudo systemctl enable postgresql qdrant ragkb-api ragkb-worker
sudo systemctl start postgresql
sudo systemctl start qdrant
sudo systemctl start ragkb-api
sudo systemctl start ragkb-worker
```

#### Configure Environment

Create `/opt/ragkb/.env`:

```bash
POSTGRES_URL=postgresql+asyncpg://ragkb:password@localhost:5432/ragkb
QDRANT_URL=http://localhost:6333
ANSWER_LLM_BASE_URL=http://localhost:11434/v1
ANSWER_LLM_MODEL=llama3.2
STORAGE_PATH=/var/lib/ragkb/storage
```

---

## Post-Deployment Verification

### Health Checks

```bash
# Check all services
./deploy/scripts/health_check.sh

# Check individual services
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
curl http://localhost:6333/healthz
```

### Smoke Tests

```bash
# Full end-to-end test
./deploy/scripts/smoke_verify.sh

# Expected output:
# [OK] API health
# [OK] Database connectivity
# [OK] Qdrant connectivity
# [OK] Document upload
# [OK] Ingestion completion
# [OK] Search results
```

### First Run Behavior

**Note:** First ingestion will take 2-3 minutes as the embedding model downloads from HuggingFace. Subsequent ingestions are much faster.

Monitor with:
```bash
docker compose logs -f worker
```

---

## Operations

### Daily Operations

#### Check Service Status

```bash
# Docker Compose
docker compose ps
docker compose logs --tail 100

# Systemd
sudo systemctl status ragkb-api ragkb-worker
journalctl -u ragkb-api -f
```

#### View Logs

```bash
# API logs
docker compose logs -f api

# Worker logs
docker compose logs -f worker

# Database logs
docker compose logs -f postgres
```

#### Restart Services

```bash
# Restart all
docker compose restart

# Restart specific service
docker compose restart worker
```

### Backup and Restore

#### PostgreSQL Backup

```bash
# Create backup
docker compose exec postgres pg_dump -U ragkb ragkb > backup_$(date +%Y%m%d).sql

# Restore
docker compose exec -T postgres psql -U ragkb ragkb < backup_YYYYMMDD.sql
```

#### Qdrant Backup

```bash
# Create snapshot
curl -X POST http://localhost:6333/collections/rag_kb_chunks/snapshots

# List snapshots
curl http://localhost:6333/collections/rag_kb_chunks/snapshots

# Restore from snapshot
curl -X PUT http://localhost:6333/collections/rag_kb_chunks/snapshots/recover \
    -H "Content-Type: application/json" \
    -d '{"snapshot_location": "/qdrant/snapshots/..."}'
```

#### Storage Backup

```bash
# Backup upload storage
tar czf storage_backup_$(date +%Y%m%d).tar.gz /var/lib/ragkb/storage
```

### Monitoring

#### Key Metrics

| Metric | Source | Alert Threshold |
|--------|--------|-----------------|
| API response time | /health | > 5s |
| Failed jobs | ingestion_jobs table | retry_count > 2 |
| Dead letter jobs | ingestion_jobs table | status = 'dead_letter' |
| Disk usage | df -h | > 85% |
| Memory usage | free -m | > 90% |

#### Health Check Endpoints

| Endpoint | Returns | Use Case |
|----------|---------|----------|
| `GET /health` | Basic health | Load balancer |
| `GET /health/ready` | DB + Qdrant status | Startup probe |
| `GET /health/live` | Process alive | Liveness probe |

---

## Troubleshooting

### Service Won't Start

**PostgreSQL connection refused:**
```bash
# Check PostgreSQL is running
docker compose logs postgres

# Verify credentials in .env match
```

**Qdrant health check fails:**
```bash
# Check Qdrant logs
docker compose logs qdrant

# Verify port not in use
sudo lsof -i :6333
```

**API fails to start:**
```bash
# Check environment variables
docker compose logs api | grep -i error

# Verify all required vars are set
docker compose exec api env | grep POSTGRES
```

### Ingestion Failures

**Job stuck in queued:**
- Check worker is running: `docker compose ps worker`
- Check worker logs: `docker compose logs worker`

**Parse failures:**
- Check document format is supported
- Verify Tesseract OCR is installed (for PDFs)
- Check file size under limit

**Embedding failures:**
- Verify model download succeeded
- Check internet connectivity for HF Hub
- Set HF_TOKEN for better rate limits

### Search Returns No Results

1. Verify documents were ingested successfully
2. Check Qdrant collection exists:
   ```bash
   curl http://localhost:6333/collections
   ```
3. Verify collection has points:
   ```bash
   curl http://localhost:6333/collections/rag_kb_chunks
   ```

### LLM Not Responding

**Ollama not reachable:**
```bash
# Test Ollama directly
curl http://localhost:11434/api/tags

# Verify ANSWER_LLM_BASE_URL in .env
```

---

## Rollback Procedure

### Docker Compose Rollback

```bash
# Stop services
docker compose down

# Restore database (if needed)
docker compose up -d postgres
docker compose exec -T postgres psql -U ragkb ragkb < backup_file.sql

# Restore Qdrant (if needed)
# Copy backup snapshot to Qdrant storage and restore

# Restart services
docker compose up -d
```

### Version Rollback

```bash
# Checkout previous version
git checkout <previous-tag>

# Rebuild and restart
docker compose down
docker compose build --no-cache
docker compose up -d
```

---

## Security Considerations

1. **Network Security**
   - Don't expose PostgreSQL or Qdrant directly to internet
   - Use reverse proxy (nginx/traefik) for API
   - Enable HTTPS in production

2. **Secrets Management**
   - Use Docker secrets or external vault
   - Never commit .env files
   - Rotate credentials regularly

3. **File Uploads**
   - MAX_UPLOAD_SIZE_MB limits upload size
   - Files stored outside web root
   - Path traversal prevented in storage layer

---

## Support

For issues:
1. Check logs: `docker compose logs`
2. Review troubleshooting section
3. Check LIVE_VALIDATION_REPORT.md
4. File issue with logs and reproduction steps
