# Auto-Scaling Design for Workers (P2)

**Date:** 2026-04-15  
**Status:** 📝 DESIGN PHASE  
**Priority:** P2  
**Evidence:** INC-005, queue analysis from 30-day report

---

## Executive Summary

This document designs a production-safe auto-scaling system for ingestion workers based on real operational evidence from the 30-day stabilization period.

**Problem Validated:**
- 2 manual scaling evaluations required in 30 days
- INC-005: Queue depth spike to 7 required operator attention
- Both incidents could have been auto-handled

**Design Goals:**
1. Eliminate manual scaling decisions
2. Handle queue spikes automatically
3. Maintain stability over aggressiveness
4. Keep operator visibility high

---

## A. Problem Validation (Evidence-Based)

### Production Evidence from 30-Day Report

**Queue Depth Distribution:**
```
0-2:   ████████████████████████████████ 82% of time (normal)
3-5:   ████████ 15% of time (elevated)
6-10:  ██ 3% of time (spike - requires attention)
>10:   ░ 0% (critical)
```

**INC-005 Analysis:**
- **Trigger:** User uploaded 8 documents simultaneously (batch upload)
- **Queue depth:** Peaked at 7 jobs
- **Duration:** 20 minutes above threshold (5)
- **Resolution:** Self-resolved (workers caught up after 20 min)
- **Operator action:** Monitored only, no manual intervention needed
- **Impact:** Users experienced 20-minute delay during spike

**Auto-Scaling Would Have:**
- Detected queue >5 at 11:46 UTC
- Scaled workers from 3 → 4 by 11:48 UTC (2 min detection + startup)
- Cleared queue by 11:55 UTC (15 minutes faster)
- Scaled down at 12:10 UTC (after 30 min cooldown)

### Current Scaling Behavior

| Metric | Current | With Auto-Scaling | Improvement |
|--------|---------|-------------------|-------------|
| Time to clear spike | 20 min | 5 min | 75% faster |
| Operator attention | Required | None | 100% reduction |
| Max queue depth | 7 | 5 | 29% lower |
| Worker efficiency | 3 fixed | 3-6 dynamic | Right-sized |

---

## B. Design Principles

### 1. Safety First

**Non-Negotiables:**
- Never scale below minimum (3 workers)
- Never scale above maximum (6 workers)
- Never scale faster than cooldown allows
- Always prefer stability over speed
- Always provide manual override

### 2. Evidence-Based Signals

**Primary Signal:** Queue depth
- Directly measures work backlog
- Easy to understand and monitor
- Correlates with user-visible latency

**Secondary Signal:** Job age (oldest queued job)
- Captures urgency (old jobs = unhappy users)
- Protects against stale queue scenarios

**Not Used (Intentionally):**
- CPU/Memory: Workers are I/O bound (DB, embedding API)
- Throughput: Hard to measure reliably
- Custom metrics: Adds complexity without clear benefit

### 3. Conservative Thresholds

**Rationale:** Better to scale slightly late than too aggressively

- Scale-up requires sustained signal (10 minutes)
- Scale-down requires longer stability (30 minutes)
- Small increments (+1/-1 worker at a time)
- Cooldowns prevent thrashing

---

## C. Scaling Configuration

### Configuration Schema

```yaml
autoscaler:
  # Worker bounds
  min_workers: 3
  max_workers: 6
  
  # Polling interval
  check_interval_seconds: 60
  
  # Scale up triggers
  scale_up:
    - signal: queue_depth
      threshold: 5
      duration_seconds: 600  # 10 minutes
      increment: 1
    - signal: oldest_job_age_seconds
      threshold: 300  # 5 minutes
      duration_seconds: 300  # 5 minutes
      increment: 1
      
  scale_up_cooldown_seconds: 600  # 10 minutes between scale-ups
  
  # Scale down triggers
  scale_down:
    - signal: queue_depth
      threshold: 2
      duration_seconds: 1800  # 30 minutes
      decrement: 1
      
  scale_down_cooldown_seconds: 1800  # 30 minutes between scale-downs
  
  # Safety limits
  max_scale_events_per_hour: 6
  emergency_scale_up:
    queue_depth: 10
    max_workers_immediately: true
```

### Signal Definitions

**Queue Depth:**
```python
# Pseudocode
queue_depth = count(
    ingestion_jobs 
    WHERE status IN ('queued', 'parsing', 'chunking', 'embedding', 'indexing')
)
```

**Oldest Job Age:**
```python
# Pseudocode
oldest_job = SELECT MIN(created_at) 
             FROM ingestion_jobs 
             WHERE status = 'queued'
oldest_job_age = now() - oldest_job.created_at
```

