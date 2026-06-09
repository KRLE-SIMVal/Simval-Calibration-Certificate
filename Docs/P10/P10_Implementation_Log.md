# P10 Implementation Log

Status: started.

P10 covers production handover, maintenance governance, and go/no-go controls for
operating the application without an in-house developer.

## Scope Implemented

- Added `Docs/P10/Handover_And_Maintenance_SOP.md`.
- Added `Docs/P10/Production_Readiness_Checklist.md`.
- Added automated regression coverage for required P10 handover controls in
  `tests/unit/test_p10_handover_docs.py`.
- Added a controlled first-user bootstrap helper in
  `app/backend/operations/user_bootstrap.py`.
- Added a first-user maintenance CLI:
  `scripts/maintenance/bootstrap_first_user.py`.
- First-user bootstrap is allowed only when the database has no user accounts.
- Bootstrap can issue a temporary local session for development/runtime access
  and records user-account audit evidence with `system-bootstrap` as actor.
- Added admin-only user-maintenance API endpoints:
  `GET /users`, `POST /users`, `POST /users/{user_id}/roles`,
  `POST /users/{user_id}/deactivation`, and
  `POST /user-sessions/{session_id}/revocation`.
- User-maintenance API routes use the existing `MANAGE_USERS_AND_ROLES`
  permission boundary and record reasoned audit evidence for role changes,
  deactivation, and session revocation.
- Added the user-administration maintenance controls to the browser workflow
  contract so the exposed API surface is discoverable from `/app/workflow`.
- Added `Docs/P10/Production_Runtime_Guide.md` for controlled startup,
  environment, first-admin bootstrap, readiness verification, and unresolved
  production decisions.
- Added `deployment/production.env.example` with runtime path placeholders only.
- Expanded `README.md` from placeholder text to local runtime, verification, and
  production-readiness entry points.
- Recorded approved free-service production decisions: temperature-only v1,
  Microsoft Entra ID Free authentication boundary, existing SIMVal-controlled
  internal hosting, SQLite/artifact storage on controlled SIMVal storage, and
  free validation tooling.
- Added `SIMVAL_ENABLED_DISCIPLINES=temperature` to the production environment
  example so pressure remains a later add-on rather than a production v1 path.

## Scope Not Implemented

- Microsoft Entra ID Free authentication integration and deployment-specific
  TLS/host verification evidence are not implemented in this repository yet.
- Final SIMVal retention periods and backup storage location are not yet
  approved.
- PDF/A and digital-signature policy decisions remain pending.
- Full production equipment library data entry remains deferred until production
  readiness, per project decision.

## Compliance Notes

- P10 documentation does not change calculation logic, certificate rendering,
  audit trail behavior, or role permissions.
- The maintenance SOP assumes Codex may propose and implement changes, but a
  SIMVal human must approve every change before production use.
- Any future calculation, uncertainty, rounding, CMC, workflow, RBAC, audit, or
  certificate-template change requires matching automated tests before or with
  implementation.
- First-user bootstrap is a one-time access setup control. It does not replace
  the approved Microsoft Entra ID Free production authentication boundary.
- Production v1 is temperature-only. Pressure calculation infrastructure exists
  for a later phase but is disabled by `SIMVAL_ENABLED_DISCIPLINES=temperature`.

## Verification

- Focused P10 handover document regression test:
  2 passed on Python 3.12.10.
- Focused P10 plus production-hardening regression slice:
  36 passed on Python 3.12.10.
- First-user bootstrap focused suite:
  19 passed on Python 3.12.10.
- User-management API focused suite:
  36 passed on Python 3.12.10.
- Production runtime documentation focused suite:
  4 passed on Python 3.12.10.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| No in-house developer will be available after release. | Use the SOP to require small Codex-assisted changes, human approval, focused tests, full regression, validation package evidence, and CI review before use. |
| Production authentication and hosting are selected but not integrated or verified yet. | Implement and verify Microsoft Entra ID Free on the existing SIMVal-controlled host before production go-live. |
| Operational controls can drift after release. | Keep P10 docs under version control and retain quarterly regression, backup, restore, and readiness evidence. |
| First-user bootstrap can create a powerful admin account. | Keep bootstrap limited to empty databases, retain audit evidence, and replace temporary local sessions with the approved production authentication model before go-live. |
| User-management API is session-header based until Entra ID Free integration is implemented. | Keep these endpoints admin-only and audit-backed now; retest them with Entra ID Free before go-live. |
| Runtime guide still cannot provide site-specific TLS, monitoring, retention, or PDF signature evidence. | Keep those as go/no-go blockers and add deployment-specific evidence before production use. |
