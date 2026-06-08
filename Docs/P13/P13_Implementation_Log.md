# P13 Implementation Log

Status: started for certificate-number sequence controls.

P13 adds controlled internal certificate-number allocation as a backend/API
capability. It does not yet replace the explicit certificate number supplied to
certificate release requests.

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
- Added browser workflow contract entries and request samples for the new
  certificate-number endpoints.
- Added service and API regression tests for sequence creation, allocation,
  incrementing, audit evidence, and non-admin rejection before sequence changes.

## Scope Not Implemented

- Rendered certificate release still accepts an explicit certificate number.
- Automatic release-time allocation is deferred until SIMVal confirms whether
  D4 or the internal sequence is the master numbering source.
- Sequence retirement, prefix change control, and multi-prefix policy are not
  implemented yet.

## Compliance Notes

- Certificate-number allocation and audit evidence are committed together by
  the service.
- Non-admin allocation attempts are rejected before the sequence increments.
- Duplicate certificate numbers remain blocked by existing certificate-record
  persistence constraints.

## Verification

- Certificate-number focused API/service/persistence suite:
  51 passed on Python 3.12.10.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| Release does not automatically allocate from the internal sequence yet. | Decide whether D4 or the internal allocator is the production master; then wire rendered release to allocate or reserve numbers through the approved source. |
| Admin-only allocation may be too restrictive for routine QA release. | Keep it admin-only until the release-numbering policy is approved; then add a release-specific permission path with tests. |
