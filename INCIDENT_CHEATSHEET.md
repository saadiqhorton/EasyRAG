# RAG Knowledge Base - Incident Response Cheat Sheet

Quick reference for common operational issues.

---

## Health Check Failures

### API Not Responding

```bash
# Check if API is running
pgrep -f "uvicorn app.backend.main"

# Check logs
tail -50 /var/log/ragkb/api.log

# Restart API
cd /opt/ragkb
export $(cat .env | xargs)
nohup .venv/bin/uvicorn app.backend.main:app --host 0.0.0.0 --port 8000 &
```

### Qdrant Not Responding

```bash
# Check if Qdrant is running
pgrep -f qdrant
curl -s http://localhost:6333/healthz

# Check logs
tail -50 /var/log/ragkb/qdrant.log

# Restart Qdrant
nohup /usr/local/bin/qdrant > /var/log/ragkb/qdrant.log 2>&1 &
sleep 3
curl http://localhost:6333/healthz
```

### PostgreSQL Not Responding

```bash
# Check PostgreSQL
pg_isready -h localhost -p 5432

# Check logs
brew services log postgresql@16  # macOS
sudo tail -50 /var/log/postgresql/*.log  # Linux

# Restart PostgreSQL
brew services restart postgresql@16  # macOS
sudo systemctl restart postgresql  # Linux
```

### Worker Not Running

```bash
# Check if worker is running
pgrep -f ingestion_worker

# Check logs
tail -50 /var/log/ragkb/worker.log

# Restart worker
cd /opt/ragkb
export PYTHONPATH="/opt/ragkb/app"
export $(cat .env | xargs)
nohup .venv/bin/python -m app.backend.workers.ingestion_worker &
```

---

## Ingestion Failures

### Jobs Stuck in "queued"

```bash
# Check worker status
pgrep -f ingestion_worker || echo "WORKER DOWN"

# Check for stuck jobs
psql -d ragkb -c "
  SELECT id, created_at, current_stage
  FROM ingestion_jobs
  WHERE status = 'queued'
  AND created_at < NOW() - INTERVAL '5 minutes';
"

# Restart worker if needed
pkill -f ingestion_worker
# Then restart (see above)
```

### Parse Failures

```bash
# Check worker logs for parse errors
tail -100 /var/log/ragkb/worker.log | grep "parse_failed"

# Common causes:
# - Unsupported file format
# - Corrupted PDF
# - OCR not available (for scanned PDFs)

# Check if tesseract is installed
tesseract --version
```

### Embedding Failures

```bash
# Check worker logs
tail -100 /var/log/ragkb/worker.log | grep -i embedding

# Common causes:
# - HuggingFace rate limits (set HF_TOKEN)
# - Network issues
# - Disk space full

# Set HF_TOKEN for better rate limits
export HF_TOKEN="your_huggingface_token"
```

### Dead Letter Jobs

```bash
# List dead letter jobs
psql -d ragkb -c "
  SELECT j.id, j.status, f.error_type, f.message
  FROM ingestion_jobs j
  JOIN failure_events f ON j.id = f.job_id
  WHERE j.status = 'dead_letter'
  ORDER BY j.created_at DESC
  LIMIT 5;
"

# Retry a specific job
curl -X POST http://localhost:8000/api/v1/ingestion-jobs/{job_id}/retry
```

---

## Search Issues

### Search Returns No Results

```bash
# Check collection has documents
curl http://localhost:6333/collections/rag_kb_chunks | jq '.result.points_count'

# Check documents are indexed
psql -d ragkb -c "SELECT COUNT(*) FROM chunks;"

# Verify query is working
curl -X POST http://localhost:8000/api/v1/collections/{id}/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "limit": 5}'
```

### Slow Search Performance

```bash
# Check Qdrant collection info
curl http://localhost:6333/collections/rag_kb_chunks | jq '.result'

# Look for:
# - indexed_vectors_count (should equal points_count)
# - segments_count (optimize if too high)
```

---

## LLM Issues

### Ask Endpoint Returns 502/503

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Check if model exists
curl http://localhost:11434/api/tags | grep llama3

# Pull model if needed
ollama pull llama3:latest

# Check Ollama logs
# macOS: ~/.ollama/logs/server.log
# Linux: /var/log/ollama/
```

### LLM Response Timeout

```bash
# Check Ollama resource usage
top -p $(pgrep ollama)

# Check if model is loaded
ollama ps

# Restart Ollama if needed
pkill ollama
ollama serve
```

---

## Resource Issues

### Disk Space Full

```bash
# Check disk usage
df -h

# Find large files
du -sh /var/lib/ragkb/* 2>/dev/null
du -sh ~/.cache/huggingface/* 2>/dev/null

# Clean up old logs
find /var/log/ragkb -name "*.log" -mtime +7 -delete

# Clean up old Qdrant snapshots
find /var/lib/qdrant/snapshots -mtime +7 -delete
```

### Memory Issues

```bash
# Check memory usage
free -h

# Check process memory
ps aux | grep -E "(uvicorn|qdrant|python)" | grep -v grep

# Restart services to free memory
pkill -f ingestion_worker
pkill -f "uvicorn app.backend.main"
sleep 5
# Restart services...
```

---

## Database Issues

### Connection Pool Exhausted

```bash
# Check active connections
psql -d ragkb -c "
  SELECT count(*), state
  FROM pg_stat_activity
  WHERE datname = 'ragkb'
  GROUP BY state;
"

# Restart API to reset connections
pkill -f "uvicorn app.backend.main"
# Restart API...
```

### Slow Queries

```bash
# Check for long-running queries
psql -d ragkb -c "
  SELECT pid, state, query_start, query
  FROM pg_stat_activity
  WHERE state != 'idle'
  AND query_start < NOW() - INTERVAL '1 minute';
"
```

---

## Quick Diagnostics

### Full System Check

```bash
# Run health check
./deploy/scripts/health_check.sh

# Check all services
pgrep -f "uvicorn|qdrant|ingestion_worker"

# Check logs for errors
tail -50 /var/log/ragkb/api.log | grep -i error
tail -50 /var/log/ragkb/worker.log | grep -i error

# Check database
psql -d ragkb -c "
  SELECT status, COUNT(*) as count
  FROM ingestion_jobs
  GROUP BY status;
"
```

### Smoke Test

```bash
# Run smoke verification
./deploy/scripts/smoke_verify.sh
```

---

## Rollback Procedures

### Emergency Rollback

```bash
# 1. Stop all services
pkill -f "uvicorn\|ingestion_worker\|qdrant"

# 2. Restore database (if needed)
psql -d ragkb < backup.sql

# 3. Restore storage
tar xzf storage_backup.tar.gz -C /

# 4. Restart services
# See launch playbook...
```

---

## Contact Information

| Role | Contact |
|------|---------|
| On-Call Engineer | [TBD] |
| Database Admin | [TBD] |
| Infrastructure | [TBD] |

---

## Escalation Path

1. Check this cheat sheet
2. Review OPERATIONS.md
3. Check LAUNCH_READINESS_REPORT.md
4. Review logs with `tail -f`
5. Escalate to on-call engineer
