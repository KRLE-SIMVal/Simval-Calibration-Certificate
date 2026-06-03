# P4 Implementation Log

Status: started.

P4 begins certificate rendering and export artifact generation after the P3 backend control gates were closed.

## Scope Implemented

- Deterministic minimal PDF renderer for certificate preview data.
- Renderer consumes `CertificatePreview` rows and does not recalculate result values.
- SIMVal-oriented PDF renderer structure with cover page, one result page per DUT
  group, and a reference-equipment page.
- Single-DUT and multi-DUT certificates are both supported by the renderer.
- Rendered PDF artifact records artifact type, filename, content bytes, and SHA-256 checksum.
- Controlled local artifact storage writes rendered bytes once and returns `controlled-local://...` storage URI evidence.
- Artifact storage rejects filename path traversal and overwrite attempts.
- Rendered release service prechecks approved workflow state and matching preview audit evidence before rendering.
- Rendered release service stores generated artifact bytes and calls the existing certificate release gate with the generated checksum and storage URI.
- Rendered release blocks missing preview evidence, wrong workflow state, and unauthorized actors before writing artifact files.

## Scope Not Implemented

- No exact SIMVal/DANAK visual certificate template matching yet.
- No image/logo embedding yet.
- No persisted certificate metadata model for client, purchase order, procedure,
  remarks, conditions, dates, or reference-equipment table values yet.
- No XLSX uncertainty-budget export yet.
- No API endpoint for rendered release yet.
- No configurable artifact storage path in API settings yet.
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

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| PDF output has SIMVal-oriented page structure but does not exactly match the approved certificate template. | Add exact template-contract tests, logo/DANAK mark handling, and visual/text extraction checks before treating output as customer-ready. |
| Certificate metadata is not yet persisted into the preview/release model. | Add a versioned certificate metadata model before finalizing page 1 and remarks/conditions content. |
| Reference equipment is not yet available to the renderer. | Connect approved selected reference equipment to the preview model and block release when reference-equipment content is missing. |
| Many result rows on one DUT page may overflow. | Add deterministic page-break rules and tests for row limits before production validation. |
| Local artifact storage path is not yet configurable through API settings. | Add `SIMVAL_ARTIFACT_STORAGE_PATH` and an API rendered-release endpoint after renderer/storage behavior is validated. |
| Rendered release can leave an orphan artifact if file storage succeeds but the later database release transaction fails. | Add a pending/finalized artifact state or transactional artifact registry before production deployment. |
| No PDF/A or digital-signature support exists. | Decide signature/PDF archival requirements before final production validation. |
