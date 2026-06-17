# P26 Implementation Log

Status: implemented for runtime-profile readiness gate.

P26 makes the runtime profile an explicit, typed runtime setting and prevents
production-readiness reports from becoming ready when they are generated from a
development profile.

## Scope Implemented

- Added a `RuntimeProfile` setting with supported values `development` and
  `production`.
- Rejected invalid `SIMVAL_RUNTIME_PROFILE` values instead of treating typos as
  development mode.
- Added `SIMVAL_RUNTIME_PROFILE=production` to `deployment/production.env.example`.
- Added `runtime_profile` to the production-readiness report scope.
- Added the `runtime_profile_not_production` readiness blocker.

## Compliance Notes

- This reduces the risk that go-live evidence is generated from a permissive
  development profile while appearing production-ready.
- Production authentication still requires `SIMVAL_AUTH_PROVIDER=entra_id_free`;
  local-session authentication remains rejected in production profile.
- No calculation, uncertainty, CMC, rounding, certificate rendering, release,
  audit immutability, reviewer-independence, parser, or token-validation logic
  was changed.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| The setting proves only the application profile, not that the host is the approved production host. | Retain TLS/host verification evidence and run the readiness report from the approved SIMVal-controlled host. |
| Operators can still run commands from an incorrect shell environment. | Use a controlled service configuration or deployment script and retain the generated readiness report with `runtime_profile` in the scope payload. |
