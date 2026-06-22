# P47 Implementation Log

Status: implemented for active browser temperature certificate workflow.

P47 changes the local browser workspace from a pressure-first preview into the
Phase 1 temperature certificate flow described in the design requirements. The
Pressure selector option remains visible, but it now switches the page into a
deferred state instead of pretending the pressure workflow is production-ready.

## Changes

- Made `/app` temperature-first:
  - Default discipline is Temperature and default mode is Automatic.
  - Main wizard fields now cover calibration XLSX upload, verification PDF
    evidence upload, IRTD row transcription, measurement window selection,
    temperature uncertainty budget inputs, calculation, preview, review, and
    release.
  - Pressure mode now visibly changes the UI and is marked deferred for Phase 3.
- Added a development-only runtime flag:
  - `SIMVAL_ALLOW_PROVISIONAL_VALPROBE_PARSER=true`
  - The flag enables the existing provisional ValProbe XLSX parser only outside
    production. Production rejects this flag.
- Fixed generated temperature data-entry identifiers:
  - DUT IDs are now job-scoped, for example
    `dut-ui-temp-1782112382-MJT1-A`.
  - Required setpoint IDs are now job-scoped.
  - This prevents repeated jobs using the same logger channel from colliding in
    the SQLite controlled record tables.
- Updated the browser temperature certificate runner to build required preview
  audit evidence before release.

## Verification

- `python -m pytest tests\unit -q`
  - 640 passed.
- Live local server on `http://127.0.0.1:8028/app` returned ready.
- Live temperature flow generated and released a certificate PDF using:
  - Generated ValProbe-style XLSX fixture
  - Stored verification PDF evidence
  - Temperature data entry
  - IRTD transcription
  - Measurement window selection
  - Approved constants and uncertainty budget
  - Temperature calculation
  - Technical review, QA approval, preview audit evidence, and release

Live evidence was retained at:

- `.runtime/temperature-ui-live-evidence.json`

## Domain And Compliance Notes

- No metrology formula, uncertainty calculation, CMC rule, or rounding logic was
  changed.
- The ValProbe parser remains provisional and is still blocked in production
  runtime settings.
- Local test sessions are still only for laboratory flow testing and do not
  replace Entra/authenticated production access.
- Pressure is intentionally deferred for Phase 3 method validation.
