# Validation And Regression Plan

## Validation Objective

The application must produce evidence that it is fit for controlled SIMVal calibration certificate work under DANAK/ISO 17025-oriented expectations.

Because legacy examples will not be supplied, validation must rely on:

- First-principles calculation tests.
- GUM and DANAK AB11 traceability.
- Approved worked examples.
- Requirements-to-test traceability.
- Automated regression evidence.
- Review and approval records.

## Validation Evidence Set

Each validated release should retain:

- Requirements version.
- Test-case catalog version.
- Source commit/version.
- Calculation-engine version.
- Constants and budget fixture versions.
- Automated test results.
- Coverage summary where available.
- Validation report.
- Known limitations.
- Reviewer approval.

## Validation Stages

| Stage | Purpose | Evidence |
|---|---|---|
| P0 | Define requirements, tests, controls, and architecture. | P0 docs and council approval. |
| Test skeleton | Prove automated tests can run in CI. | CI run and sample report. |
| Calculation validation | Prove formulas against worked examples. | Unit tests and metrology review. |
| Workflow validation | Prove state transitions, permissions, audit. | Integration/compliance tests. |
| Certificate validation | Prove output content and release locking. | Rendering tests and artifact evidence. |
| Release validation | Prove full system behavior. | Full validation report. |
| Quarterly regression | Prove continued health without code changes. | Scheduled retained evidence. |

## Quarterly Regression Control

The full regression suite must run automatically on:

- January 1.
- April 1.
- July 1.
- October 1.

Minimum scheduled run contents:

- Unit tests.
- Integration tests.
- Regression tests.
- Compliance tests.
- Security/RBAC tests.
- Certificate rendering tests.
- Validation report generation.

Evidence retention:

```text
Docs/Validation/evidence/<year>/<quarter>/
  test-results/
  validation-report.*
  environment.*
  logs/
  reviewer-disposition.*
```

Final storage layout can change when CI tooling is selected, but the evidence content must remain.

Current CI implementation:

- Scheduled quarterly runs write generated evidence under
  `Docs/Validation/evidence/<year>/Q<n>/` in the workflow workspace.
- Push, pull-request, and manual runs write generated evidence under
  `Docs/Validation/evidence/latest`.
- The workflow uploads the generated evidence tree as a GitHub Actions artifact.
- The validation report records trigger event, run type, quarter, CI metadata,
  platform metadata, controlled-fixture policy, and evidence paths.
- The workflow generates a draft validation package under
  `validation-package/` inside the evidence directory.
- The validation package contains `validation-package.json`,
  `validation-package.md`, and `reviewer-disposition.md`.
- Validation package evidence entries store paths and SHA-256 checksums rather
  than embedding controlled source documents directly.

## Failure Handling

Any quarterly regression failure must:

- Mark the run as failed.
- Create a tracked issue or deviation.
- Identify affected feature area.
- Identify whether routine use may continue.
- Require review before closing.
- Add or update regression tests if a defect is confirmed.

Current CI failure handling:

- Failed scheduled regression runs generate
  `quarterly-regression-deviation.json` and
  `quarterly-regression-deviation.md` in the evidence directory.
- The generated deviation records run id, run URL, quarter, commit, evidence
  paths, impact statement, and required QA actions.
- The workflow opens a GitHub issue from the generated Markdown for scheduled
  regression failures.
- Human QA disposition is still required before routine-use impact can be
  closed.

## Change Control

Every behavior change must include:

- Requirement or risk reference.
- Test change.
- Metrology impact statement if calculation-related.
- Security/access-control impact statement if authorization-related.
- Audit/compliance impact statement if regulated workflow is affected.

No calculation logic change may be merged silently.
