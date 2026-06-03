# P4 Implementation Log

Status: started.

P4 begins certificate rendering and export artifact generation after the P3 backend control gates were closed.

## Scope Implemented

- Deterministic minimal PDF renderer for certificate preview data.
- Renderer consumes `CertificatePreview` rows and does not recalculate result values.
- Rendered PDF artifact records artifact type, filename, content bytes, and SHA-256 checksum.
- Controlled local artifact storage writes rendered bytes once and returns `controlled-local://...` storage URI evidence.
- Artifact storage rejects filename path traversal and overwrite attempts.
- Rendered release service prechecks approved workflow state and matching preview audit evidence before rendering.
- Rendered release service stores generated artifact bytes and calls the existing certificate release gate with the generated checksum and storage URI.
- Rendered release blocks missing preview evidence, wrong workflow state, and unauthorized actors before writing artifact files.

## Scope Not Implemented

- No final SIMVal/DANAK visual certificate template matching yet.
- No image/logo embedding yet.
- No XLSX uncertainty-budget export yet.
- No API endpoint for rendered release yet.
- No configurable artifact storage path in API settings yet.
- No PDF/A, digital signature, or qualified-signature support.
- No customer-facing UI.

## Compliance Notes

- This slice does not change calculation logic, CMC logic, rounding logic, uncertainty budgets, or reported result values.
- The renderer uses locked preview display values and version references.
- The renderer output is deterministic for the same preview and certificate number, giving stable checksum evidence.
- Artifact storage uses exclusive file creation to prevent overwriting released artifact bytes.
- The service blocks rendering before release prerequisites are met, reducing the risk of uncontrolled orphan artifact generation.

## Verification

- Focused certificate rendering, artifact storage, rendered release, release gate, and preview suite: 20 passed on Python 3.12.10.
- Default regression suite after P4 renderer/export slice: 285 passed, 2 skipped on Python 3.12.10.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| Minimal PDF output does not visually match the approved certificate template. | Add template-contract tests and visual/text extraction checks before treating output as customer-ready. |
| Local artifact storage path is not yet configurable through API settings. | Add `SIMVAL_ARTIFACT_STORAGE_PATH` and an API rendered-release endpoint after renderer/storage behavior is validated. |
| Rendered release can leave an orphan artifact if file storage succeeds but the later database release transaction fails. | Add a pending/finalized artifact state or transactional artifact registry before production deployment. |
| No PDF/A or digital-signature support exists. | Decide signature/PDF archival requirements before final production validation. |
