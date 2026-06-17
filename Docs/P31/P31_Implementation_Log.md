# P31 Implementation Log

Status: implemented for reviewer-independence validation evidence generation.

P31 adds a controlled evidence generator for the pilot `reviewer_independence`
evidence key. The generator records whether the regulated workflow used four
distinct actors, whether same-user blocking was demonstrated or a deviation was
approved, and whether reviewer approval is present.

## Scope Implemented

- Added `app.backend.validation.reviewer_independence`.
- Added `scripts/validation/generate_reviewer_independence_evidence.py`.
- The evidence hashes actor identifiers before writing them to JSON.
- The evidence records the workflow evidence file checksum and size.
- The CLI returns exit code `0` only when regulated roles are independent,
  same-user blocking evidence or an approved deviation is present, and reviewer
  approval is supplied.
- The CLI returns exit code `2` while blockers remain.
- Updated production runtime and go-live evidence-pack documentation.

## Compliance Notes

- This does not replace backend reviewer-independence enforcement; it creates
  retained pilot evidence for the production-readiness package.
- Actor identifiers are hashed in the generated JSON to reduce unnecessary
  personal-data exposure in validation packages.
- No calculation, uncertainty, CMC, rounding, certificate rendering, release,
  audit immutability, reviewer-independence enforcement, parser, authentication,
  or token-validation logic was changed.

## Verification

- Unit tests cover passed evidence, reused actor blocking, missing same-user
  block/deviation evidence, controlled deviation handling, missing workflow
  evidence, timezone-aware timestamps, CLI output, exit code `0`, and exit code
  `2`.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| The generator depends on operators supplying the correct account identifiers from the pilot run. | Retain the underlying workflow/audit evidence file and require Laboratory Chief and QA/Compliance review before using `--reviewer-approved`. |
| Hashing actor identifiers protects the package, but reviewers may still need to map hashes back to controlled user records. | Keep the user-role access review in controlled operations evidence outside source control. |
