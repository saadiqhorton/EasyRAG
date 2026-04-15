# Backup and Disaster Recovery

## Overview

This document describes backup procedures, verification, and disaster recovery operations for the RAG Knowledge Base Framework.

## Backup Strategy

### What Gets Backed Up

| Component | Priority | Frequency | Retention |
|-----------|----------|-----------|-----------|
| PostgreSQL database | Critical | Daily (or hourly) | 7 days |
| Qdrant vector index | Critical | Daily | 7 days |
| Document storage | High | Daily | 7 days |
| Configuration files | Medium | On change | 30 days |
| Model cache | Low | Weekly | 14 days |

### Backup Types

1. **Full Backup** - All components (database, vectors, storage)
2. **Incremental Backup** - Only changed documents (not yet implemented)
3. **Configuration Backup** - Environment files and systemd services

## Automated Backups

### Setting Up Daily Backups

```bash
# Copy backup script to system location
sudo cp deploy/backup-scripts/backup.sh /usr/local/bin/ragkb-backup
sudo chmod +x /usr/local/bin/ragkb-backup

# Create cron job for daily backups at 2 AM
sudo tee /etc/cron.d/ragkb-backup << 'EOF'
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
0 2 * * * root /usr/local/bin/ragkb-backup >> /var/log/ragkb/backup.log 2>&1
EOF

# Or use systemd timer (preferred for systems with systemd)
sudo tee /etc/systemd/system/ragkb-backup.service << 'EOF'
[Unit]
Description=RAG KB Backup

[Service]
Type=oneshot
ExecStart=/usr/local/bin/ragkb-backup
User=root
StandardOutput=append:/var/log/ragkb/backup.log
StandardError=append:/var/log/ragkb/backup.log
EOF

sudo tee /etc/systemd/system/ragkb-backup.timer << 'EOF'
[Unit]
Description=Run RAG KB backup daily

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ragkb-backup.timer
sudo systemctl start ragkb-backup.timer
```

### Backup Environment Variables

Create `/etc/default/ragkb-backup`:

```bash
# Backup configuration
BACKUP_ROOT=/var/backups/ragkb
RETENTION_DAYS=7

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=ragkb
POSTGRES_DB=ragkb

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=rag_kb_chunks

# Storage
STORAGE_PATH=/var/lib/ragkb/storage
```

## Manual Backup

### Full Backup

```bash
# Run full backup
sudo /usr/local/bin/ragkb-backup

# Or with custom location
BACKUP_ROOT=/mnt/backups/ragkb sudo -E /usr/local/bin/ragkb-backup
```

### Component-Specific Backup

```bash
# PostgreSQL only
pg_dump -U ragkb ragkb | gzip > postgres_manual.sql.gz

# Qdrant only (via API)
curl -X POST http://localhost:6333/collections/rag_kb_chunks/snapshots

# Storage only
tar czf storage_manual.tar.gz -C /var/lib/ragkb/storage .
```

## Backup Verification

### Verify a Backup

```bash
# Check backup integrity
./deploy/backup-scripts/verify-backup.sh /var/backups/ragkb/20240115_120000

# Verbose mode
./deploy/backup-scripts/verify-backup.sh -v /var/backups/ragkb/20240115_120000
```

### What Verification Checks

1. **Manifest** - JSON file exists and is valid
2. **PostgreSQL** - gzip file is valid, not empty
3. **Qdrant** - snapshot file exists, reasonable size
4. **Storage** - gzip file is valid
5. **Logs** - Backup completed successfully

### Automated Verification

Add to backup script or run separately:

```bash
# Verify latest backup
LATEST_BACKUP=$(ls -td /var/backups/ragkb/*/ | head -1)
./deploy/backup-scripts/verify-backup.sh "$LATEST_BACKUP" || alert_ops_team
```

## Restore Procedures

### Full System Restore

Use when migrating to new hardware or recovering from total failure.

```bash
# 1. Install RAG KB on new system
./deploy/production-setup.sh

# 2. Restore from backup
sudo ./deploy/backup-scripts/restore.sh /var/backups/ragkb/20240115_120000

# 3. Start services
sudo systemctl start qdrant ragkb-api ragkb-worker

# 4. Verify
./deploy/scripts/health_check.sh
```

### Database-Only Restore

Use when database is corrupted but vectors and storage are intact.

