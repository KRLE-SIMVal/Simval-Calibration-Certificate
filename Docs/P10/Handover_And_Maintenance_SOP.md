# Handover And Maintenance SOP

Status: draft for production readiness review.

## Purpose

This SOP defines how SIMVal maintains the calibration certificate application
after production release when Codex is used as the implementation assistant and
SIMVal retains human approval authority.

## Roles

| Role | Responsibility |
|---|---|
| SIMVal System Owner | Owns production use, release decisions, access, backups, and operational evidence. |
| Laboratory Chief / Domain SME | Approves workflow reality, certificate content, traceability, and audit-facing decisions. |
| Metrology Reviewer | Approves calculation, uncertainty, CMC, rounding, units, and method changes. |
| QA/Compliance Reviewer | Approves validation evidence, deviations, change control, audit trail, and release readiness. |
| IT / Administrator | Maintains hosting, runtime paths, backups, monitoring, authentication, and secrets. |
| Codex Operator | Prompts Codex, reviews proposed changes, runs tests, and collects evidence. |

Codex may implement and explain changes, but Codex is not the approver. A SIMVal
human must approve each production change.

## Change Classification

Every request must be classified before implementation:

- Calculation/metrology change.
- Certificate output/template change.
- Workflow or audit-trail change.
- Role, permission, authentication, or security change.
- Import/parser or source-data traceability change.
- Persistence, migration, backup, restore, or deployment change.
- Documentation-only change.

When a change fits more than one category, use the highest-risk category.

## Required Change Workflow

1. Read `AGENTS.md`, the design requirements, relevant phase logs, and affected
   code.
2. State the change classification and risk.
3. Add or update planned test cases in `Docs/P0/Test_Case_Catalog.md`.
4. Add or update automated tests before or with implementation.
5. Make small, reviewable commits.
6. Explain any metrology, compliance, security, or data-model impact.
7. Run focused tests for the changed area.
8. Run the full default regression suite before release.
9. Generate or retain validation package evidence for release-significant
   changes.
10. Obtain SIMVal human approval before production use.

Calculation logic must never be changed silently. Any change to uncertainty,
CMC interpolation, rounding, units, coverage factor, or error-of-indication
rules requires Metrology Reviewer and QA/Compliance Reviewer approval.

## Regression And Release Evidence

Minimum evidence for a release-significant change:

- Git commit hash.
- Changed files.
- Focused test results.
- Full regression result.
- CI result.
- Validation package or equivalent review evidence.
- Known limitations and residual risks.
- Human approval decision.

The quarterly regression schedule remains mandatory on January 1, April 1,
July 1, and October 1.

## Backup And Restore Controls

Before production database migrations, recovery work, or release-significant
maintenance, create a SQLite backup with JSON evidence. Periodically restore the
backup to a separate verification path and retain restore evidence.

Restore over the live production database requires:

- Human approval.
- Application shutdown.
- Pre-restore backup of the current database.
- Restore from verified backup.
- Post-restore integrity check.
- `/health` and `/readiness` checks.
- Full regression or defined post-restore smoke suite.
- Deviation record if any step fails.

## Deviations And Incidents

Treat the following as deviations until reviewed:

- Failed full regression or CI.
- Failed scheduled quarterly regression.
- Failed backup, restore, or readiness check.
- Unexpected certificate output change.
- Unauthorized access attempt or role mismatch.
- Data import, parser, or traceability mismatch.
- Any production correction to released certificate records.

Deviation handling must include impact assessment, correction, verification, and
approval before routine use continues.

## Security And GDPR Controls

- Do not paste uncontrolled customer data, secrets, passwords, tokens, or private
  keys into prompts.
- Use sanitized fixtures unless controlled fixture execution is explicitly
  enabled.
- Protect backups with the same access controls as the production database.
- Do not log secrets or personal data beyond approved operational evidence.
- Review access and active users at defined intervals.

## Codex Use Limits

Codex may:

- Inspect code and docs.
- Propose risks and recommended solutions.
- Implement scoped changes.
- Add tests and documentation.
- Run regression and summarize evidence.

Codex must not:

- Approve its own changes for production.
- Bypass tests or validation evidence.
- Change calculation or certificate output rules silently.
- Remove audit, traceability, approval, or version-locking controls unless a
  SIMVal human explicitly approves the controlled change.
- Use live customer data unless SIMVal has explicitly approved the data handling.

