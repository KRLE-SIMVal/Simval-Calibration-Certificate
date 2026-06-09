# P14 Implementation Log

Status: started for released artifact retrieval.

P14 adds a controlled download path for released certificate artifacts. The goal
is to make certificate history operationally useful without trusting stored URI
strings alone.

## Scope Implemented

- Added checksum-verified stored artifact resolution in
  `app/backend/certificates/storage.py`.
- Added certificate lookup by export artifact id in SQLite persistence.
- Added session-backed released artifact retrieval service with
  `view_released_certificate` authorization.
- Added `GET /certificate-artifacts/{artifact_id}` to serve verified PDF/XLSX
  bytes from the configured artifact storage path.
- Added browser workflow contract entry for released artifact download.
- Added storage, service, and API regression tests for verified artifact
  retrieval.

## Compliance Notes

- Download is permission-gated using the existing released-certificate viewing
  permission.
- The service rejects filenames with path components and storage URIs that do
  not match the controlled local storage convention.
- The file SHA-256 checksum is recalculated before download and must match the
  released export-artifact evidence.

## Verification

- Focused certificate artifact storage, rendered-release, and API suite:
  59 passed on Python 3.12.10.
- Default regression suite after released artifact retrieval:
  434 passed, 2 skipped on Python 3.12.10.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| Artifact authorization is still role-based, not customer/project scoped. | Add customer/project access scopes before any customer portal or broader multi-client deployment. |
| Browser workflow can call the endpoint, but the UI is still a technical workflow shell. | Build a proper certificate history/download screen before production usability validation. |
