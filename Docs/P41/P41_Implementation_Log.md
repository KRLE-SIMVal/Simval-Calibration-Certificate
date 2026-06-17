# P41 Implementation Log - Manual Pressure Entry And Release Path

## Scope

P41 adds a controlled manual pressure entry path and validates that a manual
pressure job can move through calculation, review, preview, and PDF release
using persisted pressure summaries.

## Changes

- Added `app/backend/services/pressure_manual_entry.py`.
- Added `POST /calibration-jobs/{job_id}/pressure-manual-entry`.
- Manual pressure entry now requires:
  - authenticated `ENTER_MANUAL_READINGS` permission,
  - a pressure job in `equipment_selected` state,
  - an uploaded raw evidence file belonging to the same job,
  - one controlled DUT identity,
  - one selected pressure measurement window,
  - timestamped readings with source label and optional row/column traceability.
- The service records:
  - `data_entry_recorded` audit evidence,
  - transition to `data_entered`,
  - `manual_reading_changed` audit evidence,
  - `measurement_window_changed` audit evidence,
  - transition to `windows_selected`.
- Added the manual pressure entry action and sample payload to the browser
  workflow contract.
- Added an end-to-end API test proving a manual pressure certificate path can
  be created, calculated, reviewed, previewed, rendered, and released when
  pressure is explicitly enabled.

## Validation

- Added service tests for successful manual pressure entry, unauthorized
  rejection before writes, pressure-discipline enforcement, and uploaded
  evidence traceability.
- Added API tests for successful manual pressure entry and unauthorized
  rejection before writes.
- Added end-to-end pressure workflow coverage through PDF release.

## Domain Impact

No pressure calculation formulas changed. P41 adds controlled transcription and
workflow evidence for manual pressure readings from retained source evidence.

## Remaining Risk

P45 later adds known-schema automatic pressure CSV import for paired
reference/DUT source files. Unknown CSV/XLSX column mapping remains outside the
P41/P45 boundary and requires controlled manual entry or a future approved
mapping workflow.
Pressure-specific PDF wording/template review remains required before claiming
full DANAK-ready pressure certificate production release.
