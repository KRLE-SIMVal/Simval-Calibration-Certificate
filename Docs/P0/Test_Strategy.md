# Test Strategy

## Test Policy

The project is tests-first.

No production behavior may be implemented unless its expected behavior is described in an automated test plan. When code exists, tests must be written before or with the code, and the relevant suite must pass before the change is considered complete.

Every future behavior change must add or update automated tests.

## Test Levels

| Level | Purpose |
|---|---|
| Unit tests | Pure functions, calculation rules, rounding, CMC lookup, permissions, state transitions. |
| Integration tests | API, persistence, audit events, import-to-calculation flow, certificate lifecycle. |
| Regression tests | Previously approved behavior and fixed defects. |
| Compliance tests | Required audit, approval, version locking, traceability, and evidence behavior. |
| Rendering tests | Certificate content, required fields, version references, artifact locking. |
| Security tests | Authentication, authorization, inactive users, access to sensitive records. |
| Scheduled tests | Full suite run quarterly even without code changes. |

## Required Test Categories

- Domain model tests.
- Role and permission tests.
- Calibration workflow state-transition tests.
- Temperature calculation tests.
- Pressure calculation tests.
- Uncertainty budget tests.
- Distribution and divisor tests.
- CMC floor and range lookup tests.
- Rounding and AB11 reporting tests.
- Certificate numbering and revision tests.
- Audit trail tests.
- Import/parser tests.
- Equipment traceability tests.
- Certificate rendering validation tests.
- Security/GDPR access tests.
- Regression tests for every fixed bug and changed behavior.

## Requirements Traceability

Every requirement must map to:

- One or more automated test IDs.
- Test level.
- Expected evidence.
- Review owner.
- Implementation status.

No requirement may enter implementation with missing test coverage unless the gap is explicitly approved and documented.

## Test Data Rules

Test data must be controlled.

Calculation test data must include:

- Inputs.
- Units.
- Assumptions.
- Intermediate expected values.
- Final expected values.
- Rounding expectations.
- Applicable CMC values.
- Source rationale.

No test may depend on uncontrolled external services.

## Quarterly Regression

The full automated regression suite must run on:

- January 1.
- April 1.
- July 1.
- October 1.

The run must execute even if no code has changed. If the scheduled day is not a working day, the automated run still executes and human review occurs on the next working day.

Quarterly evidence must retain:

- Timestamp.
- Commit/version tested.
- Test-suite version.
- Environment.
- Pass/fail result.
- Logs.
- Validation report.
- Reviewer disposition.

Any failure must create a tracked issue or deviation before routine use continues.

## Definition Of Test Done

A test is done when:

- It has a stable ID.
- It maps to one or more requirements or risks.
- It has deterministic expected results.
- It can run automatically.
- It produces retainable evidence.
- It is included in the relevant CI or scheduled suite.

