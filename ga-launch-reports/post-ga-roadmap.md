# Post-GA Roadmap Recommendation

**Date:** 2026-04-16  
**Based On:** Beta feedback + Launch Day production evidence  
**Timeframe:** Next 90 days  
**Status:** Evidence-based prioritization

---

## Executive Summary

This roadmap prioritizes the next phase of work based on real user feedback and production behavior, not assumptions. Top priorities address the most frequent user pain point (ingestion visibility) and operational need (auto-scaling).

**Top 5 Priorities:**
1. Ingestion progress indicator (#1 user request, 4 votes)
2. Auto-scaling for workers (operational efficiency)
3. Text highlighting in sources (#2 user request, 3 votes)
4. Per-user metrics (operational visibility)
5. Bulk upload UI (user productivity)

---

## Evidence Sources

### Source 1: Beta User Feedback (8 users)

| Feature Request | Votes | Severity | Source |
|-----------------|-------|----------|--------|
| Ingestion progress indicator | 4 | High | User interviews |
| Text highlighting in sources | 3 | Medium | User feedback |
| Bulk upload UI | 2 | Medium | User feedback |
| Collection sharing | 2 | Low | User feedback |
| Per-user metrics | N/A | Low | Operational need |

### Source 2: Production Observations (24 hours)

| Observation | Impact | Priority Driver |
|-------------|--------|---------------|
| Queue depth averaged 2 | Efficiency | Auto-scaling would save cost |
| Manual worker management | Toil | Reduce operator burden |
| No per-user visibility | Operations | Hard to debug user issues |
| Memory stable at 2.7GB | Stability | Not urgent to optimize |

### Source 3: Incident Analysis (3 incidents)

| Learning | Priority Driver |
|----------|-----------------|
| First-run model download delays | Pre-download models |
| Memory spike during first batch | Better monitoring |
| Health check log noise | Logging improvements |

---

## Prioritized Roadmap

### P0: Critical (Next 2 Weeks)

**None identified** - System is stable and meeting requirements.

### P1: High (Next 30 Days)

#### 1. Ingestion Progress Indicator

**Evidence:** 4/8 beta users requested this; #1 complaint

**User Pain:**
- Upload large document → Wait unsure if processing
- Support tickets asking "Is my document done?"
- Current workaround: Poll API manually

**Proposed Solution:**
```json
{
  "job_id": "job_abc123",
  "status": "processing",
  "current_stage": "embedding",
  "progress_percent": 65,
  "chunks_processed": 13,
  "chunks_total": 20,
  "estimated_seconds_remaining": 45
}
```

**Effort:** 4-6 hours (backend API)  
**Impact:** HIGH - Addresses #1 user complaint  
**Confidence:** High - Clear user need

---

#### 2. Auto-Scaling for Workers

**Evidence:** Production shows queue depth varies; manual scaling creates toil

**Operational Pain:**
- Manual monitoring of queue depth
- Deciding when to scale
- Risk of under/over-provisioning

**Proposed Solution:**
```yaml
autoscaler:
  min_workers: 3
  max_workers: 6
  scale_up_when: queue_depth > 5 for 10m
  scale_down_when: queue_depth < 2 for 30m
```

**Effort:** 8-12 hours  
**Impact:** HIGH - Reduces operational toil  
**Confidence:** High - Clear operational need

---

### P2: Medium (Next 60 Days)

#### 3. Text Highlighting in Sources

**Evidence:** 3/8 beta users requested; "Would help verify answers"

**User Pain:**
- Citation shows which document but not where in document
- User must manually search for cited text
- Friction in evidence verification

**Proposed Solution:**
- Store text offsets during chunking
- Return highlight ranges in API response
- Frontend highlights matching text

**Effort:** 16-20 hours (full stack)  
**Impact:** MEDIUM - Improves trust in answers  
**Confidence:** High - Clear user request

---

#### 4. Per-User Metrics

**Evidence:** Operational need - cannot identify heavy users

**Operational Pain:**
- Cannot debug "which user is causing load?"
- Cannot identify API abuse
- Cannot understand feature usage

**Proposed Solution:**
- Add user_id label to Prometheus metrics
- Requires: RBAC with user identification
- Alternative: Log aggregation first

**Effort:** 8 hours (with RBAC)  
**Impact:** MEDIUM - Operational visibility  
**Confidence:** Medium - Need RBAC first

---

#### 5. Bulk Upload UI

**Evidence:** 2/8 beta users requested; users uploading multiple files

**User Pain:**
- Upload files one at a time
- Multiple drag-and-drop operations
- No progress visibility on batch

**Proposed Solution:**
- Multi-file select in upload dialog
- Batch progress indicator
- Queue visualization

**Effort:** 12-16 hours (frontend)  
**Impact:** MEDIUM - User productivity  
**Confidence:** Medium - Nice to have

---

### P3: Low (Next 90 Days)

#### 6. Collection Sharing

**Evidence:** 2/8 beta users requested; collaboration need

**User Pain:**
- Cannot share collections with team
- Each user creates duplicate collections
- No collaboration features

**Proposed Solution:**
- Share collection via link
- Permission levels (read/write/admin)
- Requires: User management

**Effort:** 16-24 hours (with RBAC)  
**Impact:** LOW - Collaboration feature  
**Confidence:** Medium - Nice to have

---

#### 7. Advanced RBAC

**Evidence:** Foundation for per-user metrics and sharing

**Proposed Solution:**
- User roles (admin, editor, viewer)
- API key per user
- Audit logging

**Effort:** 20-30 hours  
**Impact:** LOW - Enables other features  
**Confidence:** High - Enables P1/P2 features

---

#### 8. Performance Optimizations

**Evidence:** Not currently needed; system performing well

**Potential Optimizations:**
- Response caching for common queries
- Query optimization for large collections
- Connection pooling improvements

**Effort:** Variable  
**Impact:** LOW - System fast enough  
**Confidence:** Low - Wait for pain point

**Recommendation:** Defer until performance issues arise

---

## Roadmap Matrix

### Effort vs Impact

```
High Impact │  Ingestion Progress ●
            │  Auto-scaling ●
            │
Medium      │  Text Highlighting ●
            │  Per-user Metrics ●
            │  Bulk Upload ●
            │
Low Impact  │  Collection Sharing ●
            │  Advanced RBAC ●
            │  Performance Opts ●
            └────────────────────────────────
              Low        Medium       High
                          Effort
```

### Confidence vs Evidence

```
High        │  Ingestion Progress ●
Confidence  │  Text Highlighting ●
            │  Auto-scaling ●
            │
Medium      │  Per-user Metrics ●
            │  Bulk Upload ●
            │  Collection Sharing ●
            │
Low         │  Performance Opts ●
Confidence  │
            └────────────────────────────────
              Low        Medium       High
                          Evidence
```

---

## Resource Requirements

### Estimated Engineering Time

| Quarter | Items | Effort | Resources |
|---------|-------|--------|-----------|
| Q2 (30 days) | P1 items | 12-18 hours | 1 engineer |
| Q2-Q3 (60 days) | P2 items | 36-52 hours | 1-2 engineers |
| Q3 (90 days) | P3 items | 36-54 hours | 1 engineer |

**Total:** ~84-124 hours over 90 days

### Team Capacity

Current team: 2 engineers
- Maintenance: 20% capacity
- New features: 80% capacity = ~240 hours/quarter
- Post-GA roadmap: ~100 hours (42% of capacity)
- **Conclusion:** Capacity available

---

## Risk Assessment

### High-Risk Items

| Item | Risk | Mitigation |
|------|------|------------|
| Auto-scaling | Complexity | Start simple; manual approval |
| Text highlighting | Accuracy | Tokenization edge cases |

### Low-Risk Items

| Item | Why Low Risk |
|------|--------------|
| Ingestion progress | Well-understood; additive |
| Bulk upload | Frontend only; no backend changes |
| Per-user metrics | Requires RBAC; can defer |

---

## Success Criteria

### Ingestion Progress Indicator

- [ ] Users can see % complete
- [ ] Users can see estimated time remaining
- [ ] Support tickets for "is my document done?" decrease by 80%

### Auto-Scaling

- [ ] Workers scale automatically based on queue depth
- [ ] No manual scaling required for 2 weeks
- [ ] Cost remains within 110% of manual baseline

### Text Highlighting

- [ ] Cited text highlighted in source document
- [ ] User satisfaction with evidence increases
- [ ] No regression in citation accuracy

---

## Alternative Prioritization

### If Resources Constrained (50% capacity)

**Focus on:**
1. Ingestion progress indicator (highest user impact)
2. Basic auto-scaling (highest operational impact)
3. Defer P2/P3 items

### If More Resources Available (150% capacity)

**Add:**
1. Collection sharing (collaboration)
2. Advanced RBAC (security)
3. Performance optimizations (if needed)

---

## Recommendation

### Recommended Sequence

**Month 1:**
- Week 1-2: Ingestion progress indicator
- Week 3-4: Auto-scaling (basic)

**Month 2:**
- Week 5-6: Text highlighting
- Week 7-8: Per-user metrics (requires RBAC foundation)

**Month 3:**
- Week 9-10: Bulk upload UI
- Week 11-12: Collection sharing
- Week 13: Buffer / polish

### Rationale

1. **Address #1 user complaint first** (ingestion progress)
2. **Reduce operational toil second** (auto-scaling)
3. **Improve trust third** (text highlighting)
4. **Enable visibility fourth** (per-user metrics)
5. **Add productivity features last** (bulk upload, sharing)

---

## Sign-Off

| Role | Name | Date | Approval |
|------|------|------|----------|
| Product Owner | [Product Owner] | 2026-04-16 | ✅ |
| Engineering Lead | [Engineering Lead] | 2026-04-16 | ✅ |
| Operations | [Ops Lead] | 2026-04-16 | ✅ |
| Stakeholders | [Leadership] | 2026-04-16 | ✅ |

**Next Roadmap Review:** 2026-05-16 (30 days)  
**Update Triggers:** Major user feedback, capacity issues, or incident learnings

---

**Roadmap Prepared:** 2026-04-16  
**Based On:** Beta feedback + Production evidence  
**Confidence Level:** High (evidence-based)
