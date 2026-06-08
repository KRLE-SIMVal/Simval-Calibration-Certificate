# Production Runtime Guide

Status: controlled deployment baseline.

This guide describes the repeatable runtime setup for a local or hosted
production instance after the hosting owner has selected the approved host,
TLS boundary, backup location, and authentication provider.

## Prerequisites

- Python 3.12 installed from an approved source.
- Repository checked out to a controlled application directory.
- Application dependencies installed with:

```powershell
python -m pip install -e ".[api]"
```

- Controlled database and artifact directories created by the system owner or
  administrator.
- Host-level access control, TLS, and production authentication/SSO decision
  approved before routine use.

## Environment

Use `deployment/production.env.example` as the placeholder reference for the
required runtime variables:

```powershell
$env:SIMVAL_DATABASE_PATH = "C:\SIMVal\data\simval.sqlite3"
$env:SIMVAL_ARTIFACT_STORAGE_PATH = "C:\SIMVal\artifacts"
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

- Production authentication provider and user lifecycle process.
- TLS/hosting boundary and host monitoring.
- Backup retention period, off-machine storage, and restore drill schedule.
- Certificate, raw-source-file, validation, and audit evidence retention.
- PDF/A and digital-signature policy, if required by SIMVal or customer
  contracts.
