# RAG Knowledge Base - Production Rollout Checklist

Pre-deploy, deploy, and post-deploy procedures for production deployment.

---

## Overview

This checklist ensures safe, repeatable deployments of the RAG Knowledge Base Framework.

**Estimated Time:** 30-60 minutes  
**Rollback Time:** 5-15 minutes  
**Downtime:** Minimal (rolling restart)

---

## Pre-Deploy Checklist

### 1. Environment Preparation

- [ ] **Backup current data**
  ```bash
  # PostgreSQL backup
  docker compose exec postgres pg_dump -U ragkb ragkb > backup_$(date +%Y%m%d_%H%M%S).sql
  
  # Qdrant snapshot
  curl -X POST http://localhost:6333/collections/rag_kb_chunks/snapshots
  
  # Storage backup
  tar czf storage_backup_$(date +%Y%m%d).tar.gz /var/lib/ragkb/storage
  ```

- [ ] **Verify backup integrity**
  ```bash
  ls -lh backup_*.sql
  tar -tzf storage_backup_*.tar.gz | head -5
  ```

- [ ] **Review changelog**
  - Read CHANGELOG.md for version changes
  - Note any breaking changes or migrations
  - Check for new required environment variables

### 2. Configuration Review

- [ ] **Environment file prepared**
  ```bash
  cp deploy/config/.env.production .env
  # Edit with production values
  nano .env
  ```

- [ ] **Required variables set**
  - [ ] `POSTGRES_USER`
  - [ ] `POSTGRES_PASSWORD` (strong, random)
  - [ ] `POSTGRES_DB`
  - [ ] `POSTGRES_URL`
  - [ ] `QDRANT_URL`
  - [ ] `ANSWER_LLM_BASE_URL`
  - [ ] `ANSWER_LLM_MODEL`
  - [ ] `ANSWER_LLM_API_KEY` (if using OpenAI)

- [ ] **Optional variables reviewed**
  - [ ] `EMBEDDING_MODEL_NAME`
  - [ ] `RERANKER_MODEL_NAME`
  - [ ] `MAX_UPLOAD_SIZE_MB`
  - [ ] `LOG_LEVEL` (set to WARNING for production)
  - [ ] `CORS_ORIGINS`

- [ ] **Secrets secured**
  - [ ] API keys not committed to git
  - [ ] Passwords generated with sufficient entropy (32+ chars)
  - [ ] `.env` file permissions set (600)

### 3. Resource Verification

- [ ] **System requirements met**
  - [ ] CPU: 2+ cores (4+ recommended)
  - [ ] RAM: 4GB+ (8GB recommended)
  - [ ] Disk: 50GB+ free (SSD recommended)
  - [ ] Network: Ports 8000, 5432, 6333 available

- [ ] **Disk space check**
  ```bash
  df -h /var/lib
  ```

- [ ] **Memory check**
  ```bash
  free -h
  ```

- [ ] **Docker resources**
  ```bash
  docker system df
  ```

### 4. Dependency Verification

- [ ] **Docker and Docker Compose installed**
  ```bash
  docker --version  # 24.0+
  docker compose version  # v2.0+
  ```

- [ ] **Required images available**
  ```bash
  docker pull postgres:16-alpine
  docker pull qdrant/qdrant:v1.12.1
  ```

- [ ] **Network connectivity**
  - [ ] Can reach HuggingFace Hub (for model download)
  - [ ] Can reach LLM endpoint (Ollama/OpenAI)
  - [ ] Internal network between services working

---

## Deploy Phase

### 1. Pre-Deployment

- [ ] **Notify stakeholders**
  - Inform users of maintenance window
  - Set expectations for brief downtime

- [ ] **Stop dependent services**
  ```bash
  # If running with systemd
  sudo systemctl stop ragkb-worker
  sudo systemctl stop ragkb-api
  ```

### 2. Database Migration (if needed)

- [ ] **Run Alembic migrations**
  ```bash
  # Via Docker
  docker compose run --rm api alembic upgrade head
  
  # Or via systemd
  cd /opt/ragkb && venv/bin/alembic upgrade head
  ```

- [ ] **Verify migration applied**
  ```bash
  docker compose exec postgres psql -U ragkb -c "SELECT version_num FROM alembic_version;"
  ```

### 3. Application Deployment

- [ ] **Pull latest code**
  ```bash
  git fetch origin
  git checkout <version-tag>
  # or
  git pull origin main
  ```

- [ ] **Build new images**
  ```bash
  docker compose -f deploy/docker-compose.yml build --no-cache
  ```

- [ ] **Deploy with zero downtime**
  ```bash
  # Rolling restart
  docker compose -f deploy/docker-compose.yml up -d
  ```

### 4. Startup Verification

- [ ] **Wait for services to start**
  ```bash
  sleep 30
  ```

- [ ] **Check container status**
  ```bash
  docker compose ps
  ```

- [ ] **Check health endpoints**
  ```bash
  ./deploy/scripts/health_check.sh --wait
  ```

