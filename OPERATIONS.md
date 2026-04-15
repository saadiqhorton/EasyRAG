# RAG Knowledge Base - Operations Guide

Daily operations, troubleshooting, and maintenance for the RAG Knowledge Base Framework.

---

## Table of Contents

1. [Service Management](#service-management)
2. [Log Management](#log-management)
3. [Health Monitoring](#health-monitoring)
4. [Job Monitoring](#job-monitoring)
5. [Backup and Restore](#backup-and-restore)
6. [Common Tasks](#common-tasks)
7. [Troubleshooting](#troubleshooting)
8. [Performance Tuning](#performance-tuning)

---

## Service Management

### Docker Compose

```bash
# Check status
docker compose ps

# View logs
docker compose logs -f
docker compose logs -f api
docker compose logs -f worker

# Restart services
docker compose restart
docker compose restart api

# Stop/start
docker compose stop
docker compose start
docker compose up -d

# Full rebuild
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Systemd

```bash
# Check status
sudo systemctl status ragkb-api ragkb-worker

# View logs
sudo journalctl -u ragkb-api -f
sudo journalctl -u ragkb-worker -f

# Restart
sudo systemctl restart ragkb-api
sudo systemctl restart ragkb-worker

# Stop/start
sudo systemctl stop ragkb-api
sudo systemctl start ragkb-api

# Enable/disable auto-start
sudo systemctl enable ragkb-api
sudo systemctl disable ragkb-api
```

---

## Log Management

### Log Locations

| Service | Docker | Systemd |
|---------|--------|---------|
| API | `docker compose logs api` | `/var/log/ragkb/api.log` |
| Worker | `docker compose logs worker` | `journalctl -u ragkb-worker` |
| PostgreSQL | `docker compose logs postgres` | `/var/log/postgresql/` |
| Qdrant | `docker compose logs qdrant` | `journalctl -u qdrant` |

### Structured Logging

All services output JSON-structured logs:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "logger": "app.backend.services.indexer",
  "message": "upserted_chunks",
  "count": 19,
  "collection": "rag_kb_chunks"
}
```

### Key Log Patterns

**Search for errors:**
```bash
# Docker
docker compose logs | grep -i error

# Systemd
sudo journalctl -u ragkb-api | grep -i error
```

**Monitor ingestion:**
```bash
docker compose logs -f worker | grep -E "(ingestion_succeeded|ingestion_failed|job_dead_letter)"
```

**Monitor search performance:**
```bash
docker compose logs -f api | grep -E "(search_completed|search_failed)"
```

### Log Rotation

Docker Compose (configured in compose file):
- Max file size: 50MB
- Max files: 5

Systemd:
```bash
# Configure in /etc/systemd/journald.conf
SystemMaxUse=500M
MaxFileSec=1week
```

---

## Health Monitoring

### Health Endpoints

| Endpoint | URL | Purpose |
|----------|-----|---------|
| Basic health | `GET /health` | Load balancer check |
| Readiness | `GET /health/ready` | Kubernetes/Docker ready |
| Liveness | `GET /health/live` | Process alive check |

### Check Commands

```bash
# Full health check
./deploy/scripts/health_check.sh

# Wait for services
./deploy/scripts/health_check.sh --wait

# Manual checks
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
curl http://localhost:6333/healthz
```

### Key Metrics

Monitor these metrics regularly:

| Metric | Source | Threshold | Alert |
|--------|--------|-----------|-------|
| API response time | /health | > 5s | Critical |
| PostgreSQL connections | pg_stat_activity | > 80% max | Warning |
| Qdrant collection size | /collections | > 1M points | Info |
| Failed jobs | ingestion_jobs | > 5% | Warning |
| Dead letter jobs | ingestion_jobs | > 0 | Critical |
| Disk usage | df -h | > 85% | Critical |
| Memory usage | free -m | > 90% | Warning |

---

## Job Monitoring

### Check Job Status

```bash
# Via API
curl http://localhost:8000/api/v1/ingestion-jobs/{job_id}

# Via database (requires psql)
docker compose exec postgres psql -U ragkb -c "
  SELECT id, status, current_stage, retry_count, created_at
  FROM ingestion_jobs
  ORDER BY created_at DESC
  LIMIT 10;
"
```

### Common Job Queries

**Stuck jobs (queued too long):**
```sql
SELECT id, created_at, current_stage
FROM ingestion_jobs
WHERE status = 'queued'
  AND created_at < NOW() - INTERVAL '1 hour';
```

**Failed jobs:**
```sql
SELECT j.id, j.status, j.retry_count, f.error_type, f.message
FROM ingestion_jobs j
LEFT JOIN failure_events f ON j.id = f.job_id
WHERE j.status IN ('failed', 'dead_letter')
ORDER BY j.created_at DESC
LIMIT 10;
```

**Success rate (last 24h):**
```sql
SELECT
  status,
  COUNT(*) as count,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as pct
FROM ingestion_jobs
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY status;
```

### Retry Failed Jobs

```bash
# Re-queue a specific job
curl -X POST http://localhost:8000/api/v1/ingestion-jobs/{job_id}/retry

# Bulk retry all failed jobs
docker compose exec postgres psql -U ragkb -c "
  UPDATE ingestion_jobs
  SET status = 'queued', retry_count = retry_count + 1
  WHERE status = 'failed' AND retry_count < 3;
"
```

---

## Backup and Restore

### PostgreSQL Backup

**Automated daily backup:**
```bash
#!/bin/bash
BACKUP_DIR="/var/backups/ragkb"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

docker compose exec -T postgres pg_dump -U ragkb ragkb \
  | gzip > "$BACKUP_DIR/ragkb_$DATE.sql.gz"

# Keep only last 7 days
find $BACKUP_DIR -name "ragkb_*.sql.gz" -mtime +7 -delete
```

**Manual backup:**
```bash
docker compose exec postgres pg_dump -U ragkb ragkb > backup.sql
```

**Restore:**
```bash
# Stop worker to prevent writes
docker compose stop worker

# Restore database
docker compose exec -T postgres psql -U ragkb ragkb < backup.sql

# Restart worker
docker compose start worker
```

### Qdrant Backup

**Create snapshot:**
```bash
curl -X POST http://localhost:6333/collections/rag_kb_chunks/snapshots
```

**List snapshots:**
```bash
curl http://localhost:6333/collections/rag_kb_chunks/snapshots
```

**Restore from snapshot:**
```bash
# Download snapshot to Qdrant storage, then:
curl -X PUT http://localhost:6333/collections/rag_kb_chunks/snapshots/recover \
  -H "Content-Type: application/json" \
  -d '{"snapshot_location": "/qdrant/snapshots/rag_kb_chunks-xxx.snapshot"}'
```

### Storage Backup

**Backup uploaded files:**
```bash
tar czf storage_backup_$(date +%Y%m%d).tar.gz /var/lib/ragkb/storage
```

**Model cache backup:**
```bash
tar czf models_backup_$(date +%Y%m%d).tar.gz ~/.cache/huggingface
```

---

## Common Tasks

### Rotate API Keys

```bash
# Update .env file
nano .env

# Restart services to pick up new keys
docker compose restart api worker
```

### Update Configuration

```bash
# Edit environment file
nano .env

# Restart services
docker compose restart

# Verify new config took effect
docker compose logs api | grep -i "config\|setting"
```

### Clear Job Queue

**WARNING: Destructive operation**

```bash
# Cancel all queued jobs
docker compose exec postgres psql -U ragkb -c "
  UPDATE ingestion_jobs
  SET status = 'failed'
  WHERE status = 'queued';
"
```

### Purge Old Data

**Remove old document versions:**
```bash
# Archive documents older than 90 days
docker compose exec postgres psql -U ragkb -c "
  UPDATE document_versions
  SET index_status = 'archived'
  WHERE created_at < NOW() - INTERVAL '90 days'
    AND is_active = false;
"
```

### Scale Workers

Docker Compose:
```bash
# Scale to 3 workers
docker compose up -d --scale worker=3 worker
```

Systemd:
```bash
# Create multiple worker instances
sudo systemctl enable ragkb-worker@1
sudo systemctl enable ragkb-worker@2
sudo systemctl start ragkb-worker@1
sudo systemctl start ragkb-worker@2
```

---

## Troubleshooting

### Service Won't Start

**PostgreSQL connection refused:**
```bash
# Check PostgreSQL is running
docker compose logs postgres | tail -20

# Verify credentials
docker compose exec postgres psql -U ragkb -c "SELECT 1"

# Check network
docker compose exec api ping postgres
```

**Qdrant health check fails:**
```bash
# Check Qdrant logs
docker compose logs qdrant | tail -20

# Verify port not in use
sudo lsof -i :6333

# Check disk space
df -h /var/lib/qdrant
```

**API fails to start:**
```bash
# Check environment variables
docker compose exec api env | grep -E "POSTGRES|QDRANT"

# Verify config loads
docker compose logs api | grep -i "error\|config\|setting" | head -20
```

### Ingestion Failures

**Job stuck in queued:**
```bash
# Check worker is running
docker compose ps worker
docker compose logs worker | tail -50

# Check database locks
docker compose exec postgres psql -U ragkb -c "
  SELECT * FROM pg_locks WHERE NOT granted;
"
```

**Parse failures:**
```bash
# Check file format is supported
docker compose logs worker | grep -i "parse_failed"

# Verify OCR is installed (for PDFs)
docker compose exec api tesseract --version
```

**Embedding failures:**
```bash
# Check model download
docker compose logs worker | grep -i "embedding\|huggingface"

# Set HF_TOKEN for better rate limits
echo "HF_TOKEN=your_token" >> .env
docker compose restart worker
```

### Search Returns No Results

1. Check documents were ingested:
   ```bash
   curl http://localhost:6333/collections/rag_kb_chunks
   ```

2. Verify collection has points:
   ```bash
   curl http://localhost:6333/collections/rag_kb_chunks | jq '.result.points_count'
   ```

3. Check search query:
   ```bash
   curl -X POST http://localhost:8000/api/v1/collections/{id}/search \
     -H "Content-Type: application/json" \
     -d '{"query": "test", "limit": 5}'
   ```

### LLM Not Responding

**Ollama not reachable:**
```bash
# Test Ollama directly
curl http://localhost:11434/api/tags

# Check Ollama is running
sudo systemctl status ollama

# Pull model if needed
ollama pull llama3.2
```

**OpenAI API errors:**
```bash
# Verify API key
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# Check rate limits in logs
docker compose logs api | grep -i "rate\|quota\|billing"
```

---

## Performance Tuning

### Database Optimization

**PostgreSQL (add to postgresql.conf):**
```
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
work_mem = 4MB
max_connections = 100
```

**Connection pooling (PgBouncer):**
```ini
[databases]
ragkb = host=localhost port=5432 dbname=ragkb

[pgbouncer]
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 20
```

### Worker Tuning

**Adjust worker poll interval:**
```bash
# Faster polling (more CPU, lower latency)
WORKER_POLL_INTERVAL=1.0

# Slower polling (less CPU, higher latency)
WORKER_POLL_INTERVAL=5.0
```

**Chunk size optimization:**
```bash
# Smaller chunks (better precision, more storage)
CHUNK_MAX_TOKENS=300

# Larger chunks (less storage, may miss details)
CHUNK_MAX_TOKENS=1000
```

### Qdrant Optimization

**Indexing parameters:**
```yaml
# config/qdrant_config.yaml
storage:
  performance:
    max_search_threads: 4
    max_optimization_threads: 2

hnsw_config:
  m: 16
  ef_construct: 100
  ef: 100
```

---

## Support and Escalation

**For operational issues:**
1. Check logs: `docker compose logs`
2. Run health check: `./deploy/scripts/health_check.sh`
3. Review this operations guide
4. Check LIVE_VALIDATION_REPORT.md for known issues

**For bugs:**
1. Capture logs during error
2. Reproduce with minimal test case
3. File issue with:
   - Log excerpts
   - Environment details
   - Reproduction steps
