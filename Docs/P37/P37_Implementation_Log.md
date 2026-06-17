# P37 Implementation Log - Manual Pressure Calculation API

## Scope

Added a controlled manual pressure calculation API backed by the existing
pressure calculation engine.

## Changes

- Added `POST /pressure/manual-calculations`.
- Added request/response models for manual gauge, absolute, and differential
  pressure calculation inputs supported by the existing pressure engine.
- The endpoint authenticates and authorizes `RUN_CALCULATION` before validating
  calculation-specific pressure inputs.
- The endpoint records a `calculation_run` audit event with software,
  calculation-engine, constant-set, and budget versions.
- The browser workflow contract now lists `/pressure/manual-calculations` with
  a sample manual gauge pressure payload.

## Validation

- Added API tests for successful manual gauge pressure calculation, audit-event
  creation, unauthorized role rejection before audit, and invalid gauge
  pressure barometer input rejection without audit.
- Existing pressure engine tests continue to cover manual gauge, manual
  absolute, automatic pressure, CMC floor, additional uncertainty terms, and
  invalid input cases.

## Domain Impact

This exposes already-tested pressure calculation logic through an authenticated
and audited API boundary. It does not enable pressure certificate release,
pressure import workflow, pressure equipment library controls, or pressure PDF
output.

## Remaining Risk

Later pressure milestones add persisted pressure workflow, controlled pressure
entry/import paths, pressure certificate preview/rendering, and pressure
template approval evidence. Routine production pressure use still requires the
enabled pressure scope to pass the current production readiness and human
QA/Laboratory approval gates.
