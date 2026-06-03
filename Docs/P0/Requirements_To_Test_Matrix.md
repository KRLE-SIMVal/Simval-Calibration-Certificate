# Requirements To Test Matrix

This matrix is the control point between design requirements and automated tests.

Status values:

- Planned: test case defined before code exists.
- Implemented: automated test exists.
- Passing: automated test passes in CI/regression.
- Blocked: requirement cannot proceed until open question is resolved.

## Functional Requirements

| Requirement | Planned test coverage | Initial test IDs | Status |
|---|---|---|---|
| F-001 secure browser access | Authenticated access, unauthenticated rejection, session expiry. | SEC-001, SEC-002, SEC-003 | Planned |
| F-002 home screen workflows | Dashboard route availability by role. | UX-001, RBAC-001 | Planned |
| F-003 step wizard without data loss | Back/next persistence, validation warnings, draft recovery. | WF-001, WF-002, WF-003 | Planned |
| F-004 roles | Permission matrix enforcement. | RBAC-001 to RBAC-020 | Planned |
| F-005 user/timestamp/version recording | Audit event content on regulated actions. | AUD-001 to AUD-010 | Planned |
| F-010 discipline selection | Temperature, pressure, differential pressure branches. | WF-010, WF-011, WF-012 | Planned |
| F-011 manual/automatic mode | Required fields and calculation path selection. | WF-020, TEMP-010, PRESS-010 | Planned |
| F-012 language/template | Template selection and required labels. | CERT-010, CERT-011 | Planned |
| F-013 certificate metadata | Required metadata validation. | CERT-133 to CERT-136, API-011 to API-013, PERSIST-037, PERSIST-038 | Partial |
| F-014 certificate numbers | Internal sequence, duplicate prevention, future provider boundary. | CERT-001, CERT-002, INT-001 | Planned |
| F-015 one certificate per DUT and batch generation | Batch grouping, per-DUT artifacts, combined summary. | CERT-020, CERT-021, CERT-022 | Planned |
| F-016 preview and calculation summary before export | Export blocked until preview/review complete. | CERT-030, CALC-001, WF-040, API-014 to API-016 | Partial |
| F-020 manual entry and file import | Manual readings, known import, unknown import handling. | IMP-001, IMP-002, IMP-003 | Planned |
| F-021 ValProbe RT / Kaye import | Parser fixture coverage for calibration XLSX logger readings and linked verification PDF IRTD/reference values. | IMP-010 to IMP-019, IMP-040 to IMP-045 | Planned |
| F-022 raw file unchanged with checksum | Checksum, immutable raw file metadata, source traceability. | IMP-020, IMP-021, AUD-020 | Planned |
| F-023 unknown CSV/XLSX mapping | Interactive mapping rules and audit of parser choice. | IMP-030, IMP-031 | Planned |
| F-024 measurement window selection | Manual selection, automatic suggestion acceptance, override audit. | WIN-001 to WIN-010 | Planned |
| F-025 statistics | Mean, sample stdev, standard uncertainty of mean, min/max, n. | STAT-001 to STAT-010 | Planned |
| F-026 window warnings | Too few readings, instability, missing channels, time mismatch. | WIN-020 to WIN-029 | Planned |
| F-030 equipment library | Create/edit/status/range/due date. | EQ-001 to EQ-010 | Planned |
| F-031 selected equipment on certificate | Traceability table and artifact content. | EQ-020 to EQ-026, CERT-137, CERT-138, API-003, API-017 to API-019 | Partial |
| F-032 equipment warnings/blocks | Overdue, inactive, wrong range, missing certificate reference. | EQ-030 to EQ-039 | Planned |
| F-033 versioned constants | Version creation, approval, retirement, selection by certificate. | CONST-001 to CONST-020 | Planned |
| F-034 CMC floor | Calculated U below CMC is raised before reporting; CMC lookup follows approved range/interpolation rules. | CMC-001 to CMC-018 | Planned |
| F-035 constants change history | Audit trail and released certificate version locking. | CONST-020, AUD-030, CERT-050 | Planned |

## Calculation And Budget Requirements

| Requirement | Planned test coverage | Initial test IDs | Status |
|---|---|---|---|
| Common error rule | `indication - reference` for all disciplines. | CALC-001, TEMP-001, PRESS-001 | Planned |
| Temperature automatic mode | Reference/DUT means, repeatability, uncertainty combination. | TEMP-010 to TEMP-029 | Planned |
| Temperature manual mode | Manual indication, reference-side uncertainty, CMC. | TEMP-030 to TEMP-039 | Planned |
| Pressure manual mode | Up/down average where applicable, gauge branch. | PRESS-010 to PRESS-019 | Planned |
| Pressure automatic mode | Separate reference and DUT ranges. | PRESS-020 to PRESS-029 | Planned |
| Absolute pressure | Barometer contribution included. | PRESS-030 to PRESS-039 | Planned |
| Differential pressure | Units and range compatibility. | PRESS-040 to PRESS-049 | Planned |
| Rounding and display | AB11 two-significant-digit U and result precision. | RND-001 to RND-020 | Planned |
| CMC range lookup | Constant, linear segment, formula, matrix lookup, table worst-case, and blocked ambiguity cases. | CMC-001 to CMC-018 | Planned |
| UB-001 budget type | Budget family selection by method. | UB-001 | Planned |
| UB-002 contribution fields | Required value, unit, distribution, divisor, source. | UB-010 to UB-019 | Planned |
| UB-003 combined uncertainty | RSS, sensitivity coefficient, expanded uncertainty. | UB-020 to UB-029 | Planned |
| UB-004 distributions | Normal, rectangular, triangular, U-shaped. | UB-030 to UB-039 | Planned |
| UB-005 budget versioning | Draft, approved, retired, certificate link. | UB-040 to UB-049 | Planned |
| UB-006 export evidence | PDF/XLSX content and independent recalculation summary. | UB-050 to UB-059 | Partial |
| UB-007 missing contribution warning | Required method contribution checks. | UB-060 to UB-069 | Planned |

## Output, Audit, And Compliance Requirements

| Requirement | Planned test coverage | Initial test IDs | Status |
|---|---|---|---|
| O-001 certificate template and logos | Required SIMVal/DANAK content, accredited-scope warning. | CERT-100 to CERT-109 | Planned |
| O-002 file naming | Certificate number, date, configurable naming convention. | CERT-110 to CERT-119 | Planned |
| O-003 finalized PDFs | Released artifact immutability and revision-only regeneration. | CERT-120 to CERT-129, API-014 to API-016 | Partial |
| O-004 artifact history | All artifacts retrievable with checksum. | CERT-130 to CERT-139, API-014 | Partial |
| O-005 version references | Software, calculation, constants, budget, template versions. | CERT-140 to CERT-149 | Planned |
| Audit trail | Metadata, windows, results, constants, budgets, status, artifacts. | AUD-001 to AUD-099 | Planned |
| Access control | Edit/approve/regenerate restrictions. | RBAC-001 to RBAC-099 | Planned |
| Data integrity | Raw files unchanged, checksum, parsed row/column traceability. | IMP-020, DATA-001 to DATA-010 | Planned |
| Independent recalculation | Calculation summary has all inputs and intermediate values. | CALC-090 to CALC-099 | Planned |
| Validation package | IQ/OQ/PQ-style or equivalent evidence report. | VAL-001 to VAL-020 | Planned |
| Quarterly regression | Scheduled full-suite execution and evidence retention. | REG-001 to REG-010 | Planned |
