# P17 Implementation Log

Status: implemented for reviewer-independence backend enforcement.

P17 closes the implementation gap where reviewer independence was documented as
required but not technically enforced.

## Scope Implemented

- Added a backend reviewer-independence service that reads retained
  calibration-job audit evidence.
- Technical review approval is blocked if the same user already prepared or
  calculated the job, or submitted it into technical review.
- QA release approval is blocked if the same user prepared/calculated the job,
  submitted it to technical review, or approved technical review.
- Certificate release is blocked if the same user prepared/calculated the job,
  submitted or approved review, or approved QA release.
- Existing UI/API workflows now require separate users in end-to-end regression
  tests for operator, technical reviewer, QA approver, and releaser duties.

## Compliance Notes

- The control is enforced in backend services and does not rely on UI behavior.
- The control uses existing audit events and therefore works for Entra-issued
  sessions and local setup sessions alike.
- No calculation, uncertainty, CMC, rounding, certificate rendering, or token
  validation logic was changed.

## Verification

- Focused reviewer-independence, review workflow, certificate release, API
  upload workflow, and API application suite:
  76 passed on Python 3.12.10.
- Focused reviewer-independence and documentation suite:
  37 passed on Python 3.12.10.
- Full repository regression suite: 465 passed, 2 skipped on Python 3.12.10.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| Production users still need live role assignment and access-review evidence. | Before go-live, create/verify separate Entra-backed local users for operator, technical reviewer, QA approver, and release actor duties. |
| Same-person work could be required during exceptional staffing constraints. | Treat that as a controlled deviation requiring documented approval before certificate release. |
| Live end-to-end production authentication plus reviewer-independence evidence has not been retained yet. | Run the go-live workflow using real SIMVal accounts and retain the validation package evidence. |
