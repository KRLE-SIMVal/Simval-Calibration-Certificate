# Production Runtime Guide

Status: controlled deployment baseline.

This guide describes the repeatable runtime setup for production v1. The
approved v1 production scope is temperature certificates only, hosted on
existing SIMVal-controlled infrastructure, using Microsoft Entra ID Free where
available for the authentication boundary.

Manual pressure certificate release is available only when pressure is
explicitly enabled and the manual pressure entry, calculation, review, preview,
and release workflow has been executed with controlled source evidence.
Known-schema automatic pressure CSV import is available for paired
`timestamp,reference,indication[,unit]` source files through
`POST /calibration-jobs/{job_id}/pressure-automatic-entry`. The import records
parser evidence, source alignment, DUT/window creation, and workflow-transition
audit events. Generic `.csv`, `.json`, and `.txt` source evidence can still be
uploaded and retained with checksum and audit evidence; unknown CSV/XLSX column
mapping remains outside the v1 parser boundary and requires controlled manual
entry or a future approved mapping workflow.
Pressure-specific PDF wording and template layout require retained approval
evidence generated with
`scripts\validation\generate_pressure_template_approval_evidence.py` before
claiming routine DANAK-ready pressure certificate production release.

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
$env:SIMVAL_RUNTIME_PROFILE = "production"
$env:SIMVAL_ENABLED_DISCIPLINES = "temperature"
$env:SIMVAL_AUTH_PROVIDER = "entra_id_free"
$env:SIMVAL_ENTRA_TENANT_ID = "<SIMVal Entra tenant id>"
$env:SIMVAL_ENTRA_CLIENT_ID = "<SIMVal app registration client id>"
$env:SIMVAL_ENTRA_AUDIENCE = "<SIMVal accepted token audience>"
$env:SIMVAL_ENTRA_LOCAL_SESSION_HOURS = "8"
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

## Microsoft Entra ID Free Authentication

Production sign-in uses Microsoft Entra ID Free as the external identity
boundary. The API exposes `POST /auth/entra/session` for exchanging a verified
Entra bearer token for a short local SIMVal session.

The exchange validates the Entra token signature through the tenant JWKS,
issuer, audience, tenant id, v2.0 token version, expiry, and required identity
claims. The local SIMVal user account is then matched by email address against
an existing active user account. Roles are not accepted from Entra token claims;
application roles remain controlled in the local SIMVal user table and audit
trail.

The issued local session is audited as a `user_session_created` event and its
expiry is no later than the Entra token expiry or
`SIMVAL_ENTRA_LOCAL_SESSION_HOURS`, whichever is earlier.

Before routine production use, verify that:

- `SIMVAL_RUNTIME_PROFILE=production` is set; production startup rejects an
  implicit or local-session authentication provider.
- `SIMVAL_AUTH_PROVIDER=entra_id_free`.
- `SIMVAL_ENTRA_TENANT_ID`, `SIMVAL_ENTRA_CLIENT_ID`, and
  `SIMVAL_ENTRA_AUDIENCE` match the approved SIMVal app registration.
- At least one controlled local user has an active account whose email matches
  the Entra `preferred_username`, `email`, or `upn` claim.
- `POST /auth/entra/session` succeeds with an approved SIMVal account and the
  returned `X-Session-Id` works with `GET /me`.
- The session issuance audit event is retained.

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
- `GET /readiness` returns HTTP 200 with database, controlled SQLite schema
  baseline, and artifact storage `ok`.
- `GET /users` with an admin session returns the active user list for access
  review.
- `POST /auth/entra/session` can issue a local audited session from a verified
  Entra token for an active local user.
- `GET /app/workflow` lists the regulated workflow and user-administration
  maintenance endpoints.
- `SIMVAL_ENABLED_DISCIPLINES` is set to `temperature` for production v1.
- Same-user preparation/calculation, technical review approval, QA approval,
  and certificate release are blocked by reviewer-independence audit-evidence
  checks.
- ValProbe XLSX uploads are stored as raw evidence unless the provisional parser
  is explicitly enabled for controlled fixture validation; do not enable it for
  routine production use until parser validation evidence is approved.
