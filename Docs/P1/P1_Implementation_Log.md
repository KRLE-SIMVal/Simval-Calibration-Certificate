# P1 Implementation Log

Status: started.

## Scope Implemented

- Python package skeleton for backend, domain, audit, imports, and CMC calculation primitives.
- Pytest project configuration.
- Explicit Python package discovery for clean editable installs.
- GitHub Actions CI skeleton with quarterly scheduled regression trigger.
- Controlled fixture manifest for the three example files.
- Immutable core domain entities for client, calibration job, DUT, uploaded-file evidence, source location, parsed reading, and measurement-window selection.
- Immutable reference equipment traceability model with status, certificate reference, due date, range, and suitability blockers.
- Domain workflow state tests.
- Role and permission matrix tests.
- Audit event immutability tests.
- CMC lookup and floor tests for P1 expression types.
- Parser-contract tests for controlled KAYE / ValProbe RT workbook and verification PDF IRTD rule.
- Common calculation primitives for statistics, error of indication, uncertainty conversions, RSS combination, and expansion.
- AB11 reporting-rounding primitives for expanded uncertainty and result precision.
- Validation report model and CLI script for retained test evidence.

## Scope Not Implemented

- No FastAPI endpoints.
- No database models or migrations.
- No full XLSX import workflow.
- No PDF table extraction implementation.
- No persistence repositories or audit transaction orchestration.
- No certificate rendering.
- No production certificate calculations.
- No certificate-level display formatting implementation.

## Verification

- `git diff --check` passed.
- Source and tests compile with fallback `C:\Program Files\FreeCAD 1.0\bin\python.exe` using Python 3.11.13.
- Pytest was installed into workspace-local `.test-deps` for local verification.
- Default suite result with fallback Python after AB11 rounding slice: 44 passed, 2 skipped.
- Python 3.12.10 was installed from the official Python.org Windows installer.
- Clean Python 3.12 virtual environment editable-install path is covered by `ENV-001`.
- Pytest cache writes are disabled because controlled evidence is generated explicitly and `.pytest_cache` is not required for regression records.
- Focused domain entity suite: 15 passed on Python 3.12.10.
- Default suite result after core domain entity slice on Python 3.12.10: 59 passed, 2 skipped.
- Focused reference equipment and domain-validation suite: 31 passed on Python 3.12.10.
- Default suite result after reference equipment traceability slice on Python 3.12.10: 75 passed, 2 skipped.
- JUnit XML evidence was generated at `Docs/Validation/evidence/latest/pytest.xml`.
- Validation report CLI was exercised and generated `Docs/Validation/evidence/latest/validation-report.json`.
- The 2 skipped tests are controlled-file tests disabled until confidentiality classification.

## Environment Notes

- `python.exe` and `py.exe` still resolve to Windows app aliases that fail to start in this session; use `.venv\Scripts\python.exe` or the absolute Python 3.12 path.
- Fallback Python 3.11.13 was only a verification workaround before Python 3.12.10 was installed.
- Optional controlled-file tests were attempted with `SIMVAL_RUN_CONTROLLED_FIXTURE_TESTS=1`, but FreeCAD Python could not read the OneDrive example files and raised `PermissionError`. PowerShell can read the same files. Recommended solution: install/use a normal Python 3.12 runtime with OneDrive file access, or create sanitized fixtures in a non-restricted test fixture path before enabling these tests in CI.
