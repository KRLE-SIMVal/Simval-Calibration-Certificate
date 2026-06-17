# P36 Implementation Log - TLS/Host Evidence

## Scope

Implemented TLS/host evidence generation and readiness content gating for the
`tls_host` go-live evidence key.

## Changes

- Added `app.backend.validation.tls_host` to validate a controlled source
  evidence JSON for the production HTTPS endpoint and host-boundary checks.
- Added `scripts/validation/generate_tls_host_evidence.py` to produce a
  sanitized JSON evidence file with `status`, blockers, HTTPS endpoint
  verification, approved hostname verification, TLS certificate validity,
  direct API exposure review, direct unauthenticated API exposure block status,
  reviewer approval, and source-file metadata.
- Extended the production readiness report content gate so `tls_host` evidence
  must be valid JSON with `status == "passed"` when referenced.
- Updated the production runtime guide and go-live evidence pack to include the
  TLS/host evidence command and readiness evidence reference.

## Validation

- Added unit tests for complete evidence, unverified HTTPS endpoint, unverified
  hostname, invalid TLS certificate, missing direct API exposure review,
  unblocked unauthenticated direct API exposure, missing reviewer approval,
  invalid JSON, naive timestamp, and CLI return-code behavior.
- Added readiness-report tests for failed `tls_host` evidence.
- Added documentation tests for the new command and implementation log.

## Domain Impact

No calculation, uncertainty, CMC, rounding, interpolation, or calibration
acceptance logic changed. This increment only adds auditable host-boundary
go-live evidence.

## Remaining Risk

The tool validates a controlled evidence record; it does not perform live TLS
scanning or network exposure testing. The HTTPS endpoint, approved host name,
certificate, and direct API exposure evidence must be collected on the approved
production boundary and reviewed before routine production use.
