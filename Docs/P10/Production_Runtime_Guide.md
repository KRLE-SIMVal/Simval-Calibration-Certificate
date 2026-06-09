# Production Runtime Guide

Status: controlled deployment baseline.

This guide describes the repeatable runtime setup for production v1. The
approved v1 production scope is temperature certificates only, hosted on
existing SIMVal-controlled infrastructure, using Microsoft Entra ID Free where
available for the authentication boundary.

Pressure workflow code remains a future extension point and is not enabled for
production v1.

## Prerequisites

- Python 3.12 installed from an approved source.
- Repository checked out to a controlled application directory.
- Application dependencies installed with:

```powershell
python -m pip install -e ".[api]"
```

- Controlled database and artifact directories created by the system owner or
  administrator.
- Host-level access control and TLS approved before routine use.
- Microsoft Entra ID Free tenant/application configuration approved for the
  production authentication boundary.

## Environment

Use `deployment/production.env.example` as the placeholder reference for the
required runtime variables:

```powershell
$env:SIMVAL_DATABASE_PATH = "C:\SIMVal\data\simval.sqlite3"
$env:SIMVAL_ARTIFACT_STORAGE_PATH = "C:\SIMVal\artifacts"
$env:SIMVAL_ENABLED_DISCIPLINES = "temperature"
$env:SIMVAL_AUTH_PROVIDER = "entra_id_free"
$env:SIMVAL_HOSTING_MODEL = "simval_internal_host"
$env:SIMVAL_REVIEWER_INDEPENDENCE_REQUIRED = "true"
```

The real production values must be stored in the approved host or service
configuration. Do not commit production paths, credentials, tokens, private
keys, or customer data to source control.

## First Admin

For a new empty database, create the first admin only once:

```powershell
python scripts\maintenance\bootstrap_first_user.py `
  --database-path $env:SIMVAL_DATABASE_PATH `
  --user-id krle-simval `
  --display-name "Kristian Leth" `
  --email krle@simval.dk `
  --session-id krle-local-session `
  --session-hours 8 `
  --evidence-output C:\SIMVal\evidence\first-user-bootstrap.json
```

The bootstrap command is rejected after any user account exists. Temporary local
sessions are a controlled bridge until the approved production authentication
provider is configured.

For production, temporary local sessions must be replaced by the approved
Microsoft Entra ID Free authentication boundary before routine use. The local
bootstrap remains only for controlled setup and recovery on an empty database.

## Start Command

Start the API behind the approved host boundary:

```powershell
python -m uvicorn app.backend.api.main:app --host 127.0.0.1 --port 8010
```

Do not expose the application directly to users without the approved TLS and
authentication boundary.

## Runtime Verification

After startup, verify:

- `GET /health` returns HTTP 200 with status `ok`.
- `GET /readiness` returns HTTP 200 with database and artifact storage `ok`.
- `GET /users` with an admin session returns the active user list for access
  review.
- `GET /app/workflow` lists the regulated workflow and user-administration
  maintenance endpoints.
- `SIMVAL_ENABLED_DISCIPLINES` is set to `temperature` for production v1.

Any failed readiness, access-review, backup, restore, or regression evidence is
a deviation until reviewed and resolved.

## Operational Schedule

- Run the full automated regression suite before release and after changes.
- Retain CI validation evidence and reviewer disposition records.
- Schedule quarterly regression on Jan 1, Apr 1, Jul 1, and Oct 1.
- Schedule SQLite backups and periodic restore drills once the production host
  and storage location are fixed.
- Run stale `.pending` artifact cleanup under a controlled maintenance task.

## Open Production Decisions

Routine production use remains blocked until these decisions are approved and
verified:

- Microsoft Entra ID Free application/user lifecycle verification evidence.
- TLS/hosting boundary and host monitoring on the existing SIMVal-controlled
  internal host.
- Backup retention period, off-machine storage, and restore drill schedule.
- Certificate, raw-source-file, validation, and audit evidence retention.
- PDF/A and digital-signature policy, if required by SIMVal or customer
  contracts.

## Approved Free-Service Production Decisions

| Area | Approved v1 decision |
|---|---|
| Scope | Temperature certificates only. Pressure remains disabled until a later approved phase. |
| Authentication | Microsoft Entra ID Free / existing Microsoft work accounts. |
| Hosting | Existing SIMVal-controlled internal PC/server/VM; no paid cloud service required for v1. |
| Database | SQLite on controlled SIMVal storage with backup and restore evidence. |
| Artifacts | Controlled local artifact directory backed up with the database. |
| Validation | Repository test suite, GitHub Actions within free included usage, and retained validation package evidence. |
| Reviewer independence | Required before go-live; local/bootstrap sessions are not production approval evidence. |
