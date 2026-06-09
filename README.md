# SIMVal Calibration Certificate

Controlled web application for SIMVal calibration workflows, certificate
generation, uncertainty evidence, audit trail, and role-based approval.

The project is built for GxP/ISO 17025-oriented use. Calculation logic,
certificate release, user administration, validation evidence, and operational
controls are tested and documented before production use.

## Local Runtime

Install Python 3.12 dependencies:

```powershell
python -m pip install -e ".[api,test]"
```

Set runtime paths:

```powershell
$env:SIMVAL_DATABASE_PATH = ".runtime\simval.sqlite3"
$env:SIMVAL_ARTIFACT_STORAGE_PATH = ".runtime\artifacts"
```

Start the API:

```powershell
python -m uvicorn app.backend.api.main:app --host 127.0.0.1 --port 8010
```

Open the browser workflow at:

```text
http://127.0.0.1:8010/app
```

## Verification

Run the default regression suite:

```powershell
pytest
```

Controlled internal fixture tests are excluded by default and require explicit
approval plus `SIMVAL_RUN_CONTROLLED_FIXTURE_TESTS=1`.

## Production Readiness

Approved v1 production decisions:

- Scope is temperature certificates only; pressure remains disabled until a
  later approved phase.
- Authentication boundary is Microsoft Entra ID Free / existing SIMVal
  Microsoft work accounts. Entra tokens are exchanged through
  `POST /auth/entra/session` for short audited local SIMVal sessions.
- Hosting is an existing SIMVal-controlled internal PC/server/VM using only
  free/open-source runtime components.
- Database and certificate artifacts use controlled SQLite/local storage with
  backup and restore evidence.
- Reviewer independence is enforced by backend audit-evidence checks for
  review, QA approval, and certificate-release conflicts.

Use these controlled documents before routine production use:

- `Docs/P10/Production_Runtime_Guide.md`
- `Docs/P10/Production_Readiness_Checklist.md`
- `Docs/P10/Handover_And_Maintenance_SOP.md`
- `Docs/P0/Test_Strategy.md`
- `Docs/P0/Validation_And_Regression_Plan.md`

Production use remains blocked until live Entra tenant/app registration
verification, TLS/host evidence, retention, backup storage,
reviewer-independence production evidence, and final human QA/laboratory
approval are complete.
