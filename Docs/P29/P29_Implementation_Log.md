# P29 Implementation Log

Status: implemented for ValProbe parser-validation evidence generation.

P29 adds a controlled evidence generator for the pilot
`valprobe_parser_validation` evidence key. The generator records parser version,
required coverage, input evidence files, checksums, controlled-fixture execution
status, and reviewer approval status.

## Scope Implemented

- Added `app.backend.validation.parser_validation`.
- Added `scripts/validation/generate_parser_validation_evidence.py`.
- The CLI returns exit code `0` only when controlled fixture execution is
  marked enabled and reviewer approval is explicitly supplied.
- The CLI returns exit code `2` while parser-validation blockers remain.
- Updated production runtime and go-live evidence-pack documentation.

## Compliance Notes

- This creates the parser-validation evidence record; it does not perform human
  review or approve routine parser use by itself.
- `--reviewer-approved` must only be used after the Laboratory/Metrology/QA
  reviewers accept the parser fixture coverage and limitations.
- No calculation, uncertainty, CMC, rounding, certificate rendering, release,
  audit immutability, reviewer-independence enforcement, parser behavior,
  authentication, or token-validation logic was changed.

## Verification

- Unit tests cover passed evidence, blocked evidence, missing evidence files,
  timezone-aware timestamps, CLI output, exit code `0`, and exit code `2`.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| The generator can confirm that parser evidence files exist and are checksummed, but cannot judge the metrological adequacy of the fixture set. | Require Laboratory Chief, Metrology Reviewer, and QA/Compliance Reviewer disposition before using `--reviewer-approved`. |
| Controlled fixture execution remains opt-in because fixture files are confidential. | Run controlled fixture tests only in the approved validation environment and retain the controlled report outside source control. |
