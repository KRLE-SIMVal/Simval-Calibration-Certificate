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
- Audited admin user-management service for user creation, role change, user deactivation, and session revocation.
- User-management audit events record previous/new regulated identity values and required reasons for role, deactivation, and revocation changes.
- Certificate release service requiring approved workflow state and matching preview audit evidence before release.
- Certificate release service persists immutable certificate/export artifact evidence and records export, release, and workflow audit events in one transaction.
- API runtime settings require `SIMVAL_DATABASE_PATH` for persistent SQLite deployments.
- API app factory supports either a fixed test connection or a production connection provider.
- Production SQLite API connection scope opens and closes one connection per request with foreign keys enabled.
- `POST /certificate-releases` endpoint exposes the session-backed release gate and returns certificate, artifact, and audit ids.

## Scope Not Implemented

- No password, SSO, or external identity-provider integration yet.
- API coverage is limited to health, actor identity, certificate preview, and certificate release endpoints.
- Existing P2 backend services still accept explicit `user_id` strings internally for trusted backend use; P3 API-facing wrappers now resolve sessions before calling them for window and calculation actions.
- User-management workflow is service-level only; no API endpoints for admin user management yet.
- Existing full SQLite schema initializer is not yet split into a historical migration chain.
- No PDF rendering, visual template matching, or export artifact generation yet.
- Release service records controlled export-artifact metadata but does not render the PDF/XLSX bytes.

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
- User creation, role change, account deactivation, and session revocation must go through the audited service path before being exposed in an API or UI.
- Certificate release is blocked unless a previous preview audit event matches the current summary IDs, template version, software version, calculation engine, constant set, and budget version.
- Persistent API deployment must provide `SIMVAL_DATABASE_PATH`; request handlers must use scoped database connections rather than long-lived shared connections.

## Verification

- Focused user identity, SQLite user/session persistence, actor-resolution, and permission suite: 25 passed on Python 3.12.10.
- Focused session-backed measurement-window, window-completion, calculation-run, and authentication suite: 31 passed on Python 3.12.10.
- Focused controlled SQLite migration runner suite: 5 passed on Python 3.12.10.
- Focused certificate preview model, preview service, permission, and audit suite: 16 passed on Python 3.12.10.
- Focused API app, authentication, certificate preview service, and session-backed temperature service suite: 44 passed on Python 3.12.10.
- Default regression suite after API endpoint slice: 255 passed, 2 skipped on Python 3.12.10.
- Focused audited user-management, user/session persistence, and authentication suite: 21 passed on Python 3.12.10.
- Focused certificate release, preview, certificate persistence, and workflow suite: 25 passed on Python 3.12.10.
- Focused API app, API settings, API connection lifecycle, certificate release, and certificate preview suite: 22 passed on Python 3.12.10.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| No password, MFA, SSO, or Azure/M365 identity-provider integration exists yet. | Keep local session identity as the backend control boundary for P3 and select the production identity provider before deployment. |
| Admin user-management currently has service tests but no API endpoints. | Expose only session-backed admin endpoints once the UI/admin settings workflow is ready. |
| Some trusted internal services still accept explicit `user_id` strings. | Keep them internal and require API endpoints to call session-backed wrappers for regulated actions. Add wrappers for remaining regulated actions as those API surfaces are implemented. |
| Existing full SQLite schema still uses direct initialization. | Keep direct initialization for test databases now, but split the production schema history into controlled migrations before persistent multi-environment testing or deployment. |
| Certificate preview is audited but not yet persisted as a separate preview record. | Current release gate uses matching preview audit evidence; add a dedicated preview table only if template review requires retaining rendered preview payloads. |
| Release service records artifact metadata but does not render PDF/XLSX bytes. | Keep rendering as the first P4 task so P3 closes on backend control gates without template/UI scope creep. |
| API settings currently cover database path only. | Add host, port, storage path, and identity-provider settings when the deploy target is selected. |
