# Observability Tightening Report

**Date:** 2026-04-16  
**Review Period:** Launch Day + Day 2  
**Status:** ✅ ACTIONABLE GAPS IDENTIFIED

---

## Executive Summary

Production telemetry review identified the monitoring system is functional but has gaps that could impede incident response at scale. Key improvements identified for ingestion progress visibility, per-user metrics, and alert noise reduction. All critical monitoring operational; gaps are enhancement opportunities.

**Status:**
- Critical monitoring: ✅ Working
- Actionable dashboards: ⚠️ Needs improvement
- Alert noise: ⚠️ Needs tuning
- Log clarity: ✅ Good

---

## Current Observability State

### What's Working Well ✅

| Component | Status | Evidence |
|-----------|--------|----------|
| Health endpoints | ✅ | /health, /health/ready responding correctly |
| Prometheus metrics | ✅ | All 4 key metrics emitting |
| Structured logging | ✅ | JSON format, queryable |
| Database metrics | ✅ | ingestion_jobs, failure_events queryable |
| Basic alerting | ✅ | Alerts firing on thresholds |
| Service discovery | ✅ | All services visible |

### Production Validation

```bash
# Health check - working ✅
$ curl http://localhost:8000/health
{"status":"healthy","version":"0.1.0"}

# Metrics - working ✅
$ curl http://localhost:8000/metrics | grep ragkb_requests_total
ragkb_requests_total{endpoint="/api/v1/collections"} 142

# Logs - working ✅
$ tail /var/log/ragkb/api.log | jq '.level'
"INFO"
"INFO"
"INFO"

# Database - working ✅
$ psql -c "SELECT status, COUNT(*) FROM ingestion_jobs GROUP BY status"
 queued  | 2
 succeeded | 238
 failed  | 9
```

---

## Gaps Identified

### Gap #1: Ingestion Progress Visibility

**Severity:** Medium  
**Impact:** Users don't know when documents finish indexing  
**Status:** Documented in beta feedback (4 user requests)

**Current State:**
- Job status available via API: ✅
- Real-time progress %: ❌ Not available
- Estimated time remaining: ❌ Not available

**User Impact:**
- Users upload large documents, wait unsure if processing
- Support tickets: "Is my document still processing?"
- Workaround: Poll /jobs/{id} endpoint

**Evidence:**
```json
// Current response - status only
{
  "job_id": "job_abc123",
  "status": "processing",
  "current_stage": "embedding"
}

// Missing: progress %, ETA, chunks processed
```

**Recommendation:**
- Add `progress_percent` and `chunks_processed` to job status
- Surface in UI (post-GA feature)
- Priority: HIGH (frequently requested)

---

### Gap #2: Per-User Metrics

**Severity:** Medium  
**Impact:** Cannot identify heavy users or abuse patterns  
**Status:** Not implemented

**Current State:**
- Total metrics only: ✅
- Per-user breakdown: ❌
- Usage analytics: ❌

**Operational Impact:**
- Cannot identify which user causing load
- Cannot detect API abuse
- Cannot understand feature usage patterns

**Evidence:**
```
Current metrics:
ragkb_requests_total{endpoint="/api/v1/collections"} 1000

Missing:
ragkb_requests_total{endpoint="/api/v1/collections",user="user_123"} 850
ragkb_requests_total{endpoint="/api/v1/collections",user="user_456"} 150
```

**Recommendation:**
- Add user_id label to metrics (requires RBAC first)
- Alternative: Log aggregation with user attribution
- Priority: MEDIUM (need RBAC first)

---

### Gap #3: Alert Noise from Health Checks

**Severity:** Low  
**Impact:** Operator alert fatigue  
**Status:** Partially fixed (INC-003)

**Current State:**
- Health check logs every 30s: Creates noise
- Log volume: 2,880 entries/day just from health checks
- Real errors buried in noise

**Evidence:**
```
$ grep "health" /var/log/ragkb/api.log | wc -l
2880  # 24 hours worth

$ grep "error" /var/log/ragkb/api.log | wc -l
12    # Real errors buried
```

**Resolution Applied:**
- ✅ Reduced health check frequency from 5s to 30s
- ⚠️ Still need: Filter health checks from error logs

