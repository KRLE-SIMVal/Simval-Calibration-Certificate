# P30 Implementation Log

Status: implemented for backup/restore validation evidence generation.

P30 adds a controlled evidence generator for the pilot `backup_restore`
evidence key. The generator reads backup and restore JSON evidence, verifies
integrity/checksum consistency, records hashes of the source evidence files, and
blocks until reviewer approval is explicit.

## Scope Implemented

- Added `app.backend.validation.backup_restore`.
- Added `scripts/validation/generate_backup_restore_validation_evidence.py`.
- The evidence confirms backup integrity, restored database integrity, matching
  backup/restored checksums, source evidence file hashes, and reviewer approval
  status.
- The CLI returns exit code `0` only when integrity checks pass, checksums match,
  and reviewer approval is supplied.
- The CLI returns exit code `2` while blockers remain.
- Updated production runtime and go-live evidence-pack documentation.

## Compliance Notes

- This does not replace the backup or restore drill commands; it wraps their
  retained JSON evidence into a package-ready validation record.
- Backup files and raw operation evidence may contain controlled data and must
  be retained under production access controls.
- No calculation, uncertainty, CMC, rounding, certificate rendering, release,
  audit immutability, reviewer-independence enforcement, parser, authentication,
  or token-validation logic was changed.

## Verification

- Unit tests cover passed evidence, missing reviewer approval, checksum
  mismatch, invalid JSON, timezone-aware timestamps, CLI output, exit code `0`,
  and exit code `2`.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| The generator validates retained evidence content, not backup storage architecture or retention policy. | Approve backup frequency, retention period, protected storage, and restore-drill schedule before go-live. |
| Source backup/restore evidence may contain local paths or operational details. | Retain raw operation evidence in controlled operations storage; use the sanitized validation record in the pilot package. |
