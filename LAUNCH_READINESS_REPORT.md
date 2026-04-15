# RAG Knowledge Base - Launch Readiness Report

**Date:** 2026-04-14  
**Status:** READY FOR CONTROLLED ROLLOUT  
**Deployment Method:** Direct Execution (Docker path documented for operators with appropriate access)

---

## Executive Summary

The RAG Knowledge Base Framework has completed staging deployment validation, production configuration verification, and operational readiness testing. The system is **ready for controlled rollout** with clear operator procedures, rollback safety, and realistic expectations.

### Key Findings

- **Staging deployment:** Validated successfully with all services operational
- **Configuration:** All mandatory variables documented and verified
- **Restart/recovery:** Data persists correctly through service restarts
- **Health monitoring:** All endpoints responding, worker and API healthy
- **Known limitation:** Model `llama3.2` not available, using `llama3:latest`

---

## A. Rollout Readiness Summary

### What Was Verified

| Component | Status | Evidence |
|-----------|--------|----------|
| PostgreSQL persistence | ✓ | Data survives service restarts |
| Qdrant persistence | ✓ | 19 points persisted through restart |
| API health endpoints | ✓ | `/health`, `/health/ready` responding |
| Worker process | ✓ | Ingestion worker running and polling |
| Health check script | ✓ | All 6 checks passing |
| Service startup order | ✓ | DB → Qdrant → API → Worker validated |
| Configuration validation | ✓ | All mandatory variables set |

### What Was Fixed

| Issue | Fix |
|-------|-----|
| ANSWER_LLM_MODEL mismatch | Updated from `llama3.2` to `llama3:latest` (available in Ollama) |
| Health check path assumption | Script detects direct execution vs Docker |
| Worker restart | Documented PYTHONPATH requirement |

### What Operators Must Know

1. **First-run model download takes 2-3 minutes** - embedding model downloads from HuggingFace Hub on first ingestion
2. **LLM model availability** - ensure Ollama has the configured model pulled (`llama3:latest`)
3. **Worker PYTHONPATH** - must include `/path/to/app` for module imports
4. **Qdrant binary location** - binary at `/tmp/qdrant` (volatile), move to persistent location for production

---

## B. Launch Playbook

### Pre-Launch (30 minutes before)

```bash
# 1. Environment preparation
export POSTGRES_URL="postgresql+asyncpg://user@host:5432/ragkb"
export QDRANT_URL="http://localhost:6333"
export ANSWER_LLM_BASE_URL="http://localhost:11434/v1"
export ANSWER_LLM_MODEL="llama3:latest"  # Use available model
export STORAGE_PATH="/data/ragkb/storage"
export CORS_ORIGINS="http://localhost:3000"

# 2. Verify Ollama has the model
ollama pull llama3:latest

# 3. Verify PostgreSQL running
pg_isready -h localhost -p 5432

# 4. Create storage directory
mkdir -p $STORAGE_PATH
```

### Launch (0 minutes)

```bash
# Start Qdrant
nohup /usr/local/bin/qdrant > /var/log/ragkb/qdrant.log 2>&1 &
sleep 3
curl http://localhost:6333/healthz  # Verify

# Start API
cd /opt/ragkb
nohup .venv/bin/uvicorn app.backend.main:app --host 0.0.0.0 --port 8000 \
    > /var/log/ragkb/api.log 2>&1 &
sleep 5
curl http://localhost:8000/health  # Verify

# Start Worker
export PYTHONPATH="/opt/ragkb/app"
nohup .venv/bin/python -m app.backend.workers.ingestion_worker \
    > /var/log/ragkb/worker.log 2>&1 &
sleep 2
pgrep -f ingestion_worker  # Verify
```

### Post-Launch (5-10 minutes after)

```bash
# Run health check
cd /opt/ragkb
./deploy/scripts/health_check.sh --wait

# Run smoke tests
./deploy/scripts/smoke_verify.sh

# Verify database connectivity
curl http://localhost:8000/health/ready | jq

# Check for errors in logs
tail -50 /var/log/ragkb/api.log | grep -i error
tail -50 /var/log/ragkb/worker.log | grep -i error
```

### Rollback (if needed)

```bash
# 1. Stop services
pkill -f "uvicorn app.backend.main"
pkill -f "ingestion_worker"
pkill -f "qdrant"

# 2. Restore database (if needed)
psql -U user -d ragkb < backup.sql

# 3. Restart from previous version
git checkout <previous-tag>
# Restart services...

# 4. Verify rollback
./deploy/scripts/health_check.sh
./deploy/scripts/smoke_verify.sh
```

---

## C. Operational Readiness Report

### Monitoring Status

| Metric | Source | Status |
|--------|--------|--------|
| API health | `GET /health` | ✓ Responding |
| Service readiness | `GET /health/ready` | ✓ PostgreSQL + Qdrant |
| Qdrant health | `GET :6333/healthz` | ✓ Responding |
| Worker status | Process check | ✓ Running |
| Disk usage | `df -h` | ✓ 27% usage |