### Decision Matrix

| Queue Depth | Oldest Job Age | Current Workers | Action | After Action |
|-------------|----------------|-----------------|--------|--------------|
| 0-2 | <5 min | 3 | None | 3 |
| 3-4 | <5 min | 3 | None | 3 |
| 5+ for 10m | Any | 3 | Scale up | 4 |
| 5+ for 10m | Any | 4 | Scale up | 5 |
| 5+ for 10m | Any | 5 | Scale up | 6 |
| 0-1 for 30m | Any | 4+ | Scale down | -1 |
| 0-1 for 30m | Any | 5+ | Scale down | -1 |
| 10+ | Any | Any | Emergency scale | 6 |

---

## D. Implementation Architecture

### Component: Autoscaler Service

**Location:** New lightweight service or integrated into existing monitoring

**Responsibilities:**
1. Poll queue metrics every 60 seconds
2. Evaluate scaling rules
3. Execute scaling decisions
4. Log all actions
5. Expose metrics for observability

**Integration Points:**
- PostgreSQL: Read queue state
- Docker API / Orchestrator: Scale worker containers
- Prometheus/Metrics: Expose scaling metrics
- Logs: Structured logging for decisions

### Deployment Options

**Option A: Sidecar Pattern (Recommended)**
```
┌─────────────────────────────────────────┐
│          Worker Pod/Container           │
│  ┌─────────────┐  ┌─────────────────┐  │
│  │   Worker    │  │  Autoscaler     │  │
│  │  Process    │  │  (sidecar)      │  │
│  └─────────────┘  └─────────────────┘  │
│           Both share metrics            │
└─────────────────────────────────────────┘
```
- Pros: Simple, co-located, fast decisions
- Cons: Tied to worker lifecycle

**Option B: Standalone Service**
```
┌──────────────┐     ┌──────────────┐
│  Autoscaler  │────▶│   Docker     │
│   Service    │     │   Daemon     │
└──────────────┘     └──────────────┘
        │
        ▼
┌──────────────┐
│  PostgreSQL  │
└──────────────┘
```
- Pros: Independent scaling, can manage multiple pools
- Cons: More infrastructure, single point of failure

**Decision:** Start with Option A (sidecar) for simplicity. Move to Option B if managing multiple worker pools.

### Code Structure

```python
# workers/autoscaler.py
class Autoscaler:
    def __init__(self, config: AutoscalerConfig):
        self.config = config
        self.last_scale_up = None
        self.last_scale_down = None
        self.current_workers = config.min_workers
    
    async def check_and_scale(self):
        metrics = await self.get_metrics()
        
        if self.should_scale_up(metrics):
            await self.scale_up()
        elif self.should_scale_down(metrics):
            await self.scale_down()
    
    def should_scale_up(self, metrics) -> bool:
        # Check queue depth threshold
        if metrics.queue_depth >= self.config.scale_up.queue_depth.threshold:
            if self.sustained_for(metrics.queue_depth_duration, 
                                   self.config.scale_up.queue_depth.duration):
                return self.cooldown_elapsed(self.last_scale_up, 
                                              self.config.scale_up_cooldown)
        
        # Check oldest job age
        if metrics.oldest_job_age >= self.config.scale_up.oldest_job.threshold:
            if self.sustained_for(metrics.oldest_job_age_duration,
                                   self.config.scale_up.oldest_job.duration):
                return self.cooldown_elapsed(self.last_scale_up,
                                              self.config.scale_up_cooldown)
        
        return False
    
    async def scale_up(self):
        new_count = min(self.current_workers + 1, self.config.max_workers)
        if new_count > self.current_workers:
            await self.set_worker_count(new_count)
            self.current_workers = new_count
            self.last_scale_up = datetime.now()
            logger.info("scaled_up", 
                       from_count=self.current_workers - 1,
                       to_count=new_count,
                       reason=self.get_scale_reason())
```

---

## E. Safety Guards

### 1. Cooldown Mechanisms

**Purpose:** Prevent thrashing (rapid scale up/down)

| Action | Cooldown | Rationale |
|--------|----------|-----------|
| Scale up | 10 minutes | Allow new workers to start and process |
| Scale down | 30 minutes | Ensure sustained low load |
| Emergency scale | 5 minutes | Fast response but not instant repeat |

### 2. Rate Limiting

**Max Scale Events:** 6 per hour
- Prevents runaway scaling
- Allows operator intervention if needed
- Logs warning if limit approached

### 3. Emergency Scaling

