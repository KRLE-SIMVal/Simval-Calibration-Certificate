# P1 Council Preparation

Status: prepared for council review.

## New User Inputs

SIMVal added example files under:

```text
Docs/Input and output file examples/
```

Confirmed inventory:

| File | Type | SHA-256 | Purpose | Notes |
|---|---|---|---|---|
| `Calibration_input_file_Valprobe RT Loggers.xlsx` | XLSX input | `71B6AAE2BCF599A65F25B16330473B1D7B60D3A3C0D3FD169D929E25CB362B02` | KAYE / ValProbe RT calibration export used as input for final certificate. | Contains sheets `Temperature` and `Messages and Comments`. |
| `KAYE Verification file - Valprobe Logger.pdf` | PDF input/reference | `AD60CBA78FFEC2B9FF9D23BC4440DD849C6337FD3C407F773A4CA36B18F8F0F5` | Verification example showing whether a logger maintains accuracy for a temperature setpoint over a defined period, typically 10 minutes. Also contains the IRTD/reference value. | Approx. 37 PDF page objects detected. PDF text extraction tooling not yet selected. |
| `Calibration Certificate Output file.pdf` | PDF output/reference | `C1D02553D14EC400099A48A4E1F8AA506E18DB4FD3FC0FFD15CA85FCEDFF1DC6` | Example certificate from a third-party accredited laboratory. | Approx. 3 PDF page objects detected. Useful for output-field and certificate-layout comparison, not as blind calculation authority. |

The user confirmed there are three files; the earlier reference to four files was a typo.

## Classification Decision

The three raw example files are classified as `controlled_internal_confidential`.

Decision:

- Do not commit the raw XLSX/PDF files to Git at this stage.
- Do not allow these files in CI.
- Use their manifest records, hashes, and structural observations for parser-contract planning.
- Create sanitized fixtures later if automated CI needs real parser inputs.
- Revisit this decision only after repository visibility, customer data, third-party data, and retention expectations are explicitly approved.

## Observed XLSX Structure

`Calibration_input_file_Valprobe RT Loggers.xlsx` has:

- Sheet `Temperature`.
- Sheet `Messages and Comments`.
- `Temperature` used range `A2:AL524`.
- `Temperature` has 521 populated rows.
- `Messages and Comments` used range `A1:E86`.
- `Messages and Comments` has 80 populated rows.
- Temperature data starting with metadata rows, then sensor headers.
- Timestamp column in column A.
- Sensor columns beginning at column B and ending at column AL.
- Row 7 contains 37 sensor headers: `Sensor1(deg C)` through `Sensor37(deg C)`.
- Row 8 contains 37 logger/channel identifiers, from `MJT1-A` through `NWU2-A`.
- Row 9 contains `Study Start`.
- Row 11 contains `Qual`.
- Row 12 begins numeric timestamped measurement data.
- Row 524 contains sparse final timestamped data.
- System messages and start events in `Messages and Comments`.
- No resolved workbook shared-string hit was found for `IRTD`, `reference`, `RTD`, `standard`, or `trace`.

## User-Supplied Reference Mapping Rule

The IRTD/reference value is in `KAYE Verification file - Valprobe Logger.pdf`.

SIMVal states that the IRTD value is listed in the second column directly next to the `Time` column for every logger reading.

Initial implication:

- P1 should include parser-contract tests for KAYE / ValProbe RT XLSX structure.
- The parser must retain row, column, sheet, timestamp, sensor name, logger id, and source-file checksum.
- The parser must not assume all rows are numeric; marker rows such as study start and qualification events must be handled explicitly.
- The calibration import workflow must support linked-file import: XLSX logger readings plus KAYE verification PDF IRTD/reference readings.
- The parser must not infer IRTD/reference values from the XLSX when the source is the verification PDF.
- The import review must show how each logger/time reading is matched to the corresponding IRTD/reference value before calculation.

## Council Review Framing

### Lead Developer