```bash
# Restore just PostgreSQL
sudo ./deploy/backup-scripts/restore.sh --component postgres /var/backups/ragkb/20240115_120000

# Reindex documents (vectors may be out of sync)
curl -X POST http://localhost:8000/api/v1/admin/reindex \
  -H "Authorization: Bearer $API_KEY"
```

### Point-in-Time Recovery

For PostgreSQL with WAL archiving (advanced):

```bash
# Stop services
sudo systemctl stop ragkb-api ragkb-worker

# Restore to specific point in time
pg_restore --target-time "2024-01-15 14:30:00" ...

# Restart services
sudo systemctl start ragkb-api ragkb-worker
```

## Disaster Recovery Scenarios

### Scenario 1: Database Corruption

**Symptoms:** PostgreSQL won't start, data errors in logs

**Recovery:**
1. Stop all services: `sudo systemctl stop ragkb-api ragkb-worker`
2. Restore PostgreSQL: `sudo ./deploy/backup-scripts/restore.sh --component postgres <backup>`
3. Start services: `sudo systemctl start ragkb-api ragkb-worker`
4. Verify: Check `/health/detailed` endpoint

**Time to recover:** 10-30 minutes depending on database size

### Scenario 2: Vector Index Corruption

**Symptoms:** Searches return errors, Qdrant won't start

**Recovery:**
1. Stop API and workers
2. Option A - Restore from snapshot:
   ```bash
   sudo ./deploy/backup-scripts/restore.sh --component qdrant <backup>
   ```
3. Option B - Rebuild index:
   ```bash
   # Reindex all collections
   curl -X POST http://localhost:8000/api/v1/admin/reindex-all \
     -H "Authorization: Bearer $API_KEY"
   ```
4. Restart services

**Time to recover:** 5 minutes (restore) to hours (rebuild)

### Scenario 3: Document Storage Loss

**Symptoms:** API returns 404 for documents, "file not found" errors

**Recovery:**
1. Restore storage: `sudo ./deploy/backup-scripts/restore.sh --component storage <backup>`
2. Verify file permissions: `sudo chown -R ragkb:ragkb /var/lib/ragkb/storage`
3. Verify document access via API

**Time to recover:** Depends on storage size (typically 10-60 minutes)

### Scenario 4: Complete System Failure

**Symptoms:** Server won't boot, hardware failure

**Recovery:**
1. Provision new server
2. Run production setup: `./deploy/production-setup.sh`
3. Copy backup to new server (or mount backup volume)
4. Full restore: `sudo ./deploy/backup-scripts/restore.sh <backup>`
5. Update DNS or load balancer to point to new server
6. Verify all components

**Time to recover:** 1-4 hours depending on backup size and infrastructure

### Scenario 5: Accidental Data Deletion

**Symptoms:** Documents missing, collection deleted

**Recovery:**
1. Identify approximate time of deletion
2. Find backup from before deletion: `ls -lt /var/backups/ragkb/`
3. Restore specific component or full backup
4. If selective restore needed, consider:
   - Database: Restore to temp DB, extract specific records
   - Storage: Manually extract specific files from backup

**Time to recover:** 15-60 minutes

## Backup Monitoring

### Key Metrics

| Metric | Warning Threshold | Critical Threshold |
|--------|-------------------|-------------------|
| Backup age | > 25 hours | > 49 hours |
| Backup size change | -50% or +200% | -80% or +500% |
| Backup duration | > 2x normal | > 4x normal |
| Verification failures | Any | Multiple consecutive |

### Monitoring Commands

```bash
# Check last backup age
find /var/backups/ragkb -mindepth 1 -maxdepth 1 -type d -mtime +1

# Check backup sizes
du -sh /var/backups/ragkb/*/

# Check backup success in logs
grep "BACKUP COMPLETED" /var/log/ragkb/backup.log | tail -5
```

### Alerting Script

