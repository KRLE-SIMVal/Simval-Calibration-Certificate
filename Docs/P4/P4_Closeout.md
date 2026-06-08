# P4 Closeout

Status: complete for backend certificate rendering/export hardening.

## Closeout Decision

P4 is closed for the backend controls needed to render, store, release, revise,
and retrieve certificate artifacts with audit evidence.

P4 is not closed as a production/customer-ready certificate front end. Final
template validation, UI controls, signature/PDF archival policy, and production
validation remain for later phases.

## Implemented Controls

- Certificate PDF rendering consumes locked preview data and does not recalculate
  reported values.
- Single-DUT and multi-DUT certificates are supported by the renderer.
- Cover, result, and reference-equipment pages are generated deterministically.
- Certificate metadata is captured through an audited add-once service/API path.
- Selected reference equipment is captured as immutable audited snapshots.
- Reference-equipment suitability is checked at preview and release.
- SIMVal and DANAK/ILAC logo assets are embedded from controlled design assets.
- The DANAK/ILAC accreditation mark is controlled by a locked
  `accreditation_mark_allowed` preview/release decision.
- Rendered release requires approved workflow state and matching preview
  evidence.
- Rendered artifacts are stored with SHA-256 checksum and controlled storage URI
  evidence.
- Rendered artifacts are staged as pending files and finalized only after release
  persistence succeeds.
- Released-certificate revisions record immutable revision evidence and audit
  reason.
- Certificate history returns released certificate records, artifacts, and
  revision evidence for authorized sessions.
- Locked calculation-result XLSX uncertainty-budget artifacts can be generated.

## Deferred Items

- Exact approved SIMVal certificate template matching and visual regression
  checks.
- Customer-facing UI for certificate review, release, history, and accreditation
  mark scope.
- Replacement-certificate generation from a revised job.
- Full equipment-library CRUD workflow.
- Full uncertainty-budget editor/export workflow.
- PDF/A, digital signature, and qualified-signature support.
- Stale `.pending` artifact cleanup after process crash is deferred to P9
  production hardening.
- Final production validation package and SOP.

## Metrology Impact

No calculation logic, rounding logic, CMC logic, uncertainty calculation logic,
or reported certificate result values were changed in P4. The renderer and
release services consume previously locked preview values and preserve version
references for audit and review.

## Verification Plan

- Run focused unit suites after each implemented slice.
- Run full regression before each commit group and at P4 closeout.
- Push to `main` and confirm GitHub Actions passes for the final P4 commit.
- Keep controlled internal reference files out of default CI fixtures.

## Closeout Verification

- P4 closeout default regression suite: 342 passed, 2 skipped on Python 3.12.10.

## Residual Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| PDF output is backend-controlled but not visually validated against the final approved template. | Add template-contract tests, text extraction checks, and reviewed visual snapshots before customer-ready validation. |
| Accreditation mark scope is backend-controlled but not yet visible to reviewers in a UI. | Add a reviewer-visible UI decision control with approved SOP decision rules. |
| Released certificates can be revised, but a replacement certificate is not yet generated from the revised job. | Implement replacement-certificate generation before routine correction workflow use. |
| A crash could leave stale pending artifact files. | P9 adds controlled stale `.pending` cleanup with JSON evidence; deployment still needs a scheduled invocation once hosting is fixed. |
| PDF/A and signature requirements are undecided. | Decide archival/signature policy before final production validation. |
