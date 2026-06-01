# P1 Implementation Log

Status: started.

## Scope Implemented

- Python package skeleton for backend, domain, audit, imports, and CMC calculation primitives.
- Pytest project configuration.
- GitHub Actions CI skeleton with quarterly scheduled regression trigger.
- Controlled fixture manifest for the three example files.
- Domain workflow state tests.
- Role and permission matrix tests.
- Audit event immutability tests.
- CMC lookup and floor tests for P1 expression types.
- Parser-contract tests for controlled KAYE / ValProbe RT workbook and verification PDF IRTD rule.
- Common calculation primitives for statistics, error of indication, uncertainty conversions, RSS combination, and expansion.
- Validation report model and CLI script for retained test evidence.

## Scope Not Implemented

- No FastAPI endpoints.
- No database models or migrations.
- No full XLSX import workflow.
- No PDF table extraction implementation.
- No certificate rendering.
- No production certificate calculations.
- No AB11 display rounding implementation.

## Verification

- `git diff --check` passed.
- Source and tests compile with fallback `C:\Program Files\FreeCAD 1.0\bin\python.exe` using Python 3.11.13.
- Pytest was installed into workspace-local `.test-deps` for local verification.
- Default suite result with fallback Python: 37 passed, 2 skipped.
- JUnit XML evidence was generated at `Docs/Validation/evidence/latest/pytest.xml`.
- Validation report CLI was exercised and generated `Docs/Validation/evidence/latest/validation-report.json`.
- The 2 skipped tests are controlled-file tests disabled until confidentiality classification.

## Environment Notes

- `python.exe` and `py.exe` resolve to Windows app aliases that fail to start in this session.
- A proper project Python 3.12 interpreter is still required.
- Fallback Python 3.11.13 is only a verification workaround and is not the approved project runtime.
- Optional controlled-file tests were attempted with `SIMVAL_RUN_CONTROLLED_FIXTURE_TESTS=1`, but FreeCAD Python could not read the OneDrive example files and raised `PermissionError`. PowerShell can read the same files. Recommended solution: install/use a normal Python 3.12 runtime with OneDrive file access, or create sanitized fixtures in a non-restricted test fixture path before enabling these tests in CI.
