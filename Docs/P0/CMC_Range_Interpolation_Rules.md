# CMC Range And Interpolation Rules

## Purpose

This document defines the recommended SIMVal rule for applying Calibration and Measurement Capability (CMC) values in calculations.

The rule is based on:

- DANAK AB11.
- ILAC P14:09/2020.
- BIPM/CIPM MRA guidance on CMCs.
- UKAS M3003 and LAB 45 as practical accreditation-body guidance.
- ISPE GAMP calibration-management guidance as a GxP control reference.

## Source References

Reviewed on 2026-06-01:

- DANAK calibration requirements page: https://danak.dk/akkrediteringsomrader/kalibrering
- DANAK AB11: https://www2.danak.dk/akkreditering/AB/AB11_Maaleusikkerhed_i_kalibrering_medaendrmark.pdf
- ILAC P14:09/2020: https://european-accreditation.org/wp-content/uploads/2018/10/ILAC_P14_09_2020-1.pdf
- BIPM CIPM MRA-G-13: https://www.bipm.org/documents/20126/43742162/CIPM-MRA-G-13.pdf
- UKAS M3003: https://www.ukas.com/wp-content/uploads/2023/05/M3003-The-expression-of-uncertainty-and-confidence-in-measurement.pdf
- UKAS LAB 45: https://www.ukas.com/wp-content/uploads/2021/10/LAB-45-Schedules-of-Accreditation-for-Calibration-Laboratories.pdf
- ISPE GAMP Calibration Management: https://ispe.org/publications/guidance-documents/gamp-good-practice-guide-calibration-management

## Research Finding

CMC is the accredited calibration and measurement capability available to customers under normal conditions. It is not a special best-case value.

Best practice is:

- CMC must be unambiguous in the scope or approved internal capability record.
- CMC must be expressed as expanded uncertainty at approximately 95% coverage.
- CMC must be tied to measurand, method/procedure, instrument/equipment type, range, and any relevant secondary parameter.
- The reported expanded uncertainty on an accredited certificate must not be smaller than the applicable CMC.
- For one-dimensional CMC ranges, DANAK expects the range to be stated so U(CMC) is approximately linear and monotonic in the range.
- ILAC permits CMC uncertainty to be expressed as a single value, a range with appropriate linear interpolation, an explicit function, a matrix, or a graph with sufficient resolution.
- Open interval uncertainty statements are not acceptable.

## SIMVal Rule

SIMVal will use controlled CMC entries with one of these expression types:

| Type | Use | Rule |
|---|---|---|
| `constant` | One CMC value valid throughout a defined range. | Use the same CMC anywhere inside the range. |
| `linear_segment` | CMC varies approximately linearly and monotonically across a one-dimensional range. | Use linear interpolation between approved endpoints. |
| `formula` | Scope or approved method gives an explicit equation. | Evaluate the formula exactly as versioned. |
| `matrix` | CMC depends on measurand plus secondary parameter, such as pressure and range. | Use approved lookup rules; interpolate only if explicitly approved. |
| `table_worst_case` | Table gives discrete intervals but no interpolation rule. | Use the worst applicable CMC inside the interval. |

Graphical CMC expressions are not accepted directly in SIMVal because they are weak for automated auditability. If a source CMC is graphical, it must be converted into an approved numeric table or explicit formula before use.

## Interpolation Policy

Linear interpolation is allowed only when all conditions are true:

- The CMC entry is approved as `linear_segment`.
- The range is one-dimensional.
- U(CMC) is documented as approximately linear and monotonic over the segment.
- The measured value is inside the approved range.
- The interpolation formula and endpoints are versioned.
- Automated tests cover the lower bound, upper bound, midpoint, and at least one off-midpoint value.

Linear interpolation is not allowed when:

- The CMC entry is a discrete interval without interpolation approval.
- The source uses open intervals such as "less than x".
- The value is outside the approved range.
- Two matching entries conflict.
- The range depends on a secondary parameter and no matrix interpolation rule is approved.
- The CMC source is graphical and has not been converted into approved numeric data.

When interpolation is not allowed, use the conservative table rule or block approval/export.

## Range Boundary Policy

CMC ranges must use explicit lower and upper bounds.

Default interval ownership:

```text
[lower_bound, upper_bound)
```

The final segment in a contiguous range may include its upper bound:

```text
[lower_bound, upper_bound]
```

This prevents one value from matching two adjacent ranges.

If ranges overlap:

- If one entry is more specific by method, equipment type, or secondary parameter, use the more specific entry.
- If both entries are equally specific and produce different CMC values, block calculation approval/export and require admin resolution.
- If overlap is intentional and documented, the approved rule must state whether to use the more conservative CMC or a specific entry.

If there is a gap:

- Values in the gap are out of scope.
- Calculation may be saved as draft, but approval/export is blocked.

## CMC Floor Application

For each result row:

```text
U_before_cmc = calculated expanded uncertainty
U_cmc = applicable CMC(reference_value, method, equipment, secondary_parameters)
U_after_cmc = max(U_before_cmc, U_cmc)
```

Then apply AB11/ILAC reporting rounding.

The displayed expanded uncertainty must not be lower than `U_cmc`. If normal display rounding would reduce the displayed value below the CMC floor, round the displayed uncertainty upward to the next reportable increment.

The calculation summary must retain:

- CMC entry id and version.
- CMC expression type.
- Range bounds.
- Interpolation rule, if used.
- Raw CMC value before display rounding.
- U before CMC.
- U after CMC.
- Displayed U.
- Whether the CMC floor changed the reported uncertainty.

## Data Model Requirements

CMC entries must include:

- Id.
- Discipline.
- Measurand.
- Method/procedure.
- Equipment/instrument type.
- Lower bound.
- Upper bound.
- Bound inclusion rule.
- Unit.
- Secondary parameter bounds where applicable.
- Expression type.
- Expression data.
- Coverage probability.
- Coverage factor or policy.
- Source reference.
- Effective date.
- Version.
- Status.
- Approved by.
- Approval timestamp.

Units must be explicit. Avoid ambiguous terms such as PPM and PPB; use percent, explicit ratios such as uV/V, or parts per 10^6 with a defined scale.

## Blocking Rules

Approval and certificate export must be blocked when:

- No matching approved CMC entry exists.
- The measurement value is outside the approved CMC range.
- Units cannot be converted safely.
- The CMC entry is draft, retired, or not effective on the certificate date.
- The CMC expression is open-ended or ambiguous.
- Interpolation would be required but is not approved.
- Matching CMC entries conflict.
- Display rounding would produce a reported U below the CMC floor and cannot be safely adjusted.

## Test Requirements

Add automated tests for:

- Constant CMC lookup.
- Linear interpolation lower bound.
- Linear interpolation upper bound.
- Linear interpolation midpoint.
- Linear interpolation off-midpoint.
- Out-of-range below.
- Out-of-range above.
- Range gap.
- Overlapping ranges with clear specificity.
- Overlapping ranges with conflict.
- Formula CMC.
- Matrix CMC without interpolation.
- Matrix CMC with approved interpolation.
- Table worst-case rule.
- Open interval rejection.
- Ambiguous unit rejection.
- CMC floor raising U.
- CMC floor not changing U.
- Display rounding never below CMC.

## Recommended Initial SIMVal Position

For P1, use only:

- `constant`.
- `linear_segment`.
- `table_worst_case`.

Do not implement graph-based CMC. Do not implement matrix interpolation until a concrete pressure use case requires it.

This keeps the first release auditable and avoids hidden interpolation behavior.
