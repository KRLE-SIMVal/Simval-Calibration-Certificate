# P15 Implementation Log

Status: started for production v1 scope and deployment decision controls.

P15 records the approved free-service production decisions and adds a runtime
discipline policy so production v1 can be temperature-only while preserving the
pressure extension point for a later approved phase.

## Approved Decisions

- Production v1 scope is temperature certificates only.
- Pressure remains deferred and disabled in production v1.
- Authentication boundary is Microsoft Entra ID Free / existing SIMVal
  Microsoft work accounts.
- Hosting is an existing SIMVal-controlled internal PC/server/VM.
- Database is SQLite on controlled SIMVal storage for v1.
- Certificate artifacts are stored on controlled SIMVal storage.
- Validation uses repository test tooling, GitHub Actions within included/free
  usage, generated validation packages, and retained human approval evidence.
- Reviewer independence is required before go-live.

## Scope Implemented

- Added `SIMVAL_ENABLED_DISCIPLINES` runtime setting.
- Default enabled discipline is `temperature`.
- Added API job-creation enforcement so disabled disciplines are rejected before
  calibration job or audit evidence is created.
- Added Microsoft Entra ID Free token-exchange configuration and
  `/auth/entra/session` support in the follow-on production-auth slice.
- Entra-backed local sessions are issued only for existing active local users
  and are recorded with `user_session_created` audit evidence.
- Updated `deployment/production.env.example` with the approved free-service
  production choices.
- Updated P10 runtime/readiness docs and README with the approved decisions.
- Added tests for settings parsing, pressure-disabled job creation, pressure
  enablement as a future extension, and P10 decision documentation.

## Compliance Notes

- No temperature calculation, rounding, CMC, uncertainty, certificate rendering,
  audit-event immutability, or release logic was changed.
- Pressure calculation foundation remains in the codebase for later validation,
  but production v1 blocks pressure job creation by deployment policy.
- Local first-user/bootstrap sessions remain development/setup controls and are
  not production approval evidence.

## Verification

- Focused API settings, API upload workflow, and P10 documentation suite:
  27 passed on Python 3.12.10.
- Full repository regression suite: 438 passed, 2 skipped on Python 3.12.10.
- Follow-on Entra/API/documentation focused suite:
  70 passed on Python 3.12.10.
- Follow-on full repository regression suite:
  456 passed, 2 skipped on Python 3.12.10.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| Microsoft Entra ID Free integration is implemented but not live-tenant verified. | Verify `POST /auth/entra/session` with the approved SIMVal tenant/app registration before go-live; keep local session auth as setup/development only. |
| Reviewer independence is approved but not technically enforced yet. | Add reviewer-independence checks before production release validation. |
| Free internal hosting still needs site-specific TLS, monitoring, backup, and restore evidence. | Collect deployment-specific evidence using the P10 readiness checklist before go-live. |
