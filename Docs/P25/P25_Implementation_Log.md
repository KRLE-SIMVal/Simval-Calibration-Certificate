# P25 Implementation Log

Status: implemented for ValProbe parser-validation readiness gate.

P25 makes approved ValProbe parser validation evidence an explicit
production-readiness gate. Routine production use remains blocked until the
readiness report is generated with both `--valprobe-parser-validated` and a
matching retained `--evidence valprobe_parser_validation=<path>` reference.

## Scope Implemented

- Added a `valprobe_parser_validated` evidence flag to the production-readiness
  report model.
- Added the `valprobe_parser_validation_missing` readiness blocker.
- Added retained-reference enforcement through the existing
  `valprobe_parser_validation` evidence key.
- Added `--valprobe-parser-validated` to
  `generate_production_readiness_report.py`.
- Updated production runtime and go-live evidence-pack documentation.

## Compliance Notes

- This prevents a report from becoming ready for go-live review while the
  provisional ValProbe parser lacks approved validation evidence.
- The gate does not approve parser use by itself; the referenced validation
  record still needs System Owner and QA/Laboratory review.
- No calculation, uncertainty, CMC, rounding, certificate rendering, release,
  audit immutability, reviewer-independence, authentication, or token-validation
  logic was changed.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| Parser validation evidence cannot be created from code alone because approved ValProbe workbook variants and lab review records are controlled external evidence. | Build the fixture set from approved non-customer or anonymized workbooks, include malformed and unsafe workbook rejection cases, and retain QA/Laboratory approval with the validation package. |
| The readiness report checks that evidence is referenced and available; it does not judge the metrological adequacy of the workbook fixture set. | Require Domain SME, Metrology Reviewer, and QA/Compliance Reviewer disposition before enabling routine production parser use. |
