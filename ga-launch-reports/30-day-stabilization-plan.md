# 30-Day Stabilization Plan

**Date:** 2026-04-15  
**Plan Version:** 1.0  
**Status:** ACTIVE  
**Review Cycle:** Daily (Week 1), Weekly (Weeks 2-4)

---

## Executive Summary

This plan defines operational procedures for the first 30 days post-GA launch. The goal is to maintain high availability, quickly identify and resolve issues, and establish production baselines for capacity planning.

**Stabilization Objectives:**
1. Maintain >99% uptime
2. Keep ingestion success rate >95%
3. Keep P95 API latency <500ms
4. Zero unplanned outages
5. Document all production issues and resolutions

---

## Daily Operations (Week 1)

### Morning Checks (09:00 UTC)

**Purpose:** Verify overnight health

| Check | Command/Location | Threshold | Action if Threshold Exceeded |
|-------|------------------|-----------|------------------------------|
| Service health | `./deploy/scripts/health_check.sh` | All pass | Investigate immediately |
| API uptime | Prometheus/ Grafana | >99% | Review logs for restarts |
| Ingestion success | `SELECT success_rate FROM daily_metrics` | >95% | Check failure_events table |
| Queue depth | `SELECT COUNT(*) FROM ingestion_jobs WHERE status='queued'` | <10 | Scale workers if >5 for 30min |
| Error rate | Prometheus: `ragkb_request_errors_total` | <1% | Investigate error patterns |
| Worker memory | Prometheus/ `docker stats` | <3.5GB | Check for memory leak |
| Disk usage | `df -h` | <70% | Plan cleanup if >80% |
| Backup status | `/var/log/ragkb/backup.log` | Success | Run manual backup if failed |

**Morning Check Template:**
```markdown
## Morning Check - 2026-04-XX
- [ ] Health check passed
- [ ] Uptime: __% (target: >99%)
- [ ] Ingestion success: __% (target: >95%)
- [ ] Queue depth: __ (target: <10)
- [ ] Error rate: __% (target: <1%)
- [ ] Worker memory: __GB (target: <3.5GB)
- [ ] Disk usage: __% (target: <70%)
- [ ] Backup: [SUCCESS / FAILED / PENDING]

Notes: ___________________________
```

### Afternoon Checks (15:00 UTC)

**Purpose:** Monitor day-time traffic

| Check | Source | Threshold | Action |
|-------|--------|-----------|--------|
| API request volume | Prometheus | Trending | Compare to yesterday |
| Search latency P95 | Prometheus | <500ms | Investigate if >400ms |
| Ask latency P95 | Prometheus | <3000ms | Check LLM endpoint health |
| Concurrent users | Access logs | Trending | Note peak usage |
| Auth failures | Prometheus | <0.1% | Check for abuse attempts |
| Dead letter jobs | `SELECT COUNT(*) FROM ingestion_jobs WHERE status='dead_letter'` | 0 | Investigate if >0 |

### Evening Checks (21:00 UTC)

**Purpose:** Prepare for overnight

| Check | Source | Threshold | Action |
|-------|--------|-----------|--------|
| Daily summary | Grafana dashboard | Review | Document trends |
| Failed jobs | Database query | 0 unhandled | Retry or document |
| Tomorrow's backup | Cron schedule | Configured | Verify backup job ready |

---

## Weekly Operations (Weeks 2-4)

### Weekly Review (Mondays 10:00 UTC)

**Purpose:** Trend analysis and capacity planning

#### Metrics Review

| Metric | Target | Review Action |
|--------|--------|---------------|
| Weekly uptime | >99% | Document any outages |
| Ingestion success | >95% | Identify failure patterns |
| API latency P95 | <500ms | Capacity planning input |
| Search latency P95 | <300ms | Performance review |
| Worker restarts | 0 unplanned | Root cause analysis |
| Backup success | 100% | Verify 7 backups taken |
| Disk growth | <5GB/week | Capacity planning |

