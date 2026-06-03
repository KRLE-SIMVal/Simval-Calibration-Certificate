# P4 Implementation Log

Status: started.

P4 begins certificate rendering and export artifact generation after the P3 backend control gates were closed.

## Scope Implemented

- Deterministic minimal PDF renderer for certificate preview data.
- Renderer consumes `CertificatePreview` rows and does not recalculate result values.
- SIMVal-oriented PDF renderer structure with cover page, one result page per DUT
  group, and a reference-equipment page.
- Single-DUT and multi-DUT certificates are both supported by the renderer.
- Controlled certificate metadata model for certificate date, calibration date,
  receipt date, task number, purchase order, client, procedure, place, approval
  label, remarks, traceability statement, uncertainty statement, ambient
  conditions, temperature scale, and recorded-by evidence.
- SQLite certificate metadata repository with add-once storage and database-level
  update/delete blockers.
- Session-backed certificate metadata capture service with role resolution,
  metadata audit evidence, and draft-to-`metadata_complete` workflow transition.
- `POST /certificate-metadata` API endpoint for controlled metadata capture.
- Certificate preview now requires persisted metadata and DUT display details
  before preview audit evidence can be generated.
- Renderer uses locked preview metadata for page 1 and result-page
  remarks/conditions instead of P4 placeholder text.
- Rendered PDF artifact records artifact type, filename, content bytes, and SHA-256 checksum.
- Controlled local artifact storage writes rendered bytes once and returns `controlled-local://...` storage URI evidence.
- Artifact storage rejects filename path traversal and overwrite attempts.
- Rendered release service prechecks approved workflow state and matching preview audit evidence before rendering.
- Rendered release service stores generated artifact bytes and calls the existing certificate release gate with the generated checksum and storage URI.
- Rendered release blocks missing preview evidence, wrong workflow state, and unauthorized actors before writing artifact files.
- API settings require an explicit `SIMVAL_ARTIFACT_STORAGE_PATH` for
  controlled rendered artifact storage.
- `POST /certificate-rendered-releases` exposes the controlled PDF render,
  store, and release path through the session-backed API.

## Scope Not Implemented

- No exact SIMVal/DANAK visual certificate template matching yet.
- No image/logo embedding yet.
- No controlled metadata revision/edit workflow after initial capture yet.
- No reference-equipment table values in the renderer yet.
- No XLSX uncertainty-budget export yet.
- No PDF/A, digital signature, or qualified-signature support.
- No customer-facing UI.

## Compliance Notes

- This slice does not change calculation logic, CMC logic, rounding logic, uncertainty budgets, or reported result values.
- The renderer uses locked preview display values and version references.
- The renderer output is deterministic for the same preview and certificate number, giving stable checksum evidence.
- The current SIMVal-oriented renderer uses local reference files as design
  evidence only; raw reference files are classified as controlled internal
  confidential and are not default-CI fixtures.
- Artifact storage uses exclusive file creation to prevent overwriting released artifact bytes.
- The service blocks rendering before release prerequisites are met, reducing the risk of uncontrolled orphan artifact generation.

## Verification

- Focused certificate rendering, artifact storage, rendered release, release gate, and preview suite: 20 passed on Python 3.12.10.
- Default regression suite after P4 renderer/export slice: 285 passed, 2 skipped on Python 3.12.10.
- Focused SIMVal layout renderer, artifact storage, rendered release, release
  gate, and preview suite: 22 passed on Python 3.12.10.
- Focused controlled-reference manifest and certificate suite: 25 passed,
  2 skipped on Python 3.12.10.
- Default regression suite after SIMVal layout renderer slice: 287 passed,
  2 skipped on Python 3.12.10.
- Focused certificate metadata, preview, rendering, release, API, and schema
  suite: 43 passed on Python 3.12.10.
- Default regression suite after certificate metadata slice: 297 passed,
  2 skipped on Python 3.12.10.
- Focused certificate metadata capture, preview, rendering, release, API, and
  workflow suite: 54 passed on Python 3.12.10.
- Default regression suite after audited metadata capture slice: 303 passed,
  2 skipped on Python 3.12.10.
- Focused API rendered release, artifact storage, renderer, release, and
  runtime settings suite: 36 passed on Python 3.12.10.
- Default regression suite after API rendered release slice: 308 passed,
  2 skipped on Python 3.12.10.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| PDF output has SIMVal-oriented page structure but does not exactly match the approved certificate template. | Add exact template-contract tests, logo/DANAK mark handling, and visual/text extraction checks before treating output as customer-ready. |
| Certificate metadata is persisted through an audited initial capture path, but has no revision/edit workflow after initial capture. | Add a change-controlled metadata revision path before allowing post-capture changes. |
| Reference equipment is not yet available to the renderer. | Connect approved selected reference equipment to the preview model and block release when reference-equipment content is missing. |
| Many result rows on one DUT page may overflow. | Add deterministic page-break rules and tests for row limits before production validation. |
| Rendered release can leave an orphan artifact if file storage succeeds but the later database release transaction fails. | Add a pending/finalized artifact state or transactional artifact registry before production deployment. |
| No PDF/A or digital-signature support exists. | Decide signature/PDF archival requirements before final production validation. |