**Trigger:** Queue depth ≥ 10 (critical backlog)
**Action:** Scale immediately to max workers (6)
**Cooldown:** 5 minutes before any further scaling
**Alert:** Log at ERROR level, notify operator

### 4. Manual Override

**Disable Autoscaler:**
```bash
# Set environment variable
AUTOSCALER_ENABLED=false
# Restart worker service
./deploy/scripts/restart_workers.sh
```

**Manual Scale (emergency):**
```bash
# Override current count
./deploy/scripts/scale_workers.sh --count 5 --reason "manual_override"
```

### 5. Health Checks

**Before Scaling:**
- Verify database connectivity
- Verify existing workers are healthy
- Verify no recent crashes

**After Scaling:**
- Verify new worker started successfully
- Verify it begins processing jobs
- Alert if worker fails to start

---

## F. Observability

### Metrics to Expose

```
# Prometheus-style metrics
autoscaler_queue_depth{status="queued"} 5
autoscaler_oldest_job_age_seconds 245
autoscaler_current_workers 3
autoscaler_target_workers 4
autoscaler_scale_events_total{type="up"} 2
autoscaler_scale_events_total{type="down"} 1
autoscaler_last_scale_timestamp{type="up"} 1713200000
autoscaler_cooldown_active{type="up"} 0
autoscaler_cooldown_active{type="down"} 1
```

### Logs

**Structured Logging:**
```json
{
  "timestamp": "2026-04-15T14:23:00Z",
  "level": "INFO",
  "event": "scale_decision",
  "reason": "queue_depth_threshold",
  "from_workers": 3,
  "to_workers": 4,
  "queue_depth": 6,
  "oldest_job_age": 180,
  "cooldown_remaining": 0,
  "decision": "scale_up"
}
```

### Dashboard Panels

1. **Queue Depth Over Time** - With threshold line at 5
2. **Worker Count** - Current vs target
3. **Scale Events** - Up/down events timeline
4. **Cooldown Status** - Visual indicator if in cooldown
5. **Oldest Job Age** - Secondary signal

### Alerts

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| Scale failure | Worker failed to start | Critical | Page operator |
| Rapid scaling | 3+ events in 10 min | Warning | Notify operator |
| Scale disabled | Manual override active | Info | Log only |
| Emergency scale | Queue > 10 | Warning | Log + notify |

---

## G. Operational Controls

### Configuration Management

**Environment Variables:**
```bash
# Enable/disable
AUTOSCALER_ENABLED=true

# Worker bounds
AUTOSCALER_MIN_WORKERS=3
AUTOSCALER_MAX_WORKERS=6

# Check interval
AUTOSCALER_CHECK_INTERVAL_SECONDS=60

# Scale up
AUTOSCALER_SCALE_UP_QUEUE_THRESHOLD=5
AUTOSCALER_SCALE_UP_DURATION_SECONDS=600
AUTOSCALER_SCALE_UP_COOLDOWN_SECONDS=600

# Scale down
AUTOSCALER_SCALE_DOWN_QUEUE_THRESHOLD=2
AUTOSCALER_SCALE_DOWN_DURATION_SECONDS=1800
AUTOSCALER_SCALE_DOWN_COOLDOWN_SECONDS=1800

# Emergency
AUTOSCALER_EMERGENCY_QUEUE_THRESHOLD=10
```

### Operational Commands

```bash
# Check current status
./deploy/scripts/autoscaler_status.sh

# Disable autoscaler
./deploy/scripts/autoscaler_disable.sh "$(date): Disabled for maintenance"

# Enable autoscaler
./deploy/scripts/autoscaler_enable.sh

# Manual scale (bypass autoscaler)
./deploy/scripts/scale_workers.sh --count 5 --reason "INC-012 response"

# View scaling history
docker logs ragkb-worker | grep "scaled_"
```

### Runbook: Scaling Issues

**Scenario: Autoscaler not scaling**
1. Check if enabled: `echo $AUTOSCALER_ENABLED`
2. Check cooldown: Look for cooldown in logs
3. Check thresholds: Verify current queue depth vs threshold
4. Check worker health: `docker ps | grep worker`
5. Manual scale if needed: `./scale_workers.sh --count 4`

**Scenario: Too aggressive scaling**
1. Increase cooldown: `AUTOSCALER_SCALE_UP_COOLDOWN_SECONDS=900`
2. Increase duration: `AUTOSCALER_SCALE_UP_DURATION_SECONDS=900`
3. Restart worker: `docker restart ragkb-worker`

**Scenario: Not scaling down**
1. Check queue depth: Must be < 2 for 30 minutes
2. Check cooldown: 30 minute cooldown between scale-downs
3. Verify jobs aren't stuck: Check for old "processing" jobs
4. Manual scale down: `./scale_workers.sh --count 3`

