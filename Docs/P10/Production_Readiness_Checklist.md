# Production Readiness Checklist

Status: draft go/no-go checklist.

Use this checklist before routine production use.

## Application Build

| Check | Expected evidence | Status |
|---|---|---|
| Python runtime | Python 3.12 installed and controlled. | Pending |
| Dependencies | `pip install -e .[api,test]` succeeds in clean environment. | Pending |
| Default regression | Full `pytest` suite passes. | Pending |
| CI | Latest main branch CI passes. | Pending |
| Validation package | Validation package generated and reviewed. | Pending |

## Runtime Configuration

| Check | Expected evidence | Status |
|---|---|---|
| Database path | `SIMVAL_DATABASE_PATH` points to controlled SQLite database. | Pending |
| Artifact path | `SIMVAL_ARTIFACT_STORAGE_PATH` points to controlled artifact directory. | Pending |
| Enabled scope | `SIMVAL_ENABLED_DISCIPLINES=temperature` for production v1. | Pending |
| Production profile | `SIMVAL_RUNTIME_PROFILE=production` set; implicit or local-session auth rejected. | Pending |
| Hosting model | Existing SIMVal-controlled internal host/VM approved; no paid cloud service required. | Decision approved |
| Liveness | `GET /health` returns HTTP 200. | Pending |
| Readiness | `GET /readiness` returns HTTP 200 with database, controlled SQLite schema baseline, and artifact storage `ok`. | Pending |
| Migration history | Database has no applied schema migrations outside the controlled application migration plan. | Pending |
| Smoke evidence | `generate_production_smoke_evidence.py` retained for `/health`, `/readiness`, `/app`, and `/app/workflow`. | Pending |
| Logs | Logs do not expose secrets or uncontrolled customer data. | Pending |

## Certificate Workflow

| Check | Expected evidence | Status |
|---|---|---|
| Metadata capture | Certificate metadata is stored with user and timestamp evidence. | Pending |
| Reference equipment | Selected equipment snapshots are stored and checked for suitability. | Pending |
| Preview gate | Release is blocked until a matching preview exists. | Pending |
| Upload controls | Calibration XLSX/PDF uploads reject wrong extension, oversize files, and malformed XLSX ZIP structures. | Pending |
| Parser XML safety | ValProbe workbook parser rejects oversized XML members, unsafe XML declarations, and malformed XML before parsing. | Pending |
| Parser validation | ValProbe XLSX parser validation evidence retained for approved workbook variants, malformed workbook rejection, and raw-file traceability before routine production use. | Pending |
| Parser gate | Provisional ValProbe XLSX parser disabled for routine production until validation evidence is approved and referenced in the production readiness report. | Pending |
| PDF contract | Rendered certificate validates structure, logos, version evidence, and no placeholders. | Pending |
| Manual release artifact | Any manual release verifies existing local artifact path and SHA-256 before database release record creation. | Pending |
| Single DUT | Single-equipment certificate can be generated. | Pending |
| Batch DUT | Multi-equipment certificate can be generated. | Pending |
| History | Released artifacts and revisions are retrievable. | Pending |

## Operational Controls

| Check | Expected evidence | Status |
|---|---|---|
| Backup | SQLite backup evidence includes checksum, size, timestamp, and integrity check. | Pending |
| Restore drill | Restore to a separate target path succeeds and evidence is retained. | Pending |
| Pending cleanup | Stale `.pending` cleanup evidence retained when run. | Pending |
| Quarterly regression | Schedule exists for Jan 1, Apr 1, Jul 1, and Oct 1. | Pending |
| Deviation evidence | Failed scheduled run produces deviation evidence. | Pending |
| Retention | Backup, certificate, raw file, and validation evidence retention approved. | Pending |
| Readiness report | `generate_production_readiness_report.py` retained with no blockers before go-live approval. | Pending |

## Security And Access

| Check | Expected evidence | Status |
|---|---|---|
| Production authentication | Authentication provider selected and verified. | Pending |
| Entra ID Free | Microsoft Entra ID Free token exchange verified through `POST /auth/entra/session` with approved tenant, app registration, audience, and active local user email match. | Pending |
| Roles | Operator, reviewer, QA approver, admin, and read-only roles verified. | Pending |
| Reviewer independence | Same-user preparation/calculation/review/release is technically blocked by backend audit-evidence checks or documented as approved deviation. | Implemented; production evidence pending |
| First admin user | Initial admin user created through controlled first-user bootstrap or production identity provider. | Pending |
| User review | Active users reviewed before go-live. | Pending |
| Session issuance audit | `user_session_created` audit event retained for Entra-backed local session issuance. | Pending |
| Secrets | Secrets are stored outside source control. | Pending |
| Backup access | Backup access control matches production database access control. | Pending |

## Go/No-Go Rule

Production use is blocked if any of the following are unresolved:

- Full regression or CI failure.
- Missing validation package review for release-significant changes.
- Failed backup or restore drill.
- Failed `/readiness` check.
- Production readiness report contains blockers.
- Missing ValProbe parser validation evidence for routine production source-data
  import.
- Missing Microsoft Entra ID Free live tenant/app registration, token exchange,
  or user lifecycle verification.
- Production runtime profile is not set or local-session authentication is
  enabled for routine production.
- Production scope not restricted to temperature certificates.
- Provisional XLSX parser enabled for routine production without approved parser
  validation evidence.
- Manual release artifact verification failure.
- Missing reviewer independence production verification evidence or approved
  deviation.
- Unapproved calculation, uncertainty, CMC, rounding, or certificate-template
  change.
- Missing human approval from System Owner and QA/Compliance Reviewer.