Review whether P1 can include parser-interface tests without implementing full parser behavior.

Recommended position: approve parser-contract tests and fixture registration in P1; defer full import workflow until after domain/test skeleton is stable.

### Architect

Review where file examples belong in the architecture.

Recommended position: treat files as controlled fixtures under test data governance, not ad hoc developer samples. Add a fixture metadata manifest before using them in automated tests.

### Domain SME / Laboratory Chief

Review whether the calibration XLSX and verification PDF represent two related but distinct workflow artifacts:

- Calibration for certificate generation.
- Verification for accuracy hold/stability assessment.

Recommended position: keep calibration and verification as distinct workflow concepts, but allow the calibration workflow to link the verification PDF as a reference-data source when it provides IRTD values.

### Metrology Reviewer

Review what can and cannot be inferred from the third-party certificate.

Recommended position: use the certificate as an output-content and traceability reference, not as the authoritative calculation method unless its method and uncertainty assumptions are known and approved.

### QA/Compliance Reviewer

Review example-file control.

Recommended position: add fixture governance:

- Source.
- Date received.
- Intended use.
- Checksum.
- Confidentiality classification.
- Whether it may be used in CI.
- Whether expected outputs are approved or illustrative only.

### Security/GDPR Reviewer

Review whether the example files contain customer, equipment, personnel, or third-party laboratory data.

Recommended position: classify the files before committing them to any public or shared remote. If personal/customer data exists, create sanitized fixtures for automated CI.

### Test Engineer

Review how examples affect test scope.

Recommended position: add tests for file presence, checksum manifest, workbook sheet detection, header detection, sensor-channel mapping, timestamp parsing, nonnumeric event-row handling, PDF verification table detection, IRTD second-column extraction contract, cross-file timestamp alignment, and parser warning behavior.

### UX Reviewer

Review import-review expectations.

Recommended position: import review must show parsed sheets, channels/loggers, timestamps, ignored event rows, parser warnings, linked verification PDF rows, and the selected reference IRTD mapping before calculation.

## Recommended P1 Scope Adjustment

Keep P1 focused on test foundation and domain skeleton, but add one fixture-control slice:

1. Create fixture manifest format.
2. Register the three visible example files with checksum and intended use.
3. Add parser-contract tests that initially fail or are marked pending until parser implementation.
4. Add workbook-structure detection tests for:
   - Sheet names.
   - Header row.
   - Timestamp column.
   - Sensor columns.
   - Logger identifiers.
   - Messages/comments sheet.
5. Add verification-PDF contract tests for:
   - Table contains `Time`.
   - IRTD/reference value is in the second column next to `Time`.
   - Logger reading rows can be matched to IRTD/reference rows.
   - Extraction failure produces a blocking parser warning.
6. Add security classification task before using real files in CI.

Do not implement production parsing logic in P1 unless the council explicitly expands P1.

## Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| Example files may contain sensitive customer/equipment/personnel data. | Classified as `controlled_internal_confidential`; keep raw files out of Git/CI and create sanitized CI fixtures if needed. |
| Third-party certificate may encode assumptions not visible in the PDF. | Use it as layout/output reference only until method assumptions are independently approved. |
| Verification workflow may be confused with calibration workflow. | Define verification as a separate workflow type in domain planning unless SIMVal decides otherwise. |
| PDF extraction is not available locally. | Select a boring, testable PDF text/table extraction dependency before implementing verification-PDF parsing; keep production extraction out of P1 unless the dependency is approved. |
| Reference values are split across XLSX and PDF inputs. | Treat calibration import as a linked-file workflow and require import review to confirm timestamp/logger alignment before calculation. |

## Proposed Council Decision

Recommended decision: approve P1 with comments.

Condition:

- P1 may include fixture governance and parser-contract tests.
- P1 may include linked-file parser contracts for XLSX logger readings and PDF IRTD/reference readings.
- P1 must not implement full import, calculation, or certificate rendering behavior before the tests and data classifications are approved.