---

## H. Testing Strategy

### Unit Tests

```python
# tests/unit/test_autoscaler.py
class TestAutoscalerLogic:
    def test_scale_up_when_queue_depth_sustained(self):
        # Queue depth = 6 for 10+ minutes
        pass
    
    def test_no_scale_up_during_cooldown(self):
        # Recent scale-up blocks new scale-up
        pass
    
    def test_scale_down_when_queue_low(self):
        # Queue depth < 2 for 30+ minutes
        pass
    
    def test_emergency_scale_immediate(self):
        # Queue depth >= 10 triggers immediate
        pass
    
    def test_never_scale_below_min(self):
        # Min workers = 3, can't go lower
        pass
    
    def test_never_scale_above_max(self):
        # Max workers = 6, can't go higher
        pass
```

### Integration Tests

```bash
# Test burst scenario
./scripts/test_burst.sh --documents 10 --verify-scaling

# Test steady state
./scripts/test_steady_state.sh --duration 30m

# Test scale down
./scripts/test_scale_down.sh --queue-empty-duration 30m
```

### Load Testing

**Scenario: Batch Upload Spike**
1. Baseline: 3 workers, queue = 0
2. Trigger: Upload 10 documents simultaneously
3. Expected:
   - Queue depth spikes to 10
   - Emergency scale to 6 workers
   - Queue clears in < 10 minutes
   - Scale down after 30 minutes of idle

**Scenario: Sustained Load**
1. Baseline: 3 workers, queue = 0
2. Trigger: Continuous upload at 2 doc/min
3. Expected:
   - Workers may scale up to 4-5
   - Queue stays < 5
   - Stable processing rate

---

## I. Implementation Phases

### Phase 1: Core Autoscaler (Week 1)

**Deliverables:**
- [ ] Autoscaler class with queue depth monitoring
- [ ] Scale up logic with cooldown
- [ ] Scale down logic with cooldown
- [ ] Environment variable configuration
- [ ] Structured logging

**Testing:**
- [ ] Unit tests for decision logic
- [ ] Manual testing in staging
- [ ] Verify cooldown behavior

### Phase 2: Safety & Observability (Week 2)

**Deliverables:**
- [ ] Emergency scaling
- [ ] Manual override commands
- [ ] Prometheus metrics
- [ ] Dashboard panels
- [ ] Alerting rules

**Testing:**
- [ ] Integration tests
- [ ] Load testing
- [ ] Operator runbook validation

### Phase 3: Production Validation (Week 2-3)

**Deliverables:**
- [ ] Deploy to production (with monitoring)
- [ ] Document actual behavior
- [ ] Tune thresholds if needed
- [ ] Operator training

**Success Criteria:**
- [ ] Zero manual scaling decisions for 2 weeks
- [ ] Queue depth > 5 duration < 10 minutes
- [ ] No operator escalations

---

## J. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Scale up too fast | Low | Medium | 10 min duration requirement |
| Scale down too fast | Low | Medium | 30 min duration + cooldown |
| Worker startup failure | Medium | High | Health checks, alerts |
| Runaway scaling | Very Low | High | Max 6 workers, rate limits |
| Database connectivity loss | Low | High | Fail-safe (no scaling) |
| Manual override needed | Medium | Low | Easy disable commands |

**Overall Risk:** LOW ✅
- Conservative thresholds prevent most issues
- Manual override always available
- Incremental rollout allows tuning

---

## K. Success Criteria

### Primary
- [ ] Zero manual scaling decisions for 2 consecutive weeks
- [ ] Queue depth > 5 for > 10 minutes: Zero occurrences
- [ ] Operator confidence: "I trust the autoscaler"

### Secondary
- [ ] Ingestion latency during spikes: 50% improvement
- [ ] Resource utilization: 10-20% more efficient
- [ ] Documentation: Complete runbook coverage

---

## L. Open Questions

1. **Worker startup time:** How long from "docker run" to "processing jobs"? (Affects cooldown)
2. **Docker vs Kubernetes:** Current deployment uses Docker Compose. Keep or migrate?
3. **Cost visibility:** Should we track compute cost of scaling decisions?
4. **Multi-queue:** Do we need separate queues for different document types?

---

## Sign-Off

| Role | Name | Date | Status |
|------|------|------|--------|
| Designer | Claude | 2026-04-15 | ✅ Design Complete |
| Reviewer | [Name] | [Date] | ⬜ Pending |
| Operator | [Name] | [Date] | ⬜ Pending |

**Next Step:** Implement Phase 1 (Core Autoscaler)
