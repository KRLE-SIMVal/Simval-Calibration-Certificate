# P5 Implementation Log

Status: completed for validation evidence and scheduled regression controls.

P5 begins production-readiness hardening after P4 backend certificate
rendering/export controls were closed.

## Scope Implemented

- Validation evidence reports now classify each run as local, change, manual,
  scheduled, or quarterly regression.
- Reports record trigger event, quarter, CI run metadata, platform metadata,
  Python implementation/version, evidence paths, and controlled-fixture policy.
- The validation report CLI accepts GitHub Actions metadata and controlled
  fixture enablement explicitly.
- GitHub Actions now selects `Docs/Validation/evidence/<year>/Q<n>/` for
  scheduled quarterly runs and `Docs/Validation/evidence/latest` for push/manual
  runs.
- GitHub Actions uploads the validation evidence directory as a retained
  workflow artifact named for the run id.
- Failed scheduled regression runs now generate JSON and Markdown deviation
  evidence in the validation evidence directory.
- Failed scheduled regression runs now open a GitHub issue from the generated
  deviation Markdown.
- P25 hardening later restricted the normal CI test job to `contents: read` and
  moved `issues: write` to a separate scheduled-failure issue job that consumes
  the retained validation evidence artifact.
- P25 hardening also pinned third-party GitHub Actions to immutable commit SHAs
  while keeping the original major tag in comments for controlled update review.

## Scope Not Implemented

- Human reviewer approval is not automated and remains required.
- Controlled confidential fixture execution remains opt-in only through
  `SIMVAL_RUN_CONTROLLED_FIXTURE_TESTS=1`.
- Full equipment-library CRUD remains deferred. The equipment library will be
  populated manually once the program is production ready.

## Compliance Notes

- This slice does not change calculation logic, certificate rendering logic,
  workflow state logic, or reported values.
- Controlled internal reference files remain excluded from default CI.
- Scheduled regression evidence is now easier to retain and review because the
  report records the tested commit, run trigger, quarter, environment, and
  evidence artifact reference.
- Regression deviation evidence is generated only for scheduled failures; normal
  push and pull-request failures remain standard CI failures.
- The issue-opening permission is not available to normal test execution; only
  the scheduled-failure issue job can write issues.
- Third-party Action updates now require an intentional SHA update and review
  rather than silently following a moving tag.
- Manual equipment-library population is accepted as a production-readiness
  activity and is not a blocker for the current P5 validation hardening.

## Verification

- Focused validation report suite after P5 validation evidence hardening:
  4 passed on Python 3.12.10.
- Default regression suite after P5 validation evidence hardening:
  345 passed, 2 skipped on Python 3.12.10.
- Focused regression deviation suite after scheduled-failure handling:
  3 passed on Python 3.12.10.
- Focused validation/deviation suite after scheduled-failure handling:
  7 passed on Python 3.12.10.
- Default regression suite after scheduled-failure handling:
  348 passed, 2 skipped on Python 3.12.10.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| Human reviewer disposition is generated as a pending template, not completed automatically. | Require human QA/laboratory review and approval before production release. |
| Controlled fixture tests remain opt-in and local unless explicitly enabled. | Keep them opt-in until fixture confidentiality and CI storage approvals are formally documented. |
| GitHub issue creation depends on workflow token issue permissions. | Keep generated JSON/Markdown deviation artifacts as retained evidence even if issue creation fails, and verify repository Actions permissions before production validation. |
