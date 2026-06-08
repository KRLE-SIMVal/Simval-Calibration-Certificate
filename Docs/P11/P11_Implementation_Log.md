# P11 Implementation Log

Status: started.

P11 covers the production user workflow that was missing from the browser shell:
job creation, source-file upload, import review, calculation execution, and
certificate generation from the UI.

## Scope Implemented

- Added authenticated calibration job creation service and API endpoint:
  `POST /calibration-jobs`.
- Added controlled source-file upload service and API endpoint:
  `POST /calibration-jobs/{job_id}/files`.
- Added visible browser controls for creating a job and uploading a source file.
- Uploaded bytes are stored unchanged under controlled local artifact storage.
- Upload evidence includes SHA-256 checksum, storage URI, file kind, byte count,
  user, timestamp, and audit event ID.
- Calibration XLSX uploads run the existing ValProbe workbook parser and return
  parser status, reading count, warning count, and parser audit event ID.
- Verification PDF uploads are stored as raw evidence. PDF text extraction
  remains explicitly deferred.
- Added import review service and API endpoint:
  `GET /calibration-jobs/{job_id}/imports`.
- Added browser `Review Imports` action that returns uploaded-file and parser
  evidence for the current job.
- Added temperature data-entry preparation service and API endpoint:
  `POST /calibration-jobs/{job_id}/temperature-data-entry`.
- Added browser `Prepare Data` action that creates DUT/channel records and a
  required setpoint plan from parsed calibration workbook evidence.
- Temperature data entry is blocked unless the job is in `equipment_selected`,
  preserving the approved workflow order.
- Added manual verification IRTD transcription service and API endpoint:
  `POST /calibration-jobs/{job_id}/verification-irtd-rows`.
- Added browser `Record IRTD` action for controlled pasted IRTD table rows
  tied to the uploaded verification PDF evidence.
- Manual IRTD transcription stores parsed reference readings, linked
  logger/reference readings, and explicit audit evidence.
- Added temperature-window selection and completion API endpoints:
  `POST /calibration-jobs/{job_id}/temperature-windows` and
  `POST /calibration-jobs/{job_id}/temperature-windows/complete`.
- Added browser `Select Window` and `Complete Windows` actions for moving from
  linked readings to `windows_selected` through the controlled workflow.
- Added temperature calculation API endpoint:
  `POST /calibration-jobs/{job_id}/temperature-calculations`.
- Added browser `Calculate` action that submits explicit uncertainty inputs and
  governed version identifiers for the existing temperature calculation engine.
- Added review transition API endpoints:
  `POST /calibration-jobs/{job_id}/technical-review-submissions`,
  `POST /calibration-jobs/{job_id}/technical-review-approvals`, and
  `POST /calibration-jobs/{job_id}/qa-release-approvals`.
- Added browser review buttons for moving calculated jobs through technical
  review, QA review, and approved state before certificate release.
- Added direct browser shortcut buttons for certificate metadata capture,
  reference equipment selection, certificate preview generation, and rendered
  PDF certificate release.
- Added approved governed-version API endpoints:
  `POST /constant-sets/approved` and
  `POST /uncertainty-budgets/approved`.
- Added browser shortcuts for approving the default constant-set and uncertainty
  budget version records needed by the calculation gate.
- Strengthened the API regression workflow so the temperature certificate path
  proceeds through public endpoints from metadata capture and reference
  selection through rendered PDF release, without direct test-side workflow state
  mutation or direct governed-version repository seeding.
- Added end-to-end API regression coverage for one released rendered PDF
  certificate containing multiple DUT/channel results.

## Scope Not Implemented

- Automated multi-file linked XLSX/PDF import orchestration from the browser is
  not yet complete.
- Verification PDF text extraction remains deferred until a PDF dependency and
  validation approach are approved.
- Production authentication provider remains pending.

## Compliance Notes

- This slice does not change calculation logic, CMC rules, uncertainty budgets,
  certificate rendering, or reported values.
- Source files are stored with checksum and uploaded-file evidence before parser
  status is returned.
- Parser failure for calibration XLSX preserves raw uploaded-file evidence and
  records parser status instead of silently accepting data.
- Authorization uses the existing `UPLOAD_IMPORT_FILE` and
  `CREATE_CALIBRATION_JOB` permission checks.
- Manual IRTD transcription uses the existing `ENTER_MANUAL_READINGS`
  permission and does not claim automated PDF extraction.
- Temperature-window selection uses existing linked-reading service checks for
  DUT/channel match, timestamp range, units, state, and coverage completion.
- Calculation execution uses the existing temperature calculation service and
  still requires approved constant and uncertainty budget versions.
- This slice does not change formulas, rounding, uncertainty combination, CMC
  floors, or displayed result formatting.
- Review transitions use existing regulated permission actions and append
  workflow audit evidence for each state change.
- Approved governed-version endpoints use the authenticated actor as approval
  evidence and append constant/budget audit events.

## Verification

- Focused upload/API workflow suite:
  30 passed on Python 3.12.10.
- Import review focused suite:
  32 passed on Python 3.12.10.
- Temperature data-entry focused suite:
  35 passed on Python 3.12.10.
- Manual IRTD transcription focused suite:
  37 passed on Python 3.12.10.
- Temperature-window API focused suite:
  38 passed on Python 3.12.10.
- Temperature calculation API focused suite:
  38 passed on Python 3.12.10.
- Review workflow API focused suite:
  38 passed on Python 3.12.10.
- Browser certificate shortcut focused suite:
  25 passed on Python 3.12.10.
- Governed-version API focused suite:
  26 passed on Python 3.12.10.
- End-to-end API workflow focused suite:
  39 passed on Python 3.12.10.
- Multi-DUT certificate API workflow focused suite:
  14 passed on Python 3.12.10.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| Verification PDF extraction is not implemented. | Use controlled manual IRTD transcription tied to raw PDF evidence now, then add approved PDF extraction with controlled fixtures and parser tests before relying on automatic IRTD extraction from uploaded PDFs. |
| Upload endpoint uses raw request bytes rather than multipart form upload. | Keep this dependency-free path for now; move to multipart only if the production UI needs metadata and files submitted in one form. |
| DUT identity is currently derived from logger channel IDs. | Keep this as a traceable default for ValProbe imports, then add an editable mapping screen before production release if customer-facing DUT serial numbers differ from logger channel IDs. |
| Reviewer independence is not technically enforced by separate user IDs yet. | Keep permission-gated review transitions now, then add independence checks before production release when the production user model and SOP approval responsibilities are finalized. |
