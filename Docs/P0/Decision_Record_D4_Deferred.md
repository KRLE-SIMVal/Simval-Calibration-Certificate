# Decision Record: D4 Deferred

## Decision

D4 integration is deferred for the first implementation phases.

The application may initially manage certificate numbers, equipment records, due dates, and reference metadata internally.

## Reason

D4 separation is acceptable for now because it is not critical to building, testing, validating, and using the core SIMVal programme.

The first priority is a controlled, testable, validated application with:

- Explicit domain model.
- Roles and permissions.
- Calibration workflow.
- Calculation engine.
- Certificate generation.
- Audit trail.
- Automated regression testing.

## Architectural Constraint

Internal certificate numbering and equipment records must be designed behind service boundaries so D4 can be added later without rewriting core domain logic.

Required future adapter boundary:

```text
CertificateNumberProvider
EquipmentSource
ReferenceCalibrationSource
```

## Test Impact

Initial tests must cover internal behavior:

- Internal certificate number allocation.
- Duplicate number prevention.
- Equipment due-date validation.
- Reference equipment status validation.

Future D4 integration tests must be added before D4 code is implemented.

## Compliance Impact

Deferring D4 does not defer traceability.

The application must still store and audit:

- Certificate number source.
- Equipment identifier.
- Equipment calibration status.
- Calibration certificate reference.
- Due date.
- Selected reference equipment used for each certificate.

