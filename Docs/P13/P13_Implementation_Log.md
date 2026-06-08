# P13 Implementation Log

Status: implemented for internal certificate-number sequence controls and
release-time allocation.

P13 adds controlled internal certificate-number allocation as a backend/API
capability. Explicit certificate-number release remains available for migration
and future D4 integration, while routine rendered PDF release can allocate the
next number from an approved internal sequence.

## Scope Implemented

- Added audited certificate-number service in
  `app/backend/services/certificate_numbers.py`.
- Added admin-only permission action `manage_certificate_numbers`.
- Added audit actions for certificate-number sequence creation and allocation.
- Updated the SQLite certificate-number allocator so allocation can participate
  in the same transaction as audit evidence.
- Added API endpoints:
  `POST /certificate-number-sequences` and
  `POST /certificate-number-allocations`.
- Added `POST /certificate-rendered-releases/allocated` to allocate the next
  internal sequence number, render the PDF, persist release evidence, and return
  certificate-number audit evidence in one controlled workflow.
- Added browser workflow contract entries and request samples for the new
  certificate-number endpoints and the allocated rendered-release endpoint.
- Added service and API regression tests for sequence creation, allocation,
  incrementing, release-time allocation, audit evidence, rollback before file
  write, and non-admin rejection before sequence changes.

## Scope Not Implemented

- D4 numbering integration remains deferred. The explicit release endpoint stays
  available as the future adapter path for externally supplied numbers.
- Sequence retirement, prefix change control, and multi-prefix policy are not
  implemented yet.

## Compliance Notes

- Certificate-number allocation and audit evidence are committed together by
  the service.
- Non-admin allocation attempts are rejected before the sequence increments.
- Release-time allocation is authorized by the existing certificate release
  permission. Sequence creation and standalone allocation remain admin-only.
- Release-time allocation, certificate release evidence, export artifact
  evidence, and the workflow transition share the same database transaction.
- If rendering or template-contract validation fails before release persistence,
  the allocated number rolls back and no pending/final PDF artifact is retained.
- Duplicate certificate numbers remain blocked by existing certificate-record
  persistence constraints.

## Verification

- Certificate-number, rendered-release, and API focused suite after
  release-time allocation:
  57 passed on Python 3.12.10.
- Default regression suite after release-time allocation:
  427 passed, 2 skipped on Python 3.12.10.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| D4 integration is deferred and internal numbering is the current operational master. | Keep the explicit release endpoint as the D4 adapter boundary and validate any future D4 import/reservation behavior before production switch-over. |
| Sequence retirement, prefix change control, and multi-prefix policy are not implemented yet. | Add controlled sequence status/change-control fields before SIMVal needs multiple numbering streams or prefix retirement. |
| PDF finalization still occurs after release persistence, matching the existing artifact-storage design. | Keep stale pending-file cleanup in the production readiness backlog and monitor readiness evidence for artifact storage health. |
