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

## Scope Not Implemented

- Cleanup is not yet scheduled automatically in deployment.
- Backup, restore, retention, monitoring, and production authentication provider
  decisions remain pending.
- PDF/A and digital-signature policy remains pending.

## Compliance Notes

- This slice does not change calculation logic, certificate rendering logic,
  release logic, or reported values.
- Cleanup does not touch finalized artifact filenames. It only removes stale
  staging files that are not certificate records.
- Cleanup uses explicit JSON evidence so a production maintenance run can be
  retained with validation/operations records.

## Verification

- Focused artifact storage and maintenance cleanup suite:
  9 passed on Python 3.12.10.
- Default regression suite after P9 pending-artifact cleanup:
  363 passed, 2 skipped on Python 3.12.10.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| Cleanup is manual unless invoked by an operator or scheduler. | Add a deployment-specific scheduled task once the hosting model and artifact storage path are fixed. |
| Cleanup uses local filesystem modification times. | Keep artifact storage on a controlled filesystem with reliable timestamps, or adapt the cleanup boundary when storage moves to managed object storage. |
| No backup/restore validation exists yet. | Add backup/restore smoke tests and documented recovery evidence before production release. |
