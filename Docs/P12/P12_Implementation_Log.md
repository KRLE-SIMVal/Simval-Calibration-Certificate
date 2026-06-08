# P12 Implementation Log

Status: started for pressure calculation-engine foundation.

P12 begins pressure support without changing the production temperature
certificate workflow. This slice establishes first-principles pressure
calculation primitives that can later be connected to pressure import,
measurement-window, API, and certificate-template workflows.

## Scope Implemented

- Added `app/calculation_engine/pressure/results.py`.
- Added controlled pressure kinds: gauge, absolute, and differential.
- Added manual pressure calculation for a supplied reference pressure and one or
  more DUT indication values.
- Manual gauge pressure supports up/down indication averaging by averaging the
  supplied indication values before calculating error of indication.
- Added automatic pressure calculation from paired reference and DUT readings.
- Automatic pressure includes reference mean, DUT mean, reference repeatability,
  and DUT indication repeatability.
- Added pressure uncertainty inputs for reference MPE/expanded uncertainty, DUT
  resolution, optional absolute-pressure barometer uncertainty, CMC floor,
  coverage factor, and additional standard uncertainty terms.
- Barometer uncertainty is accepted only for absolute pressure and is rejected
  for gauge/differential pressure to avoid hidden method ambiguity.
- Pressure summaries use the shared result rule `indication - reference`, shared
  CMC floor, shared AB11 rounding, and version-locked summary model.

## Scope Not Implemented

- No pressure import parser, pressure measurement-window service, pressure API
  endpoint, pressure UI workflow, or pressure certificate template is connected
  yet.
- Differential pressure range/unit compatibility is not implemented beyond the
  controlled pressure-kind model.
- Pressure CMC/MPE lookup tables are not connected yet; this slice accepts
  approved uncertainty inputs supplied by the caller.

## Compliance Notes

- This slice does not change temperature calculations, certificate rendering,
  workflow state transitions, audit trail, or permissions.
- The formulas follow the approved common principle that error of indication is
  indication minus reference.
- Standard uncertainties are combined by RSS and expanded with the supplied
  coverage factor.
- Gauge pressure omits barometer contribution by rule; supplying barometer
  uncertainty for gauge/differential pressure is blocked.
- The pressure foundation is not production workflow-ready until pressure
  constants, approved examples, import/windowning, API, and certificate output
  are separately implemented and validated.

## Verification

- Pressure calculation focused suite:
  8 passed on Python 3.12.10.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| Pressure workflow is not connected to import/API/certificate output. | Implement pressure workflow as a separate milestone with tests first, starting with manual gauge pressure and then automatic/absolute/differential branches. |
| No approved SIMVal pressure examples exist yet. | Continue deriving tests from GUM/AB11 principles now; require SIMVal/laboratory review and controlled worked examples before production pressure use. |
| Pressure MPE/CMC lookup data is not connected. | Add approved pressure CMC/MPE tables with versioned lookup tests before enabling pressure release. |
