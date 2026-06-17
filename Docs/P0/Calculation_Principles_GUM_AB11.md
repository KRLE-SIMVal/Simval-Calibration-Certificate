# Calculation Principles Based On GUM And DANAK AB11

## Purpose

This document defines the initial calculation basis for the SIMVal application. It replaces legacy-workbook replication as the validation strategy.

The calculation engine must be validated from first principles using:

- JCGM 100:2008 / GUM principles.
- DANAK AB11 for uncertainty in calibration.
- Approved SIMVal method assumptions.
- Independently reviewable worked examples.

## Core Result Model

For a certificate result row:

```text
error_of_indication = indication - reference
reported_result = error_of_indication +/- expanded_uncertainty
```

The result must retain:

- Raw reference value.
- Raw indication value.
- Raw error of indication.
- Each uncertainty contribution.
- Standard uncertainty for each contribution.
- Sensitivity coefficient for each contribution.
- Combined standard uncertainty.
- Coverage factor.
- Expanded uncertainty before CMC floor.
- Applicable CMC.
- Expanded uncertainty after CMC floor.
- Display-rounded values.

## Standard Uncertainty Conversion

Uncertainty contributions are combined as standard uncertainties.

| Source form | Standard uncertainty rule |
|---|---|
| Expanded uncertainty `U` with coverage factor `k` | `u = U / k` |
| Normal standard uncertainty | `u = supplied_u` |
| Rectangular half-width `a` | `u = a / sqrt(3)` |
| Triangular half-width `a` | `u = a / sqrt(6)` |
| U-shaped half-width `a` | `u = a / sqrt(2)` |
| Digital resolution `r` | `u = (r / 2) / sqrt(3)` unless method states otherwise |

If a contribution has a sensitivity coefficient `c`, the contribution to combined uncertainty is:

```text
u_effective = abs(c) * u
```

## Combining Standard Uncertainties

For independent contributions:

```text
u_c = sqrt(sum(u_effective_i^2))
U = k * u_c
```

Default coverage factor:

```text
k = 2
```

Default coverage statement:

```text
The expanded uncertainty is based on the combined standard uncertainty multiplied by coverage factor k = 2, corresponding to approximately 95% coverage under the stated assumptions.
```

Any use of another coverage factor, effective degrees of freedom, or Monte Carlo method requires a separate approved method rule and tests.

## CMC Floor And Lookup

DANAK AB11 requires the reported expanded uncertainty not to be lower than the laboratory CMC.

Initial rule:

```text
U_after_cmc = max(U_calculated, CMC(reference_or_range))
```

The final displayed expanded uncertainty must not be lower than the applicable CMC after display rounding.

The detailed CMC policy is defined in [CMC_Range_Interpolation_Rules.md](CMC_Range_Interpolation_Rules.md).

P0 decision:

- CMC entries must be versioned and approved before use.
- CMC lookup must consider discipline, measurand, method/procedure, equipment type, range, unit, and secondary parameters where relevant.
- Supported initial expression types are `constant`, `linear_segment`, and `table_worst_case`.
- Linear interpolation is allowed only for approved one-dimensional CMC segments that are documented as approximately linear and monotonic.
- Formula-based CMC is allowed after the formula is approved and tested.
- Matrix-based CMC is deferred until a concrete approved method requires it; matrix interpolation requires a separate approved rule and tests.
- Graphical CMC is not accepted directly; it must be converted into an approved numeric table or formula.
- Unknown, missing, retired, conflicting, ambiguous, or out-of-range CMC blocks approval and export.

## AB11 Rounding And Reporting

Initial reporting rule from AB11:

- Expanded uncertainty must be reported with no more than two significant digits.
- The reported result must be rounded to the least significant digit of the reported expanded uncertainty.
- Coverage factor `k` and coverage probability statement must appear on the certificate.

P0 rule:

- MVP uses two significant digits for expanded uncertainty unless SIMVal approves a stricter method-specific rule.
- Raw values are always stored at full precision.
- Display rounding is a presentation layer over stored calculation results.
- Rounding tests must cover positive, negative, zero-crossing, very small, and boundary values.

## Temperature Calculation Scope

Temperature certificate calculations use:

```text
R = mean(reference readings in selected window)
I = mean(DUT readings in selected window) or manual indication
error = I - R
```

Expected contribution families:

- Reference sensor uncertainty.
- Reference sensor repeatability.
- DUT indication repeatability, when applicable.
- Paired error repeatability, when the approved method treats linked
  reference/DUT observations as paired differences.
- Bath/thermostat contribution, when applicable.
- DUT resolution.
- CMC floor.
- Method-specific stability or homogeneity contributions where required.

### Temperature Type A Repeatability Method

The default automatic temperature Type A method is
`independent_reference_and_dut`. It preserves the initial approved model from
the design brief:

```text
u_ref = stdev.s(R_i) / sqrt(n)
u_ind = stdev.s(I_i) / sqrt(n)
```

The engine also supports `paired_error_differences` for linked simultaneous
reference/DUT observations when the approved uncertainty budget treats the
repeatability term as the standard uncertainty of the mean error series:

```text
E_i = I_i - R_i
u_error_repeatability = stdev.s(E_i) / sqrt(n)
```

Metrology impact: the paired method accounts for correlation common to the
simultaneous reference and indication readings by evaluating the observed error
series directly. It must not be selected for routine certificates unless the
SIMVal-approved method, budget version, and validation examples explicitly use
that model. The selected Type A method must be retained in calculation audit
evidence.

## Pressure Calculation Scope

Pressure certificate calculations use:

```text
error = indication - reference_pressure
```

Expected branches:

- Gauge pressure.
- Absolute pressure.
- Differential pressure.
- Manual up/down indication.
- Automatic reference/DUT file comparison.

Absolute pressure must include barometer contribution when method-relevant. Gauge pressure must not include barometer contribution unless a method rule requires it.

## Worked Example Pattern

Each calculation test must include:

- Input values and units.
- Distribution assumptions.
- Conversion to standard uncertainty.
- Sensitivity coefficients.
- Root-sum-square calculation.
- Coverage factor.
- CMC comparison.
- Raw and rounded output.
- Expected audit/calculation summary fields.

Example form:

```text
reference = -90.032 deg C
indication = -90.130 deg C
error = -90.130 - (-90.032) = -0.098 deg C
expanded_uncertainty = 0.010 deg C
reported_error = -0.10 deg C
reported_result = -0.10 +/- 0.01 deg C
```

The example above tests indication-minus-reference and display rounding. It is not a complete uncertainty-budget example.

## Required Review Gate

Before calculation code is implemented:

- Metrology reviewer approves formulas.
- QA/compliance reviewer approves reporting and evidence expectations.
- Test engineer approves test coverage.
- Laboratory chief approves method assumptions.
