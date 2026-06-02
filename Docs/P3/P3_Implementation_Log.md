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

## Scope Not Implemented

- No password, SSO, or external identity-provider integration yet.
- No FastAPI endpoints yet.
- Existing P2 backend services still accept explicit `user_id` strings internally; P3 API-facing wrappers must resolve sessions before calling them.
- No dedicated user-management audit workflow yet for creating, deactivating, or role-changing user accounts.
- No production migration runner yet.

## Compliance Notes

- This slice does not change calculation logic or reported metrology values.
- The service boundary prevents future API calls from using arbitrary free-form user ids as audit actors.
- User roles remain controlled through the existing permission matrix.
- Multiple assigned roles are supported at the user-account level; an active user is authorized when at least one assigned role permits the requested action.
- Sessions are time bounded and can be revoked.
- Inactive users cannot perform regulated actions even when a session record exists.

## Verification

- Focused user identity, SQLite user/session persistence, actor-resolution, and permission suite: 25 passed on Python 3.12.10.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| No password, MFA, SSO, or Azure/M365 identity-provider integration exists yet. | Keep local session identity as the backend control boundary for P3 and select the production identity provider before deployment. |
| User creation and role changes are not yet audited workflows. | Add an admin user-management service that writes audit events for create, deactivate, role change, and session revocation. |
| P2 services still accept explicit `user_id` strings. | Expose P2 actions through P3 API/service wrappers that resolve `session_id` to an authenticated actor before invoking internal services. |
| SQLite schema still uses direct initialization. | Add controlled migration execution before production rollout or persistent multi-environment testing. |
