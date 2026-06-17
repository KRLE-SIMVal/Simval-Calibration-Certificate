# P28 Implementation Log

Status: implemented for runtime-profile pilot evidence generation.

P28 adds a sanitized runtime-profile evidence generator for the controlled
validation pilot. The generated JSON is intended to satisfy the pilot
`runtime_profile` evidence key before creating the pilot validation package.

## Scope Implemented

- Added `app.backend.validation.runtime_profile`.
- Added `scripts/validation/generate_runtime_profile_evidence.py`.
- The evidence records production profile, authentication provider,
  temperature-only scope, configured-path booleans, Entra configuration status,
  local session duration, and blockers.
- The evidence intentionally does not write filesystem paths, tenant ids,
  client ids, audiences, JWKS URLs, tokens, or secrets.
- The CLI returns exit code `0` when evidence passes and `2` when blockers
  remain.

## Compliance Notes

- This supports the pilot IQ activity for controlled host and runtime
  configuration.
- It does not prove live Entra token exchange, TLS, host ownership, or user
  lifecycle controls; those remain separate evidence items.
- No calculation, uncertainty, CMC, rounding, certificate rendering, release,
  audit immutability, reviewer-independence enforcement, parser, authentication,
  or token-validation logic was changed.

## Verification

- Unit tests cover passed production evidence, blocked development evidence,
  timezone-aware timestamps, CLI output, exit codes, and sensitive value
  omission.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| Runtime-profile evidence confirms configuration values only, not the real host boundary. | Retain separate TLS/host verification and live Entra token-exchange evidence before go-live. |
| The output intentionally omits local paths and Entra identifiers, so reviewers must compare it with controlled host configuration records where necessary. | Keep detailed host configuration evidence in controlled operations records, not in source-controlled JSON. |
