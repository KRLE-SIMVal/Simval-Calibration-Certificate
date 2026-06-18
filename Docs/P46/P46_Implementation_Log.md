# P46 Implementation Log

Status: implemented for active browser manual pressure preview.

P46 turns the browser shell from a mostly static API-sample surface into an
active local workflow for inspecting a manual pressure certificate before
release controls are exercised.

## Changes

- Added `POST /certificate-preview-pdfs`.
  - Builds the same audited certificate preview as `POST /certificate-previews`.
  - Renders a PDF response directly from locked preview rows.
  - Returns checksum and preview audit id headers.
  - Does not persist a certificate record, release artifact, or release audit
    event.
- Added a Manual Pressure Preview panel to `/app`.
  - Creates a pressure/manual job with a unique id.
  - Captures pressure certificate metadata.
  - Selects pressure reference equipment.
  - Uploads generated CSV source evidence.
  - Records manual pressure readings.
  - Creates approved pressure constants and budget versions for the sample job.
  - Runs the pressure calculation.
  - Opens a preview PDF from the new non-release preview endpoint.
- Fixed the embedded browser JavaScript row-splitting regex so the script
  remains valid after Python string rendering.

## Verification

- `python -m compileall app\backend\api\app.py app\backend\ui\workflow.py tests\unit\test_api_app.py`
- `python -m pytest tests/unit/test_api_app.py -q`
- `python -m pytest tests/unit/test_pressure_manual_entry_service.py tests/unit/test_pressure_calculation_service.py tests/unit/test_api_app.py -q`
- Extracted browser script parsed successfully with `node --check`.
- Live local server on `http://127.0.0.1:8022/app` returned the updated app.
- Live manual pressure preview sequence generated a PDF through
  `POST /certificate-preview-pdfs`.

## Domain And Compliance Notes

- No metrology formula changed.
- The preview PDF is not a released certificate.
- Accreditation marking remains controlled by the request flag; the guided
  manual pressure preview disables it.
- Routine release still requires the existing approval, reviewer independence,
  artifact storage, and release audit controls.
