# P9 Implementation Log

Status: started.

P9 begins production hardening after the P8 validation package generator.

## Scope Implemented

- Added controlled cleanup for stale staged certificate artifact files.
- Cleanup removes only files matching the local staged-artifact pattern
  `.*.pending` and only when the file modification time is older than a
  timezone-aware cutoff.
- Cleanup leaves final certificate artifacts and recent pending files untouched.
- Added a maintenance CLI:
  `scripts/maintenance/cleanup_stale_pending_artifacts.py`.
- The CLI writes JSON evidence with artifact directory, cutoff, removed count,
  and removed file paths.
- Added controlled SQLite backup and restore helpers in
  `app/backend/operations/backup.py`.
- Added a maintenance CLI:
  `scripts/maintenance/create_sqlite_backup.py`.
- Added a restore verification CLI:
  `scripts/maintenance/restore_sqlite_backup.py`.
- Backup and restore operations write JSON evidence with absolute paths,
  timezone-aware timestamps, SHA-256 checksums, byte counts, and SQLite
  `PRAGMA integrity_check` results.
- Restore is intentionally limited to a new target database path. It does not
  overwrite an existing production database.
- Added API runtime readiness checks at `GET /readiness`.
- `GET /health` remains a simple liveness endpoint. `GET /readiness` checks
  SQLite access and configured artifact-storage write/delete capability.
- Readiness responses do not expose local database or artifact filesystem paths.

## Scope Not Implemented

- Cleanup is not yet scheduled automatically in deployment.
- Retention, monitoring, and production authentication provider decisions remain
  pending.
- PDF/A and digital-signature policy remains pending.

## Compliance Notes

- This slice does not change calculation logic, certificate rendering logic,
  release logic, or reported values.
- Cleanup does not touch finalized artifact filenames. It only removes stale
  staging files that are not certificate records.
- Cleanup uses explicit JSON evidence so a production maintenance run can be
  retained with validation/operations records.
- Backup and restore helpers are operational controls only. They do not modify
  audit trail, certificate release records, calculation summaries, constants, or
  reported values.
- Restore evidence is designed for recovery drills and human-approved recovery.
  Restoring over a live production database remains a controlled SOP action, not
  an automatic application behavior.
- Runtime readiness checks are deployment controls only. They do not authenticate
  a user, perform regulated workflow actions, or write audit events.

## Verification

- Focused artifact storage and maintenance cleanup suite:
  9 passed on Python 3.12.10.
- Default regression suite after P9 pending-artifact cleanup:
  363 passed, 2 skipped on Python 3.12.10.
- Focused SQLite backup/restore suite:
  9 passed on Python 3.12.10.
- Focused API readiness and operations suite:
  34 passed on Python 3.12.10.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| Cleanup is manual unless invoked by an operator or scheduler. | Add a deployment-specific scheduled task once the hosting model and artifact storage path are fixed. |
| Cleanup uses local filesystem modification times. | Keep artifact storage on a controlled filesystem with reliable timestamps, or adapt the cleanup boundary when storage moves to managed object storage. |
| Backup/restore is implemented but not scheduled or retention-managed. | Add scheduled backups, periodic restore drills, off-machine protected storage, and retention rules in the production deployment SOP. |
| Restore deliberately refuses to overwrite an existing database. | Keep production recovery as a human-approved shutdown/replace/start procedure with pre-restore backup and post-restore verification. |
| Readiness checks validate only local SQLite and artifact storage dependencies. | Add host-level monitoring, disk-space thresholds, TLS/SSO checks, and backup freshness checks in the deployment platform. |
