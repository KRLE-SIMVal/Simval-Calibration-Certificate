# P5 Implementation Log

Status: started.

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

## Scope Not Implemented

- Automatic issue/deviation creation for failed quarterly regressions is not
  implemented yet.
- Reviewer disposition capture is not implemented yet.
- Controlled confidential fixture execution remains opt-in only through
  `SIMVAL_RUN_CONTROLLED_FIXTURE_TESTS=1`.
- Full IQ/OQ/PQ validation package generation is not complete.

## Compliance Notes

- This slice does not change calculation logic, certificate rendering logic,
  workflow state logic, or reported values.
- Controlled internal reference files remain excluded from default CI.
- Scheduled regression evidence is now easier to retain and review because the
  report records the tested commit, run trigger, quarter, environment, and
  evidence artifact reference.

## Verification

- Focused validation report suite after P5 validation evidence hardening:
  4 passed on Python 3.12.10.
- Default regression suite after P5 validation evidence hardening:
  345 passed, 2 skipped on Python 3.12.10.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| A quarterly failure does not yet create an issue or deviation automatically. | Add a failure-handling job that creates a GitHub issue or QMS deviation stub with run id, commit, failed suite, and affected area. |
| Human reviewer disposition is not captured in the generated evidence package. | Add a controlled reviewer-disposition template and require attachment/review after scheduled runs. |
| Controlled fixture tests remain opt-in and local unless explicitly enabled. | Keep them opt-in until fixture confidentiality and CI storage approvals are formally documented. |
