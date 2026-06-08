# P6 Implementation Log

Status: completed for backend-served browser workflow shell.

P6 adds the first customer-usable browser surface after P5 validation hardening.
It is intentionally a thin shell over existing audited backend endpoints.

## Scope Implemented

- `GET /app` and `GET /` serve a dependency-free browser workflow shell.
- `GET /app/workflow` exposes the ordered workflow contract used by the browser
  shell.
- The browser workflow includes session, metadata capture, reference equipment
  selection, preview, rendered release, certificate history, and revision
  actions.
- The workflow contract records required roles, endpoint paths, evidence fields,
  and the manual equipment-library policy.
- The browser shell uses the controlled SIMVal logo asset through
  `/design-assets/simval-logo`.
- Manual equipment-library population is explicit in the workflow contract and
  is not bypassed by hidden CRUD behavior.
- Added an ASGI runtime entrypoint at `app.backend.api.main:app` using
  controlled environment settings.

## Scope Not Implemented

- No full single-page frontend framework has been introduced.
- No client-side persistence beyond the current request editor is implemented.
- No graph-based measurement-window selection UI is implemented.
- No production authentication provider or SSO UI is implemented.
- Full equipment-library CRUD remains deferred for manual production setup.

## Compliance Notes

- P6 does not change calculation logic, certificate rendering logic, workflow
  state logic, or release controls.
- The UI calls the same audited API endpoints already covered by backend tests.
- The workflow shell is suitable as an internal controlled operator/reviewer
  surface, not as a public customer portal.

## Verification

- Focused API browser workflow suite: 22 passed on Python 3.12.10.
- Default regression suite after P6 browser workflow shell:
  351 passed, 2 skipped on Python 3.12.10.
- Focused API browser workflow and ASGI entrypoint suite:
  23 passed on Python 3.12.10.
- Default regression suite after ASGI runtime entrypoint:
  359 passed, 2 skipped on Python 3.12.10.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| Browser workflow is functional but utilitarian and not yet optimized for routine technician efficiency. | Add UX review and task-based acceptance tests before production validation. |
| Measurement-window selection is still backend/API driven, not graphical. | Add a validated window-selection UI after core release validation is stable. |
| Authentication remains session-header based in the browser shell. | Select and validate the production authentication provider before deployment. |