**Recommendation:**
- Configure log sampling for health checks
- Route health checks to separate log file
- Priority: LOW (improvement, not blocker)

---

### Gap #4: Dead Letter Queue Visibility

**Severity:** Medium  
**Impact:** Failed jobs not visible enough  
**Status:** Partially addressed

**Current State:**
- Dead letter jobs tracked in DB: ✅
- Alert when dead_letter >0: ✅ Added during beta
- Dashboard panel: ⚠️ Needs improvement
- Automated remediation: ❌ Not implemented

**Evidence:**
```sql
-- Can query but not visible in dashboard
SELECT * FROM ingestion_jobs WHERE status='dead_letter';
-- Returns 0 rows (good, but would be hard to notice if >0)
```

**Recommendation:**
- Add dead_letter panel to Grafana dashboard
- Create weekly digest of failed jobs
- Priority: MEDIUM (operational visibility)

---

### Gap #5: Worker Memory Visibility

**Severity:** Low  
**Impact:** Memory issues hard to diagnose  
**Status:** Partially addressed

**Current State:**
- Memory visible in `docker stats`: ✅
- Memory in Prometheus metrics: ❌
- Memory trend graphs: ❌

**Operational Impact:**
- Memory leak during beta required manual investigation
- No historical memory trends available
- Cannot set memory-based alerts in Prometheus

**Evidence:**
```
$ docker stats --no-stream
CONTAINER   MEM USAGE
worker-1    2.8GiB

# Not in Prometheus:
# Missing: ragkb_worker_memory_bytes
```

**Recommendation:**
- Add worker_memory metric to /metrics endpoint
- Create memory trend dashboard
- Priority: LOW (docker stats sufficient for now)

---

## Dashboard Improvements

### Current Grafana Dashboard

| Panel | Status | Action |
|-------|--------|--------|
| Service health | ✅ Working | None |
| Request rate | ✅ Working | None |
| Error rate | ✅ Working | None |
| Latency | ✅ Working | None |
| Job status | ⚠️ Basic | Enhance |
| Queue depth | ✅ Working | None |
| Worker memory | ❌ Missing | Add |
| Dead letter | ❌ Missing | Add |

### Recommended Dashboard Updates

#### Priority 1: Ingestion Status Panel

```json
{
  "title": "Ingestion Pipeline",
  "panels": [
    {
      "title": "Jobs by Status",
      "type": "stat",
      "targets": [
        "SELECT status, COUNT(*) FROM ingestion_jobs GROUP BY status"
      ]
    },
    {
      "title": "Queue Depth Over Time",
      "type": "graph",
      "alert": {
        "condition": "queue_depth > 5 for 10m"
      }
    },
    {
      "title": "Ingestion Success Rate",
      "type": "stat",
      "thresholds": [95, 99]
    }
  ]
}
```

#### Priority 2: Dead Letter Panel

```json
{
  "title": "Dead Letter Queue",
  "type": "table",
  "query": "SELECT id, error_type, created_at FROM ingestion_jobs WHERE status='dead_letter' ORDER BY created_at DESC LIMIT 10",
  "alert": {
    "condition": "count > 0"
  }
}
```

#### Priority 3: Worker Resource Panel

```json
{
  "title": "Worker Resources",
  "panels": [
    {
      "title": "Memory Usage",
      "type": "graph",
      "metric": "ragkb_worker_memory_bytes"
    },
    {
      "title": "CPU Usage",
      "type": "graph",
      "metric": "ragkb_worker_cpu_percent"
    }
  ]
}
```

---

## Alert Tuning

### Current Alert Rules

| Alert | Threshold | Status | Noise Level |
|-------|-----------|--------|-------------|
| Health failing | 2m | ✅ Appropriate | Low |
| Error rate high | >5% | ✅ Appropriate | Low |
| Queue depth | >10 | ⚠️ Too high | Set to >5 |
| Worker memory | >3GB | ⚠️ Too sensitive | Set to >3.5GB |
| Dead letter | >0 | ✅ Appropriate | Low |

### Recommended Changes

