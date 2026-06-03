# P4 Certificate Layout Reference Review

Status: active P4 reference record.

## Reference Files

| File | SHA-256 | Classification | CI use |
|---|---|---|---|
| `Docs/Design Document/SIMVal Certificate.xlsx` | `BD742DD5965CC4AAC5FD819D65CD885FAF5B7AD99D869C1B24280C3A77EE4E3A` | `controlled_internal_confidential` | No |
| `Docs/Design Document/3rd Party Certificate.pdf` | `3B280A9ABE17DABCF774E15EF46FC61AA4CDB9CF0C68F67FF6561CC929922AFB` | `controlled_internal_confidential` | No |

The raw files may be used as local design references. Automated default-CI
tests must use generated or sanitized data only.

## SIMVal Workbook Observations

- Workbook sheets: `SIMVal forside`, `Side 2`, `Side 3 `, `Konstanter`.
- The certificate structure is three pages: cover page, result page, and
  reference-equipment page.
- Page 1 uses an A4 portrait layout from columns `A:H`, with merged label/value
  sections for certificate date, approval/signature, certificate number, client,
  purchase order, calibrated item, dates, traceability, place, procedure, and
  uncertainty text.
- Page 1 contains three embedded PNG references: two header images/logos and one
  footer logo block.
- Page 2 repeats certificate number/page identity, includes remarks,
  measurement conditions, result heading, and a result table with reference
  value, measured value, error, and uncertainty columns.
- Page 3 is currently empty in the workbook, but the third-party reference shows
  it should carry reference-equipment details.
- The workbook constants sheet contains bath/block identifiers and interval/MPE
  values. It is layout evidence only for P4 and must not override approved
  versioned constants.

## Third-Party Certificate Observations

- The reference certificate is three A4 pages.
- Page 1 contains bilingual certificate title, certificate date, approval,
  certificate number, task number, client, purchase order, calibrated item,
  calibration date, receipt date, traceability text, place, procedure, and
  uncertainty statement.
- Page 2 repeats certificate number and item identity, then shows remarks,
  measurement conditions, temperature scale, and a table of reference
  temperature, indication, and error of indication with uncertainty.
- Page 3 repeats certificate number and lists reference equipment.
- The third-party certificate is a layout/content reference only. Its calculation
  method and uncertainty assumptions are not authoritative for SIMVal unless
  independently approved.

## P4 Renderer Decisions

- The renderer must continue to consume locked preview values and must not
  recalculate certificate rows.
- The first SIMVal-oriented renderer slice produces at least three pages:
  cover, one or more result pages, and a reference-equipment page.
- A single certificate can contain one DUT or multiple DUT groups. The current
  P4 renderer creates one result page per DUT group.
- Raw layout references are not default-CI fixtures. Renderer tests assert the
  approved structure using generated preview rows.

## Remaining Gaps

- Certificate metadata is now persisted in an immutable preview snapshot, but
  metadata capture/editing is not yet exposed through an audited service/API.
- Reference-equipment selection is not yet available to the renderer.
- Logos, DANAK mark placement, and exact visual grid matching are not yet
  implemented.
- Page overflow handling for many result rows per DUT still needs a renderer
  rule before production validation.