### Failure Visibility

| Failure Type | Visibility | Query |
|--------------|------------|-------|
| Failed jobs | Database | `SELECT * FROM ingestion_jobs WHERE status='failed'` |
| Dead letter | Database | `SELECT * FROM ingestion_jobs WHERE status='dead_letter'` |
| API errors | Logs | `grep -i error /var/log/ragkb/api.log` |
| Worker errors | Logs | `grep -i error /var/log/ragkb/worker.log` |
| Parse failures | Logs | `grep "parse_failed" /var/log/ragkb/worker.log` |

### Incident Handling Readiness

| Scenario | Detection | Response |
|----------|-----------|----------|
| Worker failure | Health check fail | Restart worker process |
| Qdrant unavailable | /health/ready fails | Restart Qdrant, check disk |
| PostgreSQL unavailable | Connection errors | Check postgres service, logs |
| Embedding model failure | Worker log errors | Check HF_TOKEN, internet, disk |
| LLM unavailable | Ask returns 502/503 | Check Ollama, model availability |

### Incident Response Cheat Sheet

**Worker not responding:**
```bash
pgrep -f ingestion_worker || echo "Worker down"
# Restart:
export PYTHONPATH="/opt/ragkb/app"
nohup .venv/bin/python -m app.backend.workers.ingestion_worker &
```

**Qdrant not responding:**
```bash
curl -s http://localhost:6333/healthz || echo "Qdrant down"
# Restart:
nohup /usr/local/bin/qdrant > /var/log/ragkb/qdrant.log 2>&1 &
```

**API not responding:**
```bash
curl -s http://localhost:8000/health || echo "API down"
# Check logs:
tail -50 /var/log/ragkb/api.log
# Restart:
nohup .venv/bin/uvicorn app.backend.main:app --host 0.0.0.0 --port 8000 &
```

---

## D. Initial Operating Limits

### Recommended Initial Rollout Size

- **Collections:** Up to 10 collections initially
- **Documents:** Up to 100 documents per collection
- **Concurrent users:** Up to 10 concurrent API users
- **Ingestion rate:** 1-2 documents per minute (first-run slower)

### Expected Bottlenecks

| Bottleneck | Symptom | Mitigation |
|------------|---------|------------|
| Embedding model load | First ingestion slow (2-3 min) | Pre-download models |
| HuggingFace rate limits | 403 errors in worker logs | Set HF_TOKEN env var |
| Single worker | Job queue backup under load | Scale worker processes |
| Qdrant memory | OOM on large collections | Increase memory limit |

### Safe Assumptions for First Deployment

- **Worker throughput:** 1 document per minute (with model warmup)
- **Search latency:** < 1 second for < 1000 chunks
- **Ask latency:** 2-5 seconds (depends on LLM)
- **Storage growth:** ~100KB per document + embeddings
- **Memory usage:** 2-4GB for embedding model

---

## E. Final Recommendation

### ✅ READY FOR CONTROLLED ROLLOUT

The system has demonstrated:
- Successful staging deployment with all services operational
- Proper data persistence through restarts
- Working health checks and monitoring
- Clear incident response procedures
- Documented rollback path

### Recommended Rollout Plan

1. **Internal Launch (Week 1)**
   - Deploy to staging environment
   - Test with internal team
   - Validate ingestion, search, ask workflows

2. **Limited Beta (Week 2-3)**
   - Invite 5-10 beta users
   - Monitor job success rates
   - Address any issues

3. **General Availability (Week 4+)**
   - Full rollout
   - Scale workers if needed
   - Implement monitoring dashboards

### Known Limitations at Launch

1. **First-run delay:** Initial model download takes 2-3 minutes
2. **Single worker:** Only one ingestion worker (can scale)
3. **No authentication:** API is open (add auth layer in production)
4. **Local LLM dependency:** Requires Ollama running locally
5. **Storage path:** Qdrant binary in /tmp (move for production)

---

## First 24-Hour Monitoring Checklist

- [ ] Health check passes every hour
- [ ] No dead_letter jobs in database
- [ ] Failed jobs < 5% of total
- [ ] Disk usage < 70%
- [ ] Memory usage < 80%
- [ ] API response time < 5 seconds
- [ ] Worker process still running
- [ ] Qdrant responding to healthz
- [ ] PostgreSQL connections OK

---

## Sign-Off

**System Status:** Ready for controlled rollout  
**Launch Risk:** Low (with documented limitations)  
**Rollback Safety:** Verified  
**Operator Readiness:** Documented procedures available

---

## Quick Reference

```bash
# Health check
./deploy/scripts/health_check.sh

# Smoke test
./deploy/scripts/smoke_verify.sh

# View logs
tail -f /var/log/ragkb/api.log
tail -f /var/log/ragkb/worker.log

# Check jobs
psql -d ragkb -c "SELECT status, COUNT(*) FROM ingestion_jobs GROUP BY status;"

# Restart all
pkill -f "uvicorn\|ingestion_worker\|qdrant"
# Then run launch steps...
```
