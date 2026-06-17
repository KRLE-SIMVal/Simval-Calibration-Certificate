# P27 Implementation Log

Status: implemented for controlled pilot-validation planning.

P27 adds repeatable pilot-validation plan generation for the validation phase
before routine production use. The generated plan maps pilot activities to
IQ/OQ/PQ stages, owner roles, readiness evidence keys, acceptance criteria, and
stop conditions.

## Scope Implemented

- Added `app.backend.validation.pilot` for deterministic pilot-plan generation.
- Added `scripts/validation/generate_pilot_validation_plan.py`.
- Added `scripts/validation/generate_pilot_validation_package.py` to map
  required pilot evidence keys into the existing IQ/OQ/PQ validation package.
- The plan includes controlled activities for runtime configuration, automated
  regression and smoke evidence, ValProbe parser validation, independent
  certificate workflow execution, and backup/restore drill evidence.
- The plan writes `pilot-validation-plan.json` and `pilot-validation-plan.md`.
- Updated production runtime and go-live evidence-pack documentation.

## Compliance Notes

- The pilot plan does not approve production use.
- Routine production remains blocked until pilot evidence is accepted,
  deviations are dispositioned, and the production readiness report has no
  blockers.
- No calculation, uncertainty, CMC, rounding, certificate rendering, release,
  audit immutability, reviewer-independence enforcement, parser, authentication,
  or token-validation logic was changed.

## Verification

- Pilot-plan unit tests cover evidence-key mapping, Markdown output,
  timezone-aware timestamps, CLI output, and file writing.
- Pilot package tests cover IQ/OQ/PQ stage mapping and standard validation
  package output.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| The plan is a controlled template; it does not execute the pilot activities. | Execute each activity in the validation environment, retain the referenced evidence files, and include them in the validation package. |
| The pilot still depends on human review of parser fixtures, certificate output, and workflow evidence. | Require Laboratory Chief, QA/Compliance, Metrology, and Security/GDPR reviewer disposition before go-live. |
