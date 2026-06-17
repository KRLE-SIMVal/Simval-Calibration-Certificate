# P44 Implementation Log - Pressure Template Approval Evidence

## Scope

P44 converts the remaining pressure certificate wording/layout approval blocker
into controlled validation evidence. It does not approve pressure production use
by itself; it creates a repeatable, sanitized evidence record from a
SIMVal-controlled approval JSON.

## Changes

- Added `app.backend.validation.pressure_template_approval`.
- Added `scripts/validation/generate_pressure_template_approval_evidence.py`.
- The generated evidence records:
  - pressure template version match,
  - pressure discipline confirmation,
  - reviewed rendered certificate artifact SHA-256 reference,
  - certificate artifact review status,
  - method-specific pressure statement review status,
  - DANAK mark/scope review status,
  - AB11 reporting review status,
  - QA/Laboratory Reviewer and Laboratory Chief approval decisions with hashed
    actor identifiers.
- The CLI returns exit code `0` only when all approval controls pass.
- The CLI returns exit code `2` while blockers remain.
- Updated production runtime guidance for the pressure-template approval record.

## Compliance Notes

- DANAK AB2 requires accredited certificate marking and accreditation claims not
  to mislead about what the accredited scope covers.
- DANAK AB11 requires calibration certificate result reporting with units and
  expanded uncertainty context. This evidence confirms human review of the
  pressure certificate wording/layout against that reporting expectation.

## Validation

- Unit tests cover passed evidence, missing approval roles, incomplete review
  flags, template-version mismatch, discipline mismatch, missing artifact
  reference, invalid JSON, timezone-aware timestamps, CLI output, exit code `0`,
  and exit code `2`.

## Domain Impact

No calculation, uncertainty, CMC, rounding, interpolation, release, audit
immutability, parser, authentication, or authorization logic changed.

## Remaining Risk

P45 later adds known-schema automatic pressure CSV import for paired
reference/DUT source files. Routine pressure certificate production release
still requires retained pressure-template approval evidence and controlled
go-live approval for the enabled pressure scope.
