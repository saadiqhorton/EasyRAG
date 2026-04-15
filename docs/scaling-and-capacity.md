# Scaling and Capacity Planning

## Overview

This document provides guidance for scaling the RAG Knowledge Base Framework from a controlled rollout through limited beta to general availability.

## Single Worker Capacity

### Baseline Performance

Based on testing with a single ingestion worker:

| Metric | Value |
|--------|-------|
| **Throughput** | 1-2 documents/minute (after model warmup) |
| **First-run latency** | 2-3 minutes (model download) |
| **Memory usage** | 2-4 GB (embedding model) |
| **CPU usage** | 1-2 cores during ingestion |
| **Queue capacity** | Unlimited (PostgreSQL-backed) |

### Bottlenecks Identified

1. **Embedding model loading** - Single model instance per worker
2. **Database connections** - Pool limit (default 10)
3. **Qdrant indexing** - Single-threaded per collection
4. **Worker polling** - 2-second interval adds latency

## Scaling Strategies

### Horizontal Scaling (Multiple Workers)

```bash
# Scale to 3 workers
docker compose up -d --scale worker=3 worker

# Or with systemd
sudo systemctl enable ragkb-worker@1
sudo systemctl enable ragkb-worker@2
sudo systemctl enable ragkb-worker@3
sudo systemctl start ragkb-worker@{1,2,3}
```

**Worker Scaling Formula:**

```
# Recommended workers based on throughput needs
workers = ceil(desired_docs_per_minute / 2)

# Examples:
# - 2 docs/min → 1 worker
# - 10 docs/min → 5 workers
# - 20 docs/min → 10 workers
```

### Vertical Scaling (Resource Limits)

**Worker memory:**
- Minimum: 2GB
- Recommended: 4GB
- Maximum: 8GB (for large documents)

**API server memory:**
- Minimum: 512MB
- Recommended: 1GB
- Maximum: 2GB

**Database connections:**
- Default pool: 10
- Per worker: 1-2 connections
- Formula: max_connections >= workers * 2 + api_instances * 5

## Recommended Configuration by Stage

### Controlled Rollout (Initial)

**Use case:** Internal testing, single team

| Component | Config | Resources |
|-----------|--------|-----------|
| Workers | 1 | 2GB RAM, 1 CPU |
| API | 1 instance | 1GB RAM, 0.5 CPU |
| PostgreSQL | Default | 1GB RAM, shared |
| Qdrant | Default | 1GB RAM, shared |

**Expected capacity:**
- 1-2 documents/minute ingestion
- 10 concurrent API users
- 1000 documents per collection

### Limited Beta

**Use case:** 5-10 external users, multiple collections

| Component | Config | Resources |
|-----------|--------|-----------|
| Workers | 2-3 | 4GB RAM, 2 CPUs |
| API | 2 instances | 1GB RAM each |
| PostgreSQL | Dedicated | 2GB RAM, 1 CPU |
| Qdrant | Dedicated | 2GB RAM, 1 CPU |

**Expected capacity:**
- 4-6 documents/minute ingestion
- 25 concurrent API users
- 5000 documents across collections

### Early GA

**Use case:** 50+ users, production workload

| Component | Config | Resources |
|-----------|--------|-----------|
| Workers | 5-10 | 4GB RAM each, 2+ CPUs |
| API | 3-5 instances | 1GB RAM each |
| PostgreSQL | Dedicated | 4GB RAM, 2 CPUs |
| Qdrant | Dedicated | 4GB RAM, 2 CPUs |
| Load balancer | Required | N/A |

**Expected capacity:**
- 10-20 documents/minute ingestion
- 100+ concurrent API users
- 20,000+ documents across collections

## Load Testing Guidelines

### Minimal Load Test (Recommended for Launch)

```bash
#!/bin/bash
# Minimal load test for validation

API_URL="http://localhost:8000"
COLLECTION_ID="test-collection"

# Test 1: Sequential uploads (5 documents)
echo "Testing sequential uploads..."
for i in {1..5}; do
  curl -X POST "$API_URL/api/v1/collections/$COLLECTION_ID/documents" \
    -F "file=@test-doc-$i.md" &
done
wait

# Test 2: Concurrent searches (10 requests)
echo "Testing concurrent searches..."
for i in {1..10}; do
  curl -X POST "$API_URL/api/v1/collections/$COLLECTION_ID/search" \
    -H "Content-Type: application/json" \
    -d '{"query": "test query", "limit": 5}' &
done
wait

echo "Load test complete"
```

### Monitoring During Load Test

```bash
# Terminal 1: Watch job processing
watch -n 5 'psql -d ragkb -c "SELECT status, COUNT(*) FROM ingestion_jobs GROUP BY status;"'

# Terminal 2: Watch resource usage
watch -n 2 'ps aux | grep -E "(uvicorn|qdrant|ingestion_worker)"'

# Terminal 3: Watch logs
tail -f /var/log/ragkb/worker.log | grep -E "(ingestion_succeeded|ingestion_failed)"
```

