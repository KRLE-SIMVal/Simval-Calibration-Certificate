# P45 Implementation Log - Automatic Pressure CSV Import

## Scope

P45 adds a controlled automatic pressure source-import path for a known paired
CSV schema. It covers automatic pressure jobs using retained source evidence
with columns `timestamp`, `reference`, `indication`, and optional `unit`.

This is not a generic mapping feature. Unknown CSV/XLSX layouts still require
manual controlled entry or a future approved mapping workflow.

## Changes

- Added `app/backend/imports/pressure_csv.py`.
- Added `app/backend/services/pressure_automatic_entry.py`.
- Added `POST /calibration-jobs/{job_id}/pressure-automatic-entry`.
- Added the automatic pressure entry action to the browser workflow contract.
- Updated import review so parser-event reading counts are visible when a
  parser records evidence outside the generic temperature parsed-reading table.
- Updated production runtime guidance for the known-schema pressure CSV import
  boundary.

## Controls

- Requires an authenticated user with `UPLOAD_IMPORT_FILE` permission.
- Requires a pressure job in automatic mode and `equipment_selected` state.
- Requires an uploaded `OTHER` `.csv` evidence file belonging to the same job.
- Reads only `controlled-local://` files under configured artifact storage.
- Requires at least two linked timezone-aware reference/DUT readings.
- Rejects missing required columns, invalid timestamps, invalid finite numeric
  values, NUL bytes, unit mismatches, wrong job discipline, wrong measurement
  mode, duplicate DUT/window setup, and missing artifact storage.
- Records parser result evidence on both the uploaded file and calibration job.
- Records `data_entry_recorded`, workflow transitions, source alignment, and
  `measurement_window_changed` audit evidence.
- Returns reference and indication value arrays for the existing automatic
  pressure calculation endpoint without changing calculation formulas.

## Validation

- Added parser tests for fixed schema parsing, warning/skipping invalid rows,
  missing required columns, timezone enforcement, and the two-reading minimum.
- Added service tests for successful import/audit evidence, manual-mode
  rejection, unauthorized rejection before writes, and unit mismatch rollback.
- Added API coverage for upload, automatic pressure entry, audit events, and
  import-review parser evidence.
- Updated workflow-contract tests to include the automatic pressure entry
  endpoint.

## Domain Impact

No pressure calculation, uncertainty, CMC, rounding, interpolation, release,
authentication, or role matrix logic changed. P45 only adds controlled source
parsing and data-entry evidence for automatic pressure workflows.

## Remaining Risk

Generic CSV/XLSX column mapping remains out of scope. Routine pressure
production release still requires approved pressure scope enablement,
pressure-template approval evidence, reviewer-independence evidence, live
authentication/TLS evidence, backup/restore evidence, retention approval, and
final human System Owner plus QA/Laboratory approval.
