# P4 Implementation Log

Status: completed for backend certificate rendering/export hardening.

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
- Certificate PDF cover page embeds the controlled SIMVal logo and supplied
  DANAK/ILAC CAL Reg.nr. 647 accreditation mark when the controlled PNG assets
  are present.
- Logo placement keeps the SIMVal logo larger than the DANAK/ILAC mark in line
  with the SIMVal design requirement and DANAK AB02 prominence constraint.
- Certificate preview and release paths now carry an explicit
  `accreditation_mark_allowed` decision in preview/release audit evidence and
  API responses.
- Rendered release rejects preview/release accreditation-scope mismatches and
  suppresses the DANAK/ILAC mark when the approved scope decision disallows it.
- Controlled released-certificate revision service records immutable revision
  evidence, audit reason, and `released` to `revised` workflow transition.
- `POST /certificate-revisions` exposes the controlled revision path through
  the session-backed API.
- Session-backed certificate history service returns released certificate
  records, artifact checksum/storage URI evidence, and linked revision evidence.
- `GET /certificate-history/{job_id}` exposes certificate history retrieval
  through the API for authorized sessions.
- Rendered PDF release now writes a pending artifact file first, finalizes the
  final artifact only after release persistence succeeds, and discards pending
  bytes if release persistence fails.

## Deferred / Not Implemented In P4

- Exact SIMVal/DANAK visual certificate template matching and visual regression
  checks are not complete.
- Metadata mutation in place after initial capture is intentionally not
  implemented; released certificates now use controlled revision evidence
  instead.
- Replacement-certificate generation from a revised job is not complete.
- Full equipment-library CRUD is not complete. P4 implements immutable selected
  reference-equipment snapshots and suitability gates only.
- Full uncertainty-budget editor/export is not complete. P4 implements locked
  calculation-result XLSX rendering only.
- PDF/A, digital signature, and qualified-signature support remain policy and
  tooling decisions.
- Customer-facing UI is not implemented.
- Final customer-facing UI control for the accreditation-scope decision is not
  implemented.
- Stale `.pending` artifact cleanup after process crash is not implemented.

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
- The supplied DANAK file is a combined ILAC/DANAK mark. This slice embeds the
  supplied asset only when the preview/release accreditation scope allows it;
  the business decision remains subject to approved SIMVal/DANAK scope
  controls.
- P4 closes the backend export, release evidence, history, revision, logo, and
  artifact integrity controls. It does not claim customer-ready visual template
  validation or final production validation.

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
- Focused certificate renderer logo asset suite: 8 passed on Python 3.12.10.
- Focused certificate rendering, artifact storage, preview, release, rendered
  release, and API suite after logo embedding: 51 passed on Python 3.12.10.
- Default regression suite after certificate logo embedding: 328 passed,
  2 skipped on Python 3.12.10.
- Focused certificate rendering, preview, release, rendered release, and API
  suite after accreditation-scope control: 52 passed on Python 3.12.10.
- Default regression suite after accreditation-scope control: 331 passed,
  2 skipped on Python 3.12.10.
- Focused certificate revision service and API suite: 22 passed on Python
  3.12.10.
- Focused certificate, API, and certificate persistence suite after revision
  workflow: 97 passed on Python 3.12.10.
- Default regression suite after released-certificate revision workflow:
  336 passed, 2 skipped on Python 3.12.10.
- Focused certificate history, revision, and API suite: 25 passed on Python
  3.12.10.
- Focused certificate, API, and certificate persistence suite after history
  retrieval: 100 passed on Python 3.12.10.
- Default regression suite after certificate history retrieval: 339 passed,
  2 skipped on Python 3.12.10.
- Focused certificate artifact storage and rendered release suite after staged
  artifact finalization: 11 passed on Python 3.12.10.
- Focused certificate, API, and certificate persistence suite after staged
  artifact finalization: 103 passed on Python 3.12.10.
- Default regression suite after staged artifact finalization: 342 passed,
  2 skipped on Python 3.12.10.
- P4 closeout default regression suite: 342 passed, 2 skipped on Python 3.12.10.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| PDF output has SIMVal-oriented page structure and controlled logos, but does not exactly match the approved certificate template. | Add exact template-contract tests and visual/text extraction checks before treating output as customer-ready. |
| The supplied accreditation mark now has backend/API scope control, but no customer-facing UI control exists yet. | Add a reviewer-visible UI control and QMS-approved decision rule before production validation. |
| Certificate metadata is persisted through an audited initial capture path and cannot be mutated in place; released certificate correction now requires revision evidence, but replacement-certificate generation is still a future workflow slice. | Add replacement-certificate generation from a revised job before production use of correction workflows. |
| Reference-equipment selection is audited and point-level suitability is checked at preview/release, but full equipment-library CRUD is not yet implemented. | Add controlled equipment-library management before production workflow validation. |
| XLSX uncertainty-budget rendering covers locked automatic temperature calculation output, not a full editable budget-editor export. | Add controlled budget-editor export once the budget module is implemented and approved. |
| Rendered release now prevents final orphan artifacts when release persistence fails by using pending/final artifact finalization. Pending-file cleanup after process crashes is still an operational concern. | Add a startup/admin cleanup task for stale `.pending` files before production deployment. |
| No PDF/A or digital-signature support exists. | Decide signature/PDF archival requirements before final production validation. |