- Known-schema automatic pressure CSV import requires `UploadedFileKind.OTHER`,
  a `.csv` source retained under controlled artifact storage, at least two
  linked timezone-aware readings, and a pressure job in automatic mode.
- Uploaded calibration workbooks and verification PDFs are rejected unless the
  file kind, filename extension, bounded request-size stream, and XLSX ZIP
  structure pass backend controls.
- Manual certificate release requires the supplied local artifact to exist under
  the controlled artifact directory and match the supplied SHA-256 before the
  database release record is written. Prefer rendered release endpoints for
  routine operation.

Any failed readiness, schema-baseline, access-review, backup, restore, or
regression evidence is a deviation until reviewed and resolved.

Retain a runtime smoke evidence file after startup:

```powershell
python scripts\validation\generate_production_smoke_evidence.py `
  --base-url http://127.0.0.1:8010 `
  --software-version <approved release version> `
  --output C:\SIMVal\evidence\production-smoke-evidence.json
```

The smoke evidence checks `GET /health`, `GET /readiness`, `GET /app`, and
`GET /app/workflow`. It returns exit code `2` if any endpoint fails or readiness
does not report database, schema, and artifact storage components as `ok`.

## Production Readiness Report

Before production go-live review, generate and review a controlled pilot plan:

```powershell
python scripts\validation\generate_pilot_validation_plan.py `
  --release-version <approved pilot version> `
  --output-dir C:\SIMVal\evidence\pilot-validation-plan
```

The pilot plan maps IQ/OQ/PQ validation activities to the retained evidence keys
used by the production readiness report. It does not permit routine production
use by itself.

After executing the controlled pilot activities and retaining each evidence
file, generate the pilot validation package:

```powershell
python scripts\validation\generate_runtime_profile_evidence.py `
  --output C:\SIMVal\evidence\runtime-profile.json

python scripts\validation\generate_parser_validation_evidence.py `
  --parser-version valprobe-xlsx-parser-v1 `
  --fixture-manifest tests\fixtures\example_files_manifest.json `
  --parser-test-report C:\SIMVal\evidence\parser-tests.xml `
  --controlled-fixture-report C:\SIMVal\evidence\controlled-fixtures.xml `
  --controlled-fixtures-enabled true `
  --reviewer-approved `
  --output C:\SIMVal\evidence\valprobe-parser-validation.json

python scripts\validation\generate_backup_restore_validation_evidence.py `
  --backup-evidence C:\SIMVal\evidence\backup-evidence.json `
  --restore-evidence C:\SIMVal\evidence\restore-evidence.json `
  --reviewer-approved `
  --output C:\SIMVal\evidence\backup-restore-validation.json

python scripts\validation\generate_reviewer_independence_evidence.py `
  --workflow-evidence C:\SIMVal\evidence\workflow-evidence.json `
  --operator-user <operator account id> `
  --technical-reviewer-user <technical reviewer account id> `
  --qa-approver-user <QA approver account id> `
  --release-user <release actor account id> `
  --blocked-same-user-attempts 1 `
  --reviewer-approved `
  --output C:\SIMVal\evidence\reviewer-independence.json

python scripts\validation\generate_retention_policy_evidence.py `
  --policy-file C:\SIMVal\evidence\retention-policy.json `
  --reviewer-approved `
  --output C:\SIMVal\evidence\retention-policy-evidence.json

python scripts\validation\generate_human_approval_evidence.py `
  --approval-file C:\SIMVal\evidence\go-no-go-approval.json `
  --software-version <approved release version> `
  --output C:\SIMVal\evidence\human-approval-evidence.json

python scripts\validation\generate_live_entra_evidence.py `
  --auth-evidence C:\SIMVal\evidence\live-entra-source.json `
  --reviewer-approved `
  --output C:\SIMVal\evidence\live-entra-evidence.json

