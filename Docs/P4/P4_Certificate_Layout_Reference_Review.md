# P4 Certificate Layout Reference Review

Status: active P4 reference record.

## Reference Files

| File | SHA-256 | Classification | CI use |
|---|---|---|---|
| `Docs/Design Document/SIMVal Certificate.xlsx` | `BD742DD5965CC4AAC5FD819D65CD885FAF5B7AD99D869C1B24280C3A77EE4E3A` | `controlled_internal_confidential` | No |
| `Docs/Design Document/3rd Party Certificate.pdf` | `3B280A9ABE17DABCF774E15EF46FC61AA4CDB9CF0C68F67FF6561CC929922AFB` | `controlled_internal_confidential` | No |
| `Docs/Design Document/Logo - SIMVal.png` | `5AA832C7E4AC9E8CC528CCBCF820873398B957B4D3014FA5CAE45FB4745F9372` | `controlled_internal_logo_asset` | Yes |
| `Docs/Design Document/DANAK Logo 647.png` | `BCCE2BC2E6CE993EEBBD64B7F2F304CE54B65B5A672B9E9B2DFF3D45BE2D3AD9` | `controlled_accreditation_mark_asset` | Yes |

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
- Page 3 now consumes locked selected reference-equipment snapshots from the
  preview model and lists SIMVal ID, type, serial, certificate reference, due
  date, range, and traceability statement.
- Large DUT result tables are split deterministically across additional result
  pages before the final reference-equipment page.
- The cover-page renderer embeds the supplied SIMVal logo and supplied
  DANAK/ILAC CAL Reg.nr. 647 accreditation mark as PDF image XObjects when the
  controlled asset files are present.
- The SIMVal logo is drawn larger than the DANAK/ILAC mark to satisfy the
  design requirement and AB02 prominence constraint.

## Remaining Gaps

- Certificate metadata is now persisted through an audited service/API capture
  path and included in immutable preview snapshots. Post-capture metadata
  revision/editing is still not implemented.
- Reference-equipment snapshots are available to the renderer and can be
  selected through an audited service/API. Point-level suitability is checked at
  preview/release, but full equipment-library CRUD is not yet implemented.
- Exact visual grid matching and final DANAK/ILAC scope-language review are not
  yet implemented.