#### Capacity Review

| Item | Current | Trend | Projection |
|------|---------|-------|------------|
| Active users | ___ | ___ | ___ by Day 30 |
| Documents | ___ | ___ | ___ by Day 30 |
| Storage used | ___ | ___ | ___ by Day 30 |
| Peak QPS | ___ | ___ | ___ by Day 30 |

**Scaling Decisions:**
- Scale workers if avg queue depth >3 for 3+ days
- Scale API if P95 latency >400ms for 3+ days
- Add disk if projected to exceed 80% in 2 weeks

### Weekly Tasks

| Task | Frequency | Owner | Output |
|------|-----------|-------|--------|
| Review Grafana dashboards | Weekly | Operator | Notes |
| Analyze slow queries | Weekly | DBA | Optimization recommendations |
| Verify backup integrity | Weekly | Operator | verify-backup.sh report |
| Review failed jobs | Weekly | Operator | Failure analysis |
| Update runbooks | As needed | Operator | Documentation updates |
| Stakeholder update | Weekly | Product | Status report |

---

## Key Metrics Dashboard

### Primary Metrics (Tracked Daily)

```
┌─────────────────────────────────────────────────────────┐
│ DAILY HEALTH DASHBOARD                                   │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Uptime:          99.7%        [████████░░] Target: 99% │
│  Ingestion:       96.4%        [█████████░] Target: 95% │
│  Error Rate:      0.3%         [░░░░░░░░░░] Target: <1% │
│  Search P95:     280ms          [████████░░] Target: <500│
│  Ask P95:        2.1s           [████████░░] Target: <3s │
│                                                          │
│  Queue Depth:     2            [░░░░░░░░░░] Target: <10  │
│  Workers:        3/3           [██████████] Healthy    │
│  Memory:         2.7GB avg     [██████░░░░] Target: <3.5│
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Secondary Metrics (Tracked Weekly)

| Metric | Current | Week-1 | Week-2 | Week-3 | Week-4 |
|--------|---------|--------|--------|--------|--------|
| Active users | 7 | - | - | - | - |
| Total documents | 4 | - | - | - | - |
| API requests/day | 89 | - | - | - | - |
| Search queries/day | 23 | - | - | - | - |
| Avg session duration | - | - | - | - | - |
| Peak concurrent | 4 | - | - | - | - |

---

## Operator Escalation Conditions

### Immediate Escalation (Page On-Call)

| Condition | Severity | Response Time | Action |
|-----------|----------|---------------|--------|
| Health check failing | Critical | Immediate | Start incident response |
| PostgreSQL unavailable | Critical | Immediate | Database recovery |
| Qdrant unavailable | Critical | Immediate | Vector store recovery |
| All workers down | Critical | Immediate | Worker restart |
| Data loss suspected | Critical | Immediate | Stop writes, assess |
| Auth bypass detected | Critical | Immediate | Security response |

### Urgent Escalation (Notify Within 15 Minutes)

| Condition | Severity | Response Time | Action |
|-----------|----------|---------------|--------|
| Ingestion success <90% | High | 15 min | Investigate failures |
| API latency P95 >2s | High | 15 min | Scale or investigate |
| Queue depth >50 | High | 15 min | Scale workers |
| Worker memory >3.8GB | High | 15 min | Check for leak |
| Error rate >5% | High | 15 min | Investigate errors |
| Disk usage >85% | High | 15 min | Plan cleanup |

### Standard Escalation (Notify Within 1 Hour)

| Condition | Severity | Response Time | Action |
|-----------|----------|---------------|--------|
| Single worker down | Medium | 1 hour | Restart worker |
| Ingestion success <95% | Medium | 1 hour | Review failures |
| API latency P95 >500ms | Medium | 1 hour | Performance review |
| Queue depth >10 for 1h | Medium | 1 hour | Consider scaling |
| Auth failures >1% | Medium | 1 hour | Check for attacks |
| Dead letter jobs >0 | Medium | 1 hour | Investigate |

### Informational (Log and Review)

| Condition | Severity | Response Time | Action |
|-----------|----------|---------------|--------|
| Slow search (>1s) | Low | Daily review | Monitor |
| Model download slow | Low | Daily review | Expected |
| Single failed job | Low | Weekly review | Normal |
| Backup warning | Low | Daily review | Verify |

---

## Rollback Triggers

### Automatic Rollback Conditions

If any of the following occur, consider immediate rollback:

1. **Health check fails for >5 minutes**
2. **Error rate >10% for >10 minutes**
3. **Data corruption detected**
4. **Security incident**

### Rollback Procedure

```bash
# 1. Announce rollback
# 2. Stop incoming traffic (at load balancer)
# 3. Execute rollback
./deploy/scripts/rollback.sh [PREVIOUS_VERSION]