```bash
#!/bin/bash
# /usr/local/bin/check-backup-health.sh

BACKUP_DIR="/var/backups/ragkb"
ALERT_EMAIL="ops@example.com"

# Find latest backup
LATEST=$(ls -td "$BACKUP_DIR"/*/ 2>/dev/null | head -1)

if [ -z "$LATEST" ]; then
    echo "CRITICAL: No backups found" | mail -s "RAG KB Backup Alert" "$ALERT_EMAIL"
    exit 1
fi

# Check age (seconds since last backup)
AGE=$(($(date +%s) - $(stat -c %Y "$LATEST")))
MAX_AGE=$((25 * 3600))  # 25 hours

if [ $AGE -gt $MAX_AGE ]; then
    echo "WARNING: Last backup is $(($AGE / 3600)) hours old" | \
        mail -s "RAG KB Backup Alert" "$ALERT_EMAIL"
    exit 1
fi

# Verify backup
if ! ./deploy/backup-scripts/verify-backup.sh "$LATEST" > /dev/null 2>&1; then
    echo "CRITICAL: Latest backup failed verification" | \
        mail -s "RAG KB Backup Alert" "$ALERT_EMAIL"
    exit 1
fi

echo "Backup health check passed"
exit 0
```

## Cross-Region/Offsite Backups

### S3 Backup (AWS)

```bash
# After local backup, sync to S3
aws s3 sync /var/backups/ragkb/ s3://mycompany-backups/ragkb/ \
    --delete \
    --storage-class STANDARD_IA

# Or use rclone for other providers
rclone sync /var/backups/ragkb/ remote:backups/ragkb/
```

### Requirements for Offsite

1. **Encryption** - Encrypt backups before transfer
2. **Bandwidth** - Ensure backup window fits within available time
3. **Retention** - Match or exceed local retention policy
4. **Testing** - Periodically restore from offsite backup

## Recovery Time Objectives

| Scenario | RTO (Recovery Time Objective) | RPO (Recovery Point Objective) |
|----------|------------------------------|-------------------------------|
| Database corruption | 30 min | Last backup (up to 24h) |
| Vector index loss | 5 min (restore) or 4h (rebuild) | Last backup or current |
| Storage loss | 1-4 hours | Last backup |
| Complete failure | 2-4 hours | Last backup |
| Accidental deletion | 30 min | Last backup |

## Security Considerations

### Backup Encryption

```bash
# Encrypt backup with GPG
gpg --encrypt --recipient ops@example.com \
    --output backup.tar.gz.gpg backup.tar.gz

# Decrypt for restore
gpg --decrypt --output backup.tar.gz backup.tar.gz.gpg
```

### Backup Permissions

```bash
# Secure backup directory
sudo chown root:root /var/backups/ragkb
sudo chmod 700 /var/backups/ragkb

# Each backup owned by root
sudo chown -R root:root /var/backups/ragkb/*/
sudo chmod -R 600 /var/backups/ragkb/*/
```

### Credential Handling

- Never store database passwords in backup scripts
- Use environment files with restricted permissions
- Rotate backup encryption keys regularly
- Use IAM roles for S3 access (avoid access keys in scripts)

## Testing Recovery Procedures

### Quarterly DR Drill

1. **Schedule** - Quarterly, during maintenance window
2. **Scope** - Full system restore to test environment
3. **Process:**
   ```bash
   # 1. Provision test instance
   # 2. Run production-setup.sh
   # 3. Restore from latest backup
   # 4. Run full test suite
   # 5. Verify data integrity
   # 6. Document issues and timing
   ```
4. **Success Criteria:**
   - All services start successfully
   - Health checks pass
   - Sample searches return expected results
   - Documents can be downloaded
   - Ingestion pipeline works

### Backup Spot Checks

Monthly:
- Verify backup exists and is recent
- Run verify-backup.sh
- Check backup size is reasonable
- Review backup logs for errors

## Quick Reference

```bash
# Manual backup
sudo /usr/local/bin/ragkb-backup

# List backups
ls -lt /var/backups/ragkb/

# Verify backup
./deploy/backup-scripts/verify-backup.sh /var/backups/ragkb/YYYYMMDD_HHMMSS

# Full restore
sudo ./deploy/backup-scripts/restore.sh /var/backups/ragkb/YYYYMMDD_HHMMSS

# Component restore
sudo ./deploy/backup-scripts/restore.sh --component postgres /var/backups/ragkb/YYYYMMDD_HHMMSS

# Dry run
sudo ./deploy/backup-scripts/restore.sh --dry-run /var/backups/ragkb/YYYYMMDD_HHMMSS

# Check backup status
sudo systemctl status ragkb-backup.timer
sudo journalctl -u ragkb-backup.service
```
