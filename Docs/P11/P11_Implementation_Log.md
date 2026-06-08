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

## Scope Not Implemented

- Multi-file linked XLSX/PDF import orchestration from the browser is not yet
  complete.
- Verification PDF text extraction remains deferred until a PDF dependency and
  validation approach are approved.
- Import review, logger/channel mapping, measurement-window selection, and
  calculation execution are not yet exposed as technician-friendly screens.
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

## Verification

- Focused upload/API workflow suite:
  30 passed on Python 3.12.10.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| Verification PDF extraction is not implemented. | Keep raw verification PDF upload available now, then add approved PDF extraction with controlled fixtures and parser tests before relying on automatic IRTD extraction from uploaded PDFs. |
| Browser workflow still lacks import review and measurement-window selection. | Continue P11 with import review tables, channel summaries, window selection, and calculation execution as separate tested slices. |
| Upload endpoint uses raw request bytes rather than multipart form upload. | Keep this dependency-free path for now; move to multipart only if the production UI needs metadata and files submitted in one form. |