# 4. Verify rollback
./deploy/scripts/health_check.sh
./deploy/scripts/smoke_verify.sh

# 5. Resume traffic
# 6. Post-incident review
```

---

## Documentation Requirements

### Daily Log Entry Template

```markdown
## Day X - 2026-04-XX

### Morning Check (09:00)
- Uptime: ___%
- Ingestion: ___%
- Queue: ___
- Status: [HEALTHY / WATCH / ISSUE]

### Issues Found
- [None / List here]

### Actions Taken
- [None / List here]

### Notes
- ___________________________

Signed: ___________
```

### Weekly Report Template

```markdown
## Week X Stabilization Report

### Week of: 2026-04-XX to 2026-04-XX

### Metrics Summary
| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Uptime | >99% | ___% | ___ |
| Ingestion | >95% | ___% | ___ |
| Latency P95 | <500ms | ___ms | ___ |

### Issues This Week
1. [Issue description]
   - Root cause: ___
   - Resolution: ___
   - Prevention: ___

### Capacity Observations
- Current users: ___
- Trend: [Growing / Stable / Declining]
- Projected capacity needs: ___

### Recommendations
- ___________________________

### Next Week Focus
- ___________________________
```

---

## Communication Plan

### Stakeholder Updates

| Audience | Frequency | Channel | Owner |
|----------|-----------|---------|-------|
| Engineering team | Daily | Slack #ragkb-ops | On-call |
| Product/Leadership | Weekly | Email | Product Owner |
| Customers | As needed | Status page | Support |
| Operations | Daily | Handoff log | On-call |

### Incident Communication

**Severity 1 (Critical):**
- Immediate Slack notification
- Page on-call engineer
- Post to status page within 15 minutes
- Hourly updates until resolved

**Severity 2 (High):**
- Slack notification within 15 minutes
- Daily update until resolved

**Severity 3 (Medium):**
- Logged in issue tracker
- Weekly review

---

## Success Criteria

### Day 7 (End of Week 1)
- [ ] >99% uptime maintained
- [ ] <5 total incidents
- [ ] All incidents documented
- [ ] Ingestion success >95%
- [ ] Daily check procedures validated

### Day 14 (End of Week 2)
- [ ] >99% uptime maintained
- [ ] <10 total incidents
- [ ] Weekly review procedures validated
- [ ] Capacity trends identified
- [ ] First scaling decision documented

### Day 30 (End of Stabilization)
- [ ] >99% uptime maintained
- [ ] <20 total incidents
- [ ] All critical/high issues resolved
- [ ] Capacity plan for next 90 days
- [ ] Post-stabilization report complete
- [ ] Transition to steady-state operations

---

## Post-Stabilization Transition

After Day 30, transition to:
- **Weekly operations reviews** (from daily)
- **Monthly capacity planning** (from weekly)
- **Quarterly DR drills**
- **Standard on-call rotation**

---

**Plan Active:** 2026-04-15 to 2026-05-15  
**Next Review:** Daily (first 7 days), then weekly  
**Owner:** Operations Team