python scripts\validation\generate_tls_host_evidence.py `
  --host-evidence C:\SIMVal\evidence\tls-host-source.json `
  --reviewer-approved `
  --output C:\SIMVal\evidence\tls-host-evidence.json

python scripts\validation\generate_pilot_validation_package.py `
  --release-version <approved pilot version> `
  --pilot-plan C:\SIMVal\evidence\pilot-validation-plan\pilot-validation-plan.json `
  --evidence runtime_profile=C:\SIMVal\evidence\runtime-profile.json `
  --evidence smoke_evidence=C:\SIMVal\evidence\production-smoke-evidence.json `
  --evidence valprobe_parser_validation=C:\SIMVal\evidence\valprobe-parser-validation.json `
  --evidence reviewer_independence=C:\SIMVal\evidence\reviewer-independence.json `
  --evidence backup_restore=C:\SIMVal\evidence\backup-restore-validation.json `
  --output-dir C:\SIMVal\evidence\pilot-validation-package
```

The command reuses the standard IQ/OQ/PQ validation package format and fails if
any required pilot evidence file is missing.

Before go-live review, generate a JSON readiness report from the approved
runtime environment:

```powershell
python scripts\validation\generate_production_readiness_report.py `
  --software-version <approved release version> `
  --live-entra-verified `
  --tls-host-verified `
  --backup-restore-verified `
  --reviewer-independence-verified `
  --valprobe-parser-validated `
  --retention-policy-approved `
  --final-human-approval-recorded `
  --evidence validation_package=Docs\Validation\evidence\latest\validation-package `
  --evidence live_entra=C:\SIMVal\evidence\live-entra-evidence.json `
  --evidence tls_host=C:\SIMVal\evidence\tls-host-evidence.json `
  --evidence backup_restore=C:\SIMVal\evidence\backup-restore-validation.json `
  --evidence reviewer_independence=C:\SIMVal\evidence\reviewer-independence.json `
  --evidence smoke_evidence=C:\SIMVal\evidence\production-smoke-evidence.json `
  --evidence valprobe_parser_validation=C:\SIMVal\evidence\valprobe-parser-validation.json `
  --evidence retention_policy=C:\SIMVal\evidence\retention-policy-evidence.json `
  --evidence human_approval=C:\SIMVal\evidence\human-approval-evidence.json `
  --output C:\SIMVal\evidence\production-readiness.json
```

The command returns exit code `2` while blockers remain and exit code `0` only
when the report is ready for go-live review. It does not replace human System
Owner and QA/Laboratory approval.

Each verified go-live flag must have a matching retained evidence reference in
the report. For example, `--live-entra-verified` requires
`--evidence live_entra=<controlled record>`. If a verified flag is supplied
without the matching evidence reference, the report remains blocked.
`--valprobe-parser-validated` similarly requires
`--evidence valprobe_parser_validation=<controlled parser validation record>`.
`--retention-policy-approved` requires a generated
`--evidence retention_policy=<controlled retention-policy evidence JSON>` with
`status` set to `passed`.
`--final-human-approval-recorded` requires a generated
`--evidence human_approval=<controlled human approval evidence JSON>` with
`status` set to `passed`.
`--live-entra-verified` requires a generated
`--evidence live_entra=<controlled live Entra evidence JSON>` with `status` set
to `passed`.
`--tls-host-verified` requires a generated
`--evidence tls_host=<controlled TLS/host evidence JSON>` with `status` set to
`passed`.

The report also checks whether each supplied evidence reference exists from the
current working directory or as the supplied absolute path. Existing file
references are recorded in the report manifest with SHA-256 and byte size.
Missing references are listed in `unavailable_references` and keep the report
blocked.

## Operational Schedule

- Run the full automated regression suite before release and after changes.
- Retain CI validation evidence and reviewer disposition records.
- Schedule quarterly regression on Jan 1, Apr 1, Jul 1, and Oct 1.
- Schedule SQLite backups and periodic restore drills once the production host
  and storage location are fixed.
- Run stale `.pending` artifact cleanup under a controlled maintenance task.

## Open Production Decisions

Routine production use remains blocked until these items are approved and
verified:

- Microsoft Entra ID Free live tenant/app registration and user lifecycle
  verification evidence.
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
| Reviewer independence | Backend audit-evidence checks block same-user preparation/calculation, review approval, QA approval, and release conflicts; production verification evidence is still required before go-live. |
