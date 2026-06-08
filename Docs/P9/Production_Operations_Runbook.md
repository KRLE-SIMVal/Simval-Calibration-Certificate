# P9 Production Operations Runbook

Status: draft operational baseline.

This runbook covers local production-hardening controls that can be executed
without changing certificate, calculation, or workflow logic.

## SQLite Backup

Create a backup:

```powershell
python scripts\maintenance\create_sqlite_backup.py `
  --database-path C:\SIMVal\data\simval.sqlite3 `
  --backup-dir C:\SIMVal\backups `
  --evidence-output C:\SIMVal\evidence\backup-evidence.json
```

Expected evidence:

- Source database path.
- Backup database path.
- Timezone-aware creation timestamp.
- SHA-256 checksum.
- Database size in bytes.
- SQLite `PRAGMA integrity_check` result.

The integrity check must be `ok`. Any other result is a failed backup and must
be handled as a deviation before relying on that file.

## Restore Verification Drill

Restore a backup to a separate verification path:

```powershell
python scripts\maintenance\restore_sqlite_backup.py `
  --backup-path C:\SIMVal\backups\simval-sqlite-backup-YYYYMMDDTHHMMSSZ.sqlite3 `
  --restore-path C:\SIMVal\restore-drills\simval-restored.sqlite3 `
  --evidence-output C:\SIMVal\evidence\restore-evidence.json
```

The restore command refuses to overwrite an existing target database. This is
intentional. A production recovery that replaces the live database must be
handled as a controlled SOP action with human approval, pre-restore backup,
application shutdown, restore, post-restore integrity verification, and restart.

## Stale Pending Artifact Cleanup

Clean up old staged certificate artifact files:

```powershell
python scripts\maintenance\cleanup_stale_pending_artifacts.py `
  --artifact-dir C:\SIMVal\artifacts `
  --older-than-minutes 1440 `
  --output C:\SIMVal\evidence\pending-artifact-cleanup.json
```

The cleanup command only removes files matching `.*.pending` under the configured
artifact directory. Released certificate artifacts are not removed by this tool.

## Runtime Checks

The API exposes two runtime checks:

- `GET /health`: process liveness only. Expected result: HTTP 200 with
  `{"status":"ok"}`.
- `GET /readiness`: dependency readiness. Expected production result: HTTP 200
  with database and artifact storage components set to `ok`.

`GET /readiness` returns HTTP 503 when the database cannot be queried, artifact
storage is not configured, the artifact directory does not exist, or the
write/delete probe fails. The response deliberately does not include local
filesystem paths.

## Retention Baseline

Minimum production decisions still required before routine use:

- Backup frequency.
- Backup retention period.
- Off-machine or protected backup storage location.
- Quarterly restore drill schedule and evidence retention.
- Incident/deviation handling when backup, restore, or cleanup evidence fails.
- Host-level monitoring, disk-space thresholds, TLS/SSO checks, and backup
  freshness checks.

## Compliance Assumptions

- Backup files may contain customer and calibration records and must be protected
  with the same access controls as the production database.
- Backup evidence should be retained with validation and operations evidence.
- Restore over the live database is never automatic and always requires human
  approval.
