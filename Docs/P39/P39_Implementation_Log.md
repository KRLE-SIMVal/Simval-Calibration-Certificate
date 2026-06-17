# P39 Implementation Log - Persisted Pressure Calculation Workflow

## Scope

P39 connects pressure point calculations to the regulated calibration-job
workflow. It does not change pressure calculation formulas.

## Changes

- Added `app/backend/services/pressure_calculations.py`.
- Added `POST /calibration-jobs/{job_id}/pressure-calculations`.
- Persisted pressure calculation summaries in `measurement_point_summaries`.
- Required pressure jobs to be in `windows_selected` state before calculation.
- Required the job discipline to be `pressure`.
- Required the job measurement mode to match submitted manual or automatic
  pressure points.
- Required approved pressure constant and uncertainty-budget versions before
  calculation.
- Required each pressure point to reference an existing DUT and selected
  measurement window belonging to the same job.
- Appended `calculation_run` audit evidence to the calibration job with
  pressure kind, calculation type, summary values, CMC status, version refs, and
  uncertainty contributions.
- Transitioned successful pressure jobs to `calculated`.
- Added the persisted pressure job calculation action and sample request to the
  browser workflow contract.

## Validation

- Added service tests for successful manual pressure persistence, successful
  session-authenticated automatic pressure calculation, unauthorized rejection,
  discipline mismatch, mode mismatch, missing approved versions, and missing
  selected measurement-window evidence.
- Added API tests for successful persisted pressure calculation and
  authorization-before-validation behavior.

## Domain Impact

The metrology calculation logic is unchanged. P39 only adds regulated workflow
orchestration around the existing pressure calculation engine: traceability
checks, approved-version checks, summary persistence, audit evidence, and job
state transition.

## Remaining Risk

Later pressure milestones add controlled manual pressure entry, known-schema
automatic pressure CSV import, pressure certificate preview/rendering, and
pressure template approval evidence. Routine production pressure use still
requires the enabled pressure scope to pass the current production readiness and
human QA/Laboratory approval gates.
