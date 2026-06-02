# P3 Implementation Log

Status: started.

P3 begins the production-control and API-readiness work after the P2 backend temperature workflow closeout.

## Scope Implemented

- User account identity domain model with user id, display name, email, role set, active status, optional signature label, and creation timestamp.
- User session domain model with issued, expiry, and optional revocation timestamps.
- Authenticated actor value object for service/API boundaries.
- SQLite persistence for user accounts.
- SQLite persistence for user sessions.
- SQLite schema marker updated to the first P3 schema version.
- Session revocation persistence.
- Authenticated actor resolution service that requires an active, unexpired, unrevoked session.
- Actor resolution rejects inactive users and users without permission for the requested regulated action.
- Actor resolution returns controlled user id, display name, and roles for downstream audit events.
- Session-backed temperature measurement-window selection wrapper.
- Session-backed temperature window-completion wrapper.
- Session-backed automatic temperature calculation-run wrapper.
- Session-backed wrappers resolve the authenticated actor before invoking the existing internal P2 service functions.
- Unauthorized session-backed service calls are rejected before window records, calculation summaries, audit events, or workflow transitions are written.
- Controlled SQLite migration runner foundation.
- Migration runner records version, description, SQL checksum, timezone-aware applied timestamp, and applied order.
- Migration runner is idempotent when an already-applied migration has the same checksum.
- Migration runner blocks checksum mismatches for already-applied versions.
- Migration runner rejects duplicate migration versions in one plan and does not record failed SQL as applied.
- Certificate preview permission added to the regulated action matrix.
- Immutable certificate preview models for rows generated from locked calculation summaries.
- Session-backed certificate preview service.
- Certificate preview service requires `calculated` or later workflow state.
- Certificate preview service rejects missing summaries and mixed calculation-engine, constant-set, or budget versions.
- Certificate preview generation records audit evidence with summary ids, row count, template version, actor, and version references.
- Optional API dependencies installed and `httpx` added to the test dependency extra for endpoint tests.
- FastAPI application factory with injected SQLite connection and clock.
- `GET /health` endpoint.
- `GET /me` endpoint resolving active session identity.
- `POST /certificate-previews` endpoint using the session-backed certificate preview service.
- API certificate preview endpoint returns controlled error responses for unauthorized sessions and invalid workflow state.
- CI default regression dependency installation includes both API and test extras.

## Scope Not Implemented

- No password, SSO, or external identity-provider integration yet.
- API coverage is limited to health, actor identity, and certificate preview endpoints.
- Existing P2 backend services still accept explicit `user_id` strings internally for trusted backend use; P3 API-facing wrappers now resolve sessions before calling them for window and calculation actions.
- No dedicated user-management audit workflow yet for creating, deactivating, or role-changing user accounts.
- Existing full SQLite schema initializer is not yet split into a historical migration chain.
- No PDF rendering, visual template matching, or export artifact generation yet.

## Compliance Notes

- This slice does not change calculation logic or reported metrology values.
- The service boundary prevents future API calls from using arbitrary free-form user ids as audit actors.
- User roles remain controlled through the existing permission matrix.
- Multiple assigned roles are supported at the user-account level; an active user is authorized when at least one assigned role permits the requested action.
- Sessions are time bounded and can be revoked.
- Inactive users cannot perform regulated actions even when a session record exists.
- Future API endpoints must call the session-backed wrappers for regulated window and calculation actions, not the internal `user_id` service functions directly.
- Future schema changes should be applied through the controlled migration runner so version and checksum evidence are retained.
- Certificate preview consumes locked summaries and does not recalculate certificate result rows.
- Certificate preview audit evidence can be used by later export/release gates to prove preview occurred before export.
- API endpoint tests use ASGI transport directly and avoid deprecated synchronous test-client behavior.
- Default regression CI must install `.[api,test]` because the default suite now includes API endpoint tests.

## Verification

- Focused user identity, SQLite user/session persistence, actor-resolution, and permission suite: 25 passed on Python 3.12.10.
- Focused session-backed measurement-window, window-completion, calculation-run, and authentication suite: 31 passed on Python 3.12.10.
- Focused controlled SQLite migration runner suite: 5 passed on Python 3.12.10.
- Focused certificate preview model, preview service, permission, and audit suite: 16 passed on Python 3.12.10.
- Focused API app, authentication, certificate preview service, and session-backed temperature service suite: 44 passed on Python 3.12.10.
- Default regression suite after API endpoint slice: 255 passed, 2 skipped on Python 3.12.10.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| No password, MFA, SSO, or Azure/M365 identity-provider integration exists yet. | Keep local session identity as the backend control boundary for P3 and select the production identity provider before deployment. |
| User creation and role changes are not yet audited workflows. | Add an admin user-management service that writes audit events for create, deactivate, role change, and session revocation. |
| Some trusted internal services still accept explicit `user_id` strings. | Keep them internal and require API endpoints to call session-backed wrappers for regulated actions. Add wrappers for remaining regulated actions as those API surfaces are implemented. |
| Existing full SQLite schema still uses direct initialization. | Keep direct initialization for test databases now, but split the production schema history into controlled migrations before persistent multi-environment testing or deployment. |
| Certificate preview is audited but not yet persisted as a separate preview record. | Use preview audit evidence for the next export gate, then add a dedicated preview table only if template review requires retaining rendered preview payloads. |
| API app currently uses an injected SQLite connection for tests. | Add production connection/session lifecycle management before running a persistent web server. |
