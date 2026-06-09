# P16 Implementation Log

Status: implemented for Microsoft Entra ID Free authentication boundary.

P16 adds a controlled Entra token-exchange path while preserving the existing
local SIMVal roles, permissions, audit trail, and session-based regulated API
actions.

## Scope Implemented

- Added Entra runtime configuration for tenant id, client id, token audience,
  and local session duration.
- Added a lazy PyJWT/JWKS verifier for Entra ID v2.0 bearer tokens.
- Added `POST /auth/entra/session` to exchange a verified Entra token for a
  short local SIMVal session.
- Local sessions are issued only when the Entra account email matches exactly
  one existing active local SIMVal user account.
- Entra token claims do not grant SIMVal roles. Roles remain controlled through
  local user-management records and audit evidence.
- Entra-backed session issuance records a `user_session_created` audit event.

## Compliance Notes

- No calculation, uncertainty, CMC, rounding, certificate rendering, or
  certificate-release logic was changed.
- Production use still requires live tenant/app registration verification,
  TLS/host evidence, backup/restore evidence, reviewer independence, and final
  human QA/laboratory approval.
- Tenant id, client id, and audience are identifiers, not secrets, but the real
  production values must still be controlled in the host configuration.

## Verification

- Focused Entra token, Entra session, API settings, and API application suite:
  65 passed on Python 3.12.10.
- Focused Entra/API/documentation suite after documentation updates:
  70 passed on Python 3.12.10.
- Full repository regression suite: 456 passed, 2 skipped on Python 3.12.10.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| Live SIMVal Entra tenant/app registration has not been verified in this workspace. | Perform a go-live authentication test with the approved app registration, verify `POST /auth/entra/session`, then verify `GET /me` using the returned local session id. |
| Local SIMVal users are matched by email. | Include email matching in access review; if Entra UPN/email changes, update/deactivate the local SIMVal user before routine use. |
| Reviewer independence is still a production blocker. | Implement same-user release/review blocking or document an approved deviation before go-live. |
