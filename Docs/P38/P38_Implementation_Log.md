# P38 Implementation Log - Automatic Pressure Calculation API

## Scope

P38 exposes the existing automatic pressure point calculation engine through the
controlled backend API. This is a calculation evidence endpoint only.

## Changes

- Added `POST /pressure/automatic-calculations`.
- Reused the shared pressure uncertainty request fields used by the manual
  pressure calculation API.
- Preserved the existing pressure engine as the single calculation source for
  paired reference and DUT readings.
- Required `RUN_CALCULATION` authorization before automatic pressure input
  validation.
- Recorded `calculation_run` audit evidence with `calculation_type` set to
  `automatic`, version references, pressure kind, summary values, CMC floor
  status, and uncertainty contributions.
- Added the automatic pressure calculation action and sample request to the
  browser workflow contract.

## Validation

- Added API tests for successful automatic pressure calculation response and
  audit event creation.
- Added API tests proving unauthorized users are rejected before calculation
  validation and before audit writes.
- Added API tests for unpaired automatic pressure readings.
- Existing pressure engine tests remain the validation source for the
  metrology calculation behavior.

## Domain Impact

The calculation logic is unchanged. P38 only adds an authenticated and audited
API boundary for automatic pressure calculations already covered by the pressure
engine tests.

## Remaining Risk

Later pressure milestones add persisted pressure workflow, controlled pressure
entry/import paths, pressure certificate preview/rendering, and pressure
template approval evidence. Routine production pressure use still requires the
enabled pressure scope to pass the current production readiness and human
QA/Laboratory approval gates.
