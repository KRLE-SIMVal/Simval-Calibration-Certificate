# P7 Implementation Log

Status: completed for deterministic certificate template-contract validation.

P7 hardens certificate output after the P6 browser workflow shell by adding a
backend release gate for the rendered PDF structure.

## Scope Implemented

- Added a certificate template-contract validator for rendered PDF artifacts.
- The validator checks PDF header, expected page count, certificate number,
  required certificate sections, reference-equipment section, version evidence,
  accreditation mark scope, SIMVal logo presence, DANAK/ILAC mark presence or
  suppression, and absence of placeholder text.
- Rendered certificate release now validates the generated PDF before staging
  artifact bytes.
- Template-contract failures are returned through the existing certificate
  release service error path and no final or pending artifact is written.
- Accredited and non-accredited-scope certificate outputs are both covered by
  tests.

## Scope Not Implemented

- Exact pixel/grid matching against the SIMVal XLSX layout is not implemented.
- Full PDF/A conformance is not implemented.
- Digital or qualified signature handling is not implemented.
- External visual snapshot tooling is not introduced.

## Compliance Notes

- P7 does not change calculation logic, CMC logic, uncertainty logic, rounding,
  preview generation, or reported values.
- The contract validates the rendered artifact created from locked preview
  values and blocks release before controlled storage if required output
  evidence is missing.
- The current contract is deterministic and suitable for automated regression.

## Verification

- Focused certificate rendering and rendered-release suite after P7 template
  contract validation: 19 passed on Python 3.12.10.
- Default regression suite after P7 template-contract validation:
  355 passed, 2 skipped on Python 3.12.10.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| Template-contract validation does not prove exact visual alignment with the approved SIMVal certificate template. | Add reviewed text-extraction and visual snapshot acceptance checks once the final template is approved. |
| PDF/A and signature requirements remain undecided. | Decide archival/signature requirements before production validation. |
| Danish text encoding is validated against the current deterministic renderer output, not an external PDF text extractor. | Add an extraction-based check when a PDF extraction dependency is approved. |