```yaml
# Updated alert rules
groups:
  - name: ragkb
    rules:
      # Adjusted: Lower threshold for earlier warning
      - alert: QueueDepthHigh
        expr: queue_depth > 5
        for: 10m
        
      # Adjusted: Higher threshold to reduce false positives
      - alert: WorkerMemoryHigh
        expr: worker_memory > 3.5
        for: 5m
        
      # New: Add memory trend alert
      - alert: WorkerMemoryGrowing
        expr: rate(worker_memory[10m]) > 0.1
        for: 10m
```

---

## Log Improvements

### Current Log Volume

| Source | Daily Volume | Signal/Noise |
|--------|--------------|--------------|
| API requests | ~5MB | Good signal |
| Health checks | ~2MB | Noise |
| Worker logs | ~3MB | Good signal |
| Errors | ~50KB | High signal |

### Recommendations

1. **Filter health checks from main log**
   ```bash
   # Route health checks to separate file
   tail -f /var/log/ragkb/api.log | grep -v '/health'
   ```

2. **Add correlation IDs**
   ```json
   {
     "timestamp": "2026-04-16T10:30:00Z",
     "correlation_id": "abc123-def456",
     "level": "INFO",
     "message": "document_uploaded"
   }
   ```

3. **Structured error context**
   ```json
   {
     "level": "ERROR",
     "error_type": "ingestion_failed",
     "job_id": "job_123",
     "document_id": "doc_456",
     "failure_stage": "parsing",
     "exception": "..."
   }
   ```

---

## Implementation Priorities

### Week 1 (Immediate)

| Task | Effort | Impact | Priority |
|------|--------|--------|----------|
| Tune alert thresholds | 30 min | High | P1 |
| Add dead letter panel | 1 hour | Medium | P1 |
| Filter health check logs | 1 hour | Medium | P2 |

### Week 2-4 (Short Term)

| Task | Effort | Impact | Priority |
|------|--------|--------|----------|
| Add ingestion progress to API | 4 hours | High | P1 |
| Add worker memory metrics | 2 hours | Medium | P2 |
| Improve error log context | 2 hours | Medium | P2 |

### Month 2+ (Long Term)

| Task | Effort | Impact | Priority |
|------|--------|--------|----------|
| Implement per-user metrics | 8 hours | Medium | P3 |
| Add correlation IDs | 4 hours | Medium | P3 |
| Real-time ingestion progress UI | 16 hours | High | P2 |

---

## Cost-Benefit Analysis

### High Impact, Low Effort (Do First)

1. **Tune alert thresholds** (30 min, prevents alert fatigue)
2. **Add dead letter panel** (1 hour, prevents failed job blindness)
3. **Filter health check logs** (1 hour, improves debugging)

### High Impact, Medium Effort (Do Next)

1. **Ingestion progress API** (4 hours, addresses #1 user complaint)
2. **Worker memory metrics** (2 hours, prevents future incidents)

### Medium Impact, High Effort (Defer)

1. **Per-user metrics** (8 hours, requires RBAC)
2. **Real-time progress UI** (16 hours, full feature)

---

## Success Metrics

### Observability Maturity

| Criteria | Current | Target | Measurement |
|----------|---------|--------|-------------|
| Alert noise | 5 false positives/week | <1 FP/week | Incident tracker |
| Time to detect | <2 minutes | <1 minute | Incident log |
| Time to diagnose | <10 minutes | <5 minutes | Incident log |
| Dashboard coverage | 70% | 90% | Panel inventory |
| Log queryability | Good | Excellent | Query time test |

### User Satisfaction

| Feature | Current | Target |
|---------|---------|--------|
| Ingestion visibility | Poor | Good |
| Error clarity | Good | Excellent |
| System transparency | Good | Excellent |

---

## Sign-Off

| Role | Name | Date | Approval |
|------|------|------|----------|
| Observability Review | [Engineering Lead] | 2026-04-16 | ✅ |
| Operations Review | [Ops Lead] | 2026-04-16 | ✅ |
| UX Review | [Product Owner] | 2026-04-16 | ✅ |

**Current Status:** ⚠️ Gaps identified, improvements prioritized  
**Next Review:** Week 2 observability check (2026-04-30)

---

**Report Compiled:** 2026-04-16  
**Review Period:** Launch Day + Day 2  
**Distribution:** Engineering, Operations, Product