### First Bottleneck Detection

Watch for these signs during load testing:

| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| High job queue, low processing | Worker throughput | Add workers |
| OOM errors | Memory limit | Increase worker memory or reduce batch size |
| Database connection errors | Pool exhausted | Increase pool size |
| Slow searches | Qdrant indexing | Check Qdrant CPU/disk |
| API timeouts | API overloaded | Scale API instances |

## Resource Estimation

### Per-Document Resource Usage

| Resource | Usage per Document |
|----------|-------------------|
| Storage | ~100KB (original + derived) |
| Memory (during ingest) | ~50MB peak |
| Database rows | ~50 (doc + versions + chunks + job) |
| Qdrant points | 10-50 (depends on chunking) |
| Processing time | 30-60 seconds |

### Capacity Formula

```python
# Estimate resources needed
def estimate_capacity(documents, avg_chunks_per_doc=20):
    storage_gb = documents * 0.0001  # 100KB per doc
    memory_gb = 4  # Base for embedding model
    db_rows = documents * 50
    qdrant_points = documents * avg_chunks_per_doc
    
    return {
        "storage_gb": storage_gb,
        "memory_gb": memory_gb,
        "db_rows": db_rows,
        "qdrant_points": qdrant_points,
    }

# Example: 10,000 documents
estimate_capacity(10000)
# {
#   "storage_gb": 1.0,
#   "memory_gb": 4,
#   "db_rows": 500000,
#   "qdrant_points": 200000
# }
```

## Performance Tuning

### Worker Tuning

```python
# .env.production

# Faster polling for lower latency
WORKER_POLL_INTERVAL=1.0

# Larger chunks (fewer chunks per doc)
CHUNK_MAX_TOKENS=800
CHUNK_OVERLAP_TOKENS=200

# Bigger batches (if memory allows)
MAX_BATCH_SIZE=100
```

### Database Tuning

```ini
# postgresql.conf

# Connection pooling
max_connections = 100
shared_buffers = 256MB
work_mem = 4MB

# Write performance
wal_buffers = 16MB
checkpoint_completion_target = 0.9
```

### Qdrant Tuning

```yaml
# config.yaml

storage:
  # On-disk vs in-memory
  storage_path: /var/lib/qdrant
  
  # Indexing performance
  max_search_threads: 4
  max_optimization_threads: 2

service:
  # Timeout settings
  default_snapshot_timeout: 300
```

## Monitoring Scaling

### Key Metrics to Watch

| Metric | Warning | Critical |
|--------|---------|----------|
| Job queue depth | > 10 for 5min | > 50 |
| Worker CPU | > 70% | > 90% |
| Worker memory | > 3GB | > 3.8GB |
| API response time | > 500ms | > 2s |
| Search latency | > 200ms | > 1s |
| Database connections | > 80% | > 95% |

### Auto-Scaling Considerations

**Not recommended for initial launch.**

When ready for auto-scaling:

1. **Worker scaling**
   - Metric: Job queue depth
   - Target: Queue depth < 5
   - Scale up: Queue > 10 for 2 minutes
   - Scale down: Queue < 2 for 5 minutes

2. **API scaling**
   - Metric: Response time
   - Target: P95 < 500ms
   - Scale up: P95 > 1s for 2 minutes
   - Scale down: P95 < 300ms for 5 minutes

## Known Limitations

### Current Limits

| Resource | Hard Limit | Notes |
|----------|------------|-------|
| Single collection | ~1M documents | Qdrant collection limit |
| Single document | 100MB | Configurable via MAX_UPLOAD_SIZE_MB |
| Concurrent jobs | Unlimited | PostgreSQL queue |
| Search results | 100 | Configurable per request |
| API request size | 50MB | Default FastAPI limit |

### Scaling Boundaries

1. **Single database instance** - Vertical scaling only beyond ~100K documents
2. **Single Qdrant instance** - Horizontal sharding needed beyond ~1M points
3. **Single LLM instance** - Concurrent answer generation limited by GPU/CPU

## Rollout Checklist

### Before Scaling Up

- [ ] Current tier at < 70% capacity
- [ ] Load test passed
- [ ] Monitoring dashboards in place
- [ ] Runbooks updated
- [ ] Rollback plan tested

### Scaling Decision Matrix

| Current Load | Action |
|--------------|--------|
| < 50% capacity | Continue monitoring |
| 50-70% capacity | Plan next scaling event |
| > 70% capacity | Scale up this week |
| > 90% capacity | Scale up today |
| Hitting limits | Emergency scaling |

## Quick Reference

```bash
# Check current capacity usage
./deploy/scripts/health_check.sh

# View resource usage
df -h /var/lib/qdrant /var/lib/ragkb
free -h
ps aux | grep -E "(uvicorn|qdrant|ingestion_worker)"

# Scale workers
docker compose up -d --scale worker=3 worker

# Check job queue
psql -d ragkb -c "SELECT status, COUNT(*) FROM ingestion_jobs GROUP BY status;"
```
