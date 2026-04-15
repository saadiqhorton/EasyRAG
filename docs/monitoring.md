# Monitoring and Alerting Guide

## Overview

The RAG Knowledge Base Framework includes built-in monitoring capabilities for operational visibility:

- **Prometheus-compatible metrics** at `/metrics`
- **Detailed health endpoint** at `/health/detailed`
- **Structured logging** for observability
- **Database-driven metrics** for job tracking

## Metrics Endpoints

### Prometheus Metrics (`GET /metrics`)

Returns Prometheus-compatible metrics for scraping:

```
# HELP ragkb_requests_total Total API requests
# TYPE ragkb_requests_total counter
ragkb_requests_total{endpoint="/api/v1/collections"} 42

# HELP ragkb_request_errors_total Total API request errors
# TYPE ragkb_request_errors_total counter
ragkb_request_errors_total{endpoint="/api/v1/collections"} 0

# HELP ragkb_jobs_total Total jobs processed
# TYPE ragkb_jobs_total counter
ragkb_jobs_total{status="succeeded"} 15
ragkb_jobs_total{status="failed"} 2
ragkb_jobs_total{status="dead_letter"} 0

# HELP ragkb_uptime_seconds Service uptime
# TYPE ragkb_uptime_seconds gauge
ragkb_uptime_seconds 3600
```

### Detailed Health (`GET /health/detailed`)

Returns comprehensive health status:

```json
{
  "status": "healthy",
  "postgres": true,
  "qdrant": true,
  "qdrant_points": 156,
  "uptime_seconds": 3600,
  "requests": {
    "total_requests": 42,
    "total_errors": 0,
    "error_rate": 0.0,
    "avg_latency_ms": 45.2,
    "by_endpoint": {
      "/api/v1/collections": {
        "count": 5,
        "errors": 0,
        "avg_latency_ms": 23.1
      }
    }
  },
  "jobs": {
    "queued": 0,
    "succeeded": 15,
    "failed": 2,
    "dead_letter": 0,
    "total_processed": 17,
    "success_rate": 0.8824,
    "dead_letter_rate": 0.0
  }
}
```

## Database-Driven Metrics

### Job Status Monitoring

```bash
# Current job status counts
psql -d ragkb -c "
  SELECT status, COUNT(*) as count
  FROM ingestion_jobs
  GROUP BY status
  ORDER BY count DESC;
"

# Recent failures
psql -d ragkb -c "
  SELECT 
    j.id,
    j.status,
    j.current_stage,
    j.retry_count,
    f.error_type,
    f.message
  FROM ingestion_jobs j
  LEFT JOIN failure_events f ON j.id = f.job_id
  WHERE j.status IN ('failed', 'dead_letter')
  ORDER BY j.created_at DESC
  LIMIT 10;
"

# Success rate over time
psql -d ragkb -c "
  SELECT 
    DATE(created_at) as date,
    status,
    COUNT(*) as count
  FROM ingestion_jobs
  WHERE created_at > NOW() - INTERVAL '7 days'
  GROUP BY DATE(created_at), status
  ORDER BY date DESC;
"
```

### Collection Metrics

```bash
# Documents per collection
psql -d ragkb -c "
  SELECT 
    c.name,
    COUNT(d.id) as document_count,
    COUNT(DISTINCT CASE WHEN v.index_status = 'indexed' THEN d.id END) as indexed_count
  FROM collections c
  LEFT JOIN source_documents d ON c.id = d.collection_id
  LEFT JOIN document_versions v ON d.id = v.document_id
  WHERE d.deleted_at IS NULL
  GROUP BY c.id, c.name;
"
```

## Alert Conditions

### Critical Alerts (Page Immediately)

| Condition | Query | Threshold |
|-----------|-------|-----------|
| Health check failing | `GET /health/ready` | Status != 200 for 2m |
| PostgreSQL unavailable | `/health/detailed` | `postgres: false` |
| Qdrant unavailable | `/health/detailed` | `qdrant: false` |
| Dead letter growing | Database query | `dead_letter > 0` |

### Warning Alerts (Investigate Soon)

| Condition | Query | Threshold |
|-----------|-------|-----------|
| High error rate | `/health/detailed` | `error_rate > 0.05` |
| Low job success rate | `/health/detailed` | `success_rate < 0.8` |
| Worker down | Process check | `pgrep ingestion_worker` fails |
| Disk space | `df -h` | `usage > 85%` |

### Info Alerts (Monitor Trends)

| Condition | Query | Threshold |
|-----------|-------|-----------|
| High request volume | `/health/detailed` | `total_requests > 1000/hour` |
| Slow response times | `/health/detailed` | `avg_latency_ms > 1000` |
| Queue backlog | Database | `queued > 10 for 10m` |

## Dashboard Setup

### Prometheus Configuration

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'ragkb-api'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s
```

### Grafana Dashboard Panels

**Health Overview:**
- Singlestat: Service status (healthy/unhealthy)
- Graph: Request rate over time
- Graph: Error rate over time
- Graph: Average latency over time

**Job Processing:**
- Singlestat: Jobs succeeded (24h)
- Singlestat: Jobs failed (24h)
- Singlestat: Dead letter jobs
- Graph: Job status distribution

**Storage:**
- Singlestat: Qdrant points
- Graph: Points over time
- Singlestat: Documents indexed

**Alerts:**
- Alert list: All firing alerts
- Table: Recent failure events

## Log-Based Monitoring

### Structured Log Format

All services emit JSON-structured logs:

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

```bash
# API errors
tail -f /var/log/ragkb/api.log | jq 'select(.level == "ERROR")'

# Worker errors
tail -f /var/log/ragkb/worker.log | jq 'select(.level == "ERROR")'

# Ingestion events
tail -f /var/log/ragkb/worker.log | grep "ingestion_"

# Search events
tail -f /var/log/ragkb/api.log | grep "search_"
```

## Incident Response

### Alert: Health Check Failing

1. Check `/health/detailed` for which component is down
2. Check logs for error details
3. Restart failing service
4. Verify recovery with `/health/ready`

### Alert: Dead Letter Jobs

1. Query database for dead letter jobs
2. Investigate failure reasons
3. Fix underlying issue (e.g., OCR, parse failures)
4. Manually retry jobs if appropriate

### Alert: High Error Rate

1. Check logs for error patterns
2. Identify affected endpoints
3. Check database connectivity
4. Check Qdrant health
5. Consider rolling back if recent deployment

## Monitoring Best Practices

1. **Set up before production** - Don't wait for problems
2. **Alert on symptoms, not causes** - Alert when users affected
3. **Use actionable alerts** - Include runbook links
4. **Test alerts regularly** - Ensure they work when needed
5. **Keep historical data** - At least 30 days of metrics
6. **Monitor the monitors** - Ensure Prometheus/Grafana are healthy

## Quick Reference

```bash
# Health check
curl http://localhost:8000/health/ready | jq

# Detailed health
curl http://localhost:8000/health/detailed | jq

# Metrics
curl http://localhost:8000/metrics

# Job status
psql -d ragkb -c "SELECT status, COUNT(*) FROM ingestion_jobs GROUP BY status;"

# Recent failures
psql -d ragkb -c "SELECT * FROM failure_events ORDER BY created_at DESC LIMIT 5;"

# Service logs
tail -f /var/log/ragkb/api.log
tail -f /var/log/ragkb/worker.log
```
