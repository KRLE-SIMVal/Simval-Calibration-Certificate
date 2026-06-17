# P35 Implementation Log - Live Entra Evidence

## Scope

Implemented live Entra evidence generation and readiness content gating for the
`live_entra` go-live evidence key.

## Changes

- Added `app.backend.validation.live_entra` to validate a controlled source
  evidence JSON for Microsoft Entra ID Free production authentication checks.
- Added `scripts/validation/generate_live_entra_evidence.py` to produce a
  sanitized JSON evidence file with `status`, blockers, provider, tenant/client
  verification flags, audience verification, session exchange result, `GET /me`
  result, retained `user_session_created` audit-event status, local role-mapping
  review status, reviewer approval, and source-file metadata.
- Extended the production readiness report content gate so `live_entra`
  evidence must be valid JSON with `status == "passed"` when referenced.
- Updated the production runtime guide and go-live evidence pack to include the
  live Entra evidence command and readiness evidence reference.

## Validation

- Added unit tests for complete evidence, wrong provider, unverified tenant,
  failed session checks, missing audit/role-mapping review evidence, missing
  reviewer approval, invalid JSON, naive timestamp, and CLI return-code
  behavior.
- Added readiness-report tests for failed `live_entra` evidence.
- Added documentation tests for the new command and implementation log.

## Domain Impact

No calculation, uncertainty, CMC, rounding, interpolation, or calibration
acceptance logic changed. This increment only adds auditable authentication
go-live evidence.

## Remaining Risk

The tool validates a controlled evidence record; it does not contact Microsoft
Entra or prove the tenant live by itself. The live tenant/app registration,
token exchange, `GET /me`, and audit-event evidence must be collected on the
approved production host and reviewed before routine production use.
