# P23 Implementation Log

Status: implemented for runtime smoke evidence collection.

P23 adds a repeatable smoke evidence command for a running SIMVal API. The
command is intended for the approved host after startup and before final
production-readiness review.

## Scope Implemented

- Added `scripts/validation/generate_production_smoke_evidence.py`.
- The command checks `GET /health`, `GET /readiness`, `GET /app`, and
  `GET /app/workflow`.
- The command returns exit code `0` only when all smoke checks pass and exit
  code `2` when any smoke check fails.
- The readiness check requires database, controlled schema baseline, and
  artifact storage components to be `ok`.
- The JSON payload records endpoint paths, HTTP status codes, pass/fail status,
  generated timestamp, base URL, temperature-only scope, and software version
  without recording response bodies.
- Updated P10 runtime guide and readiness checklist.

## Compliance Notes

- This makes host smoke evidence repeatable and retainable for System Owner and
  QA/Laboratory review.
- The smoke evidence does not replace live Entra, TLS, backup/restore,
  reviewer-independence, retention, or human approval evidence.
- No calculation, uncertainty, CMC, rounding, certificate rendering, release,
  audit immutability, reviewer-independence, authentication, or token-validation
  logic was changed.

## Verification

- Focused production smoke evidence suite:
  3 passed on Python 3.12.10.
- Local running API smoke evidence:
  exit code 0 with `/health`, `/readiness`, `/app`, and `/app/workflow`
  passing against `http://127.0.0.1:8010`.
- Full repository regression suite:
  485 passed, 2 skipped on Python 3.12.10.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| The smoke command checks public runtime endpoints only and cannot prove Entra token exchange or role-based workflows. | Retain separate Entra session, access review, and reviewer-independence workflow evidence before go-live. |
| The command records status evidence, not full page screenshots or browser rendering evidence. | Use it as runtime smoke evidence and retain any UI/browser screenshots separately if required by QA/Laboratory review. |