---

## Post-Deploy Verification

### 1. Health Checks

- [ ] **All services healthy**
  ```bash
  ./deploy/scripts/health_check.sh
  ```

- [ ] **Database connectivity**
  ```bash
  curl http://localhost:8000/health/ready | grep '"postgres":true'
  ```

- [ ] **Qdrant connectivity**
  ```bash
  curl http://localhost:8000/health/ready | grep '"qdrant":true'
  ```

### 2. Smoke Tests

- [ ] **Run full smoke test**
  ```bash
  ./deploy/scripts/smoke_verify.sh
  ```

- [ ] **Verify all test steps pass**
  - [ ] API health check
  - [ ] Service readiness
  - [ ] Collection creation
  - [ ] Document upload
  - [ ] Ingestion completion
  - [ ] Search results
  - [ ] Ask endpoint

### 3. Functional Verification

- [ ] **Create test collection**
  ```bash
  curl -X POST http://localhost:8000/api/v1/collections \
    -H "Content-Type: application/json" \
    -d '{"name": "post-deploy-test", "description": "Verification"}'
  ```

- [ ] **Upload test document**
  ```bash
  curl -X POST http://localhost:8000/api/v1/collections/{id}/documents \
    -F "file=@test.md"
  ```

- [ ] **Verify search works**
  ```bash
  curl -X POST http://localhost:8000/api/v1/collections/{id}/search \
    -H "Content-Type: application/json" \
    -d '{"query": "test", "limit": 5}'
  ```

- [ ] **Clean up test data**
  ```bash
  curl -X DELETE http://localhost:8000/api/v1/documents/{document_id}
  curl -X DELETE http://localhost:8000/api/v1/collections/{collection_id}
  ```

### 4. Monitoring Setup

- [ ] **Verify logging**
  ```bash
  docker compose logs --tail 50 api
  ```

- [ ] **Check for errors**
  ```bash
  docker compose logs | grep -i error | head -20
  ```

- [ ] **Verify metrics exposure** (if applicable)
  ```bash
  curl http://localhost:8000/metrics  # if metrics endpoint exists
  ```

### 5. Final Verification

- [ ] **All containers running**
  ```bash
  docker compose ps
  ```

- [ ] **No critical errors in logs**

- [ ] **Smoke tests passed**

- [ ] **Performance acceptable**
  - API responds within 5s
  - Search returns within 10s

---

## Rollback Procedure

**Use this if deployment fails verification.**

### 1. Immediate Rollback

```bash
# Stop current services
docker compose down

# Restore previous version
git checkout <previous-tag>

# Restore database (if needed)
docker compose up -d postgres
docker compose exec -T postgres psql -U ragkb ragkb < backup_file.sql

# Start previous version
docker compose up -d
```

### 2. Database Rollback (if migration failed)

```bash
# Downgrade Alembic migration
docker compose run --rm api alembic downgrade -1

# Or specific version
docker compose run --rm api alembic downgrade <previous-revision>
```

### 3. Verification After Rollback

```bash
# Run health checks
./deploy/scripts/health_check.sh

# Run smoke tests
./deploy/scripts/smoke_verify.sh
```

### 4. Notify Stakeholders

- Inform users that rollback completed
- Document reason for rollback
- Plan for retry with fixes

---

## Post-Deployment Tasks

### 1. Documentation

- [ ] **Update deployment log**
  ```bash
  echo "$(date): Deployed version X.X.X" >> deployments.log
  ```

- [ ] **Record any issues encountered**

- [ ] **Update runbooks if needed**

### 2. Monitoring

- [ ] **Set up alerts** (if not already configured)
  - Disk usage > 85%
  - Memory usage > 90%
  - Failed job rate > 5%
  - API response time > 5s

- [ ] **Verify log aggregation**

### 3. Cleanup

- [ ] **Remove old images**
  ```bash
  docker image prune -a --filter "until=168h"
  ```

- [ ] **Archive old backups** (keep last 7 days)
  ```bash
  find /var/backups/ragkb -name "*.sql.gz" -mtime +7 -delete
  ```

---

## Sign-Off

**Deployment completed by:** _________________  
**Date:** _________________  
**Version deployed:** _________________  

**Verification completed by:** _________________  
**All checks passed:** [ ] Yes [ ] No

**Notes:**

---

## Emergency Contacts

| Role | Name | Contact |
|------|------|---------|
| Primary On-Call | | |
| Secondary On-Call | | |
| Database Admin | | |
| Infrastructure | | |

---

## Quick Reference

**Health Check:**
```bash
./deploy/scripts/health_check.sh
```

**Smoke Test:**
```bash
./deploy/scripts/smoke_verify.sh
```

**View Logs:**
```bash
docker compose logs -f api
docker compose logs -f worker
```

**Restart Services:**
```bash
docker compose restart
```

**Full Reset:**
```bash
docker compose down
docker compose up -d
```
