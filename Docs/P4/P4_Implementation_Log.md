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
- Immutable selected reference-equipment snapshots can be persisted for a job
  with selector/timestamp evidence and database-level update/delete blockers.
- Certificate preview generation now requires selected reference equipment,
  records reference-equipment ids in preview audit evidence, and exposes
  reference-equipment rows in the API preview response.
- The renderer populates the reference-equipment page from locked preview
  equipment snapshots.
- The renderer deterministically splits large DUT result tables across multiple
  result pages before the reference-equipment page.
- Session-backed reference-equipment selection service stores immutable
  selected-equipment evidence, records explicit selection audit evidence, and
  transitions `metadata_complete` jobs to `equipment_selected`.
- `POST /reference-equipment-selections` exposes the controlled selection path
  through the API.
- Deterministic dependency-free XLSX uncertainty-budget artifact renderer for
  locked automatic temperature calculation outputs.
- Certificate preview and release gates run selected reference-equipment
  suitability checks against calculated point reference value, unit, job
  discipline, and certificate calibration date before audit/release evidence is
  written.

## Scope Not Implemented

- No exact SIMVal/DANAK visual certificate template matching yet.
- No image/logo embedding yet.
- No controlled metadata revision/edit workflow after initial capture yet.
- No full equipment-library CRUD workflow yet.
- No full uncertainty-budget editor/export workflow beyond locked calculation
  result XLSX rendering yet.
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
- Reference-equipment suitability checks use certificate calibration date as the
  equipment use date and the locked calculation summary reference value/unit as
  the checked measurement point.

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
- Focused selected reference-equipment domain, persistence, preview, renderer,
  release, API, and schema suite: 60 passed on Python 3.12.10.
- Default regression suite after selected reference-equipment certificate slice:
  314 passed, 2 skipped on Python 3.12.10.
- Focused audited reference-equipment selection, preview, renderer, release,
  API, permissions, and schema suite: 71 passed on Python 3.12.10.
- Default regression suite after audited reference-equipment selection slice:
  320 passed, 2 skipped on Python 3.12.10.
- Focused renderer pagination, rendered release, and API suite: 27 passed on
  Python 3.12.10.
- Default regression suite after renderer pagination slice: 321 passed,
  2 skipped on Python 3.12.10.
- Focused uncertainty-budget XLSX export, calculation, artifact, and record
  suite: 21 passed on Python 3.12.10.
- Default regression suite after uncertainty-budget XLSX export slice:
  323 passed, 2 skipped on Python 3.12.10.
- Focused reference-equipment suitability gate, domain, persistence, preview,
  release, rendered release, API, and workflow suite: 60 passed on Python
  3.12.10.
- Default regression suite after reference-equipment suitability gate slice:
  326 passed, 2 skipped on Python 3.12.10.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| PDF output has SIMVal-oriented page structure but does not exactly match the approved certificate template. | Add exact template-contract tests, logo/DANAK mark handling, and visual/text extraction checks before treating output as customer-ready. |
| Certificate metadata is persisted through an audited initial capture path, but has no revision/edit workflow after initial capture. | Add a change-controlled metadata revision path before allowing post-capture changes. |
| Reference-equipment selection is audited and point-level suitability is checked at preview/release, but full equipment-library CRUD is not yet implemented. | Add controlled equipment-library management before production workflow validation. |
| XLSX uncertainty-budget rendering covers locked automatic temperature calculation output, not a full editable budget-editor export. | Add controlled budget-editor export once the budget module is implemented and approved. |
| Rendered release can leave an orphan artifact if file storage succeeds but the later database release transaction fails. | Add a pending/finalized artifact state or transactional artifact registry before production deployment. |
| No PDF/A or digital-signature support exists. | Decide signature/PDF archival requirements before final production validation. |
