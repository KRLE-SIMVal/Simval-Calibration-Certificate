# P43 Implementation Log - Discipline-Aware Certificate Result Wording

## Scope

P43 removes the remaining pressure wording issue in the deterministic
certificate renderer by making result-page wording depend on the locked
certificate-preview discipline.

## Changes

- Added `discipline` to `CertificatePreview`.
- Populated preview discipline from the persisted calibration job during both
  preview generation and release rendering.
- Recorded preview discipline in the `certificate_preview_generated` audit
  event.
- Rendered temperature previews with `Temperaturskala / Temperature scale`.
- Rendered pressure previews with `Trykenhed / Pressure unit` and
  `Trykresultater / Pressure results`.
- Updated template-contract validation so pressure certificates require the
  pressure result heading while temperature certificates keep the temperature
  heading.

## Validation

- Added preview model coverage for retained discipline.
- Added rendering coverage for pressure-specific certificate wording.
- Re-ran focused preview, rendering, rendered-release, and pressure API
  workflow tests.

## Domain Impact

No calculation, uncertainty, CMC, rounding, interpolation, or release logic
changed. The change is presentation and traceability only: certificate output
now uses the job discipline already stored in the regulated workflow.

## Compliance Notes

- Reviewed local DANAK AB2 extract for accredited certificate mark/claim
  context; discipline wording must not mislead about what the accredited scope
  covers.
- Reviewed local DANAK AB11 extract for calibration-certificate reporting
  context; result rows still report reference/indication/error with expanded
  uncertainty and units from locked summaries.

## Remaining Risk

SIMVal QA/Laboratory still needs to approve final pressure certificate wording,
layout, and method-specific pressure statements before routine DANAK production
release. P45 later adds known-schema automatic pressure CSV import; unknown
CSV/XLSX column mapping remains outside this certificate-wording increment.
