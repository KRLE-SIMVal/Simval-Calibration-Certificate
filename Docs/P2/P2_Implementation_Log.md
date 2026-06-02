# P2 Implementation Log

Status: started.

P2 begins the temperature certificate workflow implementation after the P1 backend foundation closeout.

## Scope Implemented

- SQLite persistence schema for calibration job records.
- SQLite persistence schema for append-only audit events.
- Calibration job repository with duplicate-ID protection and stale-state protection.
- Audit event repository with ordered entity history lookup.
- Database triggers that reject audit event update and delete operations.
- Transactional workflow persistence service that updates job state and appends the workflow audit event in one database transaction.
- SQLite persistence for uploaded raw-file evidence.
- SQLite persistence for DUT records with duplicate job/serial/channel identity protection.
- SQLite persistence for selected measurement windows and source-located readings.
- Referential integrity from source readings to uploaded-file evidence, DUTs, and calibration jobs.
- SQLite persistence for immutable measurement-point calculation summaries.
- SQLite persistence for certificate records, calculation-summary links, export artifacts, and revision evidence.
- Database triggers that reject released certificate update/delete operations.
- Database triggers that reject calculation-summary and export-artifact update/delete operations.
- SQLite persistence for constant-set version records.
- SQLite persistence for uncertainty-budget version records linked to constant-set versions.
- Database triggers that reject constant-set and uncertainty-budget update/delete operations.
- Internal SQLite certificate number sequence allocator with configurable prefix and zero padding.
- SQLite schema version marker recorded during schema initialization.
- Deterministic ValProbe/KAYE temperature XLSX parser boundary for sanitized workbooks.
- Parser output preserves logger channel, unit, timestamp, source sheet, source row, and source column for each parsed reading.
- Parser warnings are returned for nonnumeric measurement cells instead of silently converting invalid values.
- SQLite persistence for immutable raw parsed readings produced by import parsers.

## Scope Not Implemented

- No production database migration toolchain yet.
- No API endpoints.
- No user/session persistence.
- No parser result orchestration around the uploaded-file, DUT, reading, or measurement-window repositories.
- No controlled-file parser regression in default CI until sanitized customer-safe fixtures are approved.
- No D4 certificate-number adapter yet.

## Compliance Notes

- This slice does not change calculation logic or reported metrology values.
- Audit events are stored separately from job state and are protected as append-only records at database level.
- Workflow transition persistence uses the existing workflow service, so state rules and audit evidence stay aligned with P1 domain behavior.
- Stale-state protection is present so a workflow update cannot silently overwrite a state changed by another process.
- Source-located readings remain linked to uploaded-file evidence, preserving row/column traceability for parsed values.
- Calculation summaries store Decimal uncertainty values as text so reported uncertainty and CMC floor precision are preserved on round trip.
- Released certificate rows, calculation summaries, and export artifacts are protected from direct mutation at database level.
- Constant-set and uncertainty-budget version records are immutable and budget records retain a database reference to the linked constant-set version.
- Certificate numbers can be allocated internally while preserving the future D4 adapter boundary.
- Schema initialization records an auditable schema marker so future migrations can be tied to validation evidence.
- The XLSX parser slice does not calculate certificate results. It only converts sanitized workbook rows into traceable readings.
- Raw parsed readings are retained before measurement-window selection so imported data can be reviewed independently from later selected windows.

## Verification

- Focused persistence suite: 7 passed on Python 3.12.10.
- Focused source-data persistence suite: 7 passed on Python 3.12.10.
- Combined focused persistence suite: 14 passed on Python 3.12.10.
- Focused calculation and certificate persistence suite: 7 passed on Python 3.12.10.
- Expanded combined focused persistence suite: 21 passed on Python 3.12.10.
- Focused version-lock persistence suite: 5 passed on Python 3.12.10.
- Expanded combined focused persistence suite after version-lock repositories: 26 passed on Python 3.12.10.
- Focused certificate numbering suite: 5 passed on Python 3.12.10.
- Expanded combined focused persistence and numbering suite: 31 passed on Python 3.12.10.
- Focused SQLite schema evidence suite: 1 passed on Python 3.12.10.
- Expanded combined focused SQLite persistence, numbering, and schema suite: 32 passed on Python 3.12.10.
- Default regression suite after the first P2 persistence slice: 124 passed, 2 skipped on Python 3.12.10.
- Default regression suite after source-data persistence slice: 131 passed, 2 skipped on Python 3.12.10.
- Default regression suite after calculation and certificate persistence slice: 138 passed, 2 skipped on Python 3.12.10.
- Default regression suite after version-lock persistence slice: 143 passed, 2 skipped on Python 3.12.10.
- Default regression suite after certificate numbering slice: 148 passed, 2 skipped on Python 3.12.10.
- Default regression suite after schema evidence slice: 149 passed, 2 skipped on Python 3.12.10.
- Focused ValProbe XLSX parser suite: 4 passed on Python 3.12.10.
- Import-focused parser and controlled-fixture contract suite: 7 passed, 2 skipped on Python 3.12.10.
- Default regression suite after sanitized ValProbe XLSX parser slice: 153 passed, 2 skipped on Python 3.12.10.
- Focused parsed-reading persistence suite: 3 passed on Python 3.12.10.
- Expanded combined focused SQLite persistence suite after parsed-reading repository: 35 passed on Python 3.12.10.
- Default regression suite after parsed-reading persistence slice: 156 passed, 2 skipped on Python 3.12.10.
- JUnit XML evidence was generated at `Docs/Validation/evidence/latest/pytest.xml`.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| SQLite schema is currently initialized directly, not via controlled migrations. | Add a migration/version table or Alembic/SQL migration runner before production deployment. |
| Parser tests currently use generated sanitized XLSX workbooks, not the controlled customer workbook. | Create and approve customer-safe sanitized fixtures that mirror the observed workbook structure before production parser validation. |
| D4 is still not integrated as the external certificate-number source. | Keep the internal sequence as the approved interim source and add a D4 adapter only when interface requirements are known. |
| Audit actor identity is accepted as a user ID string only. | Add user repository/session integration before exposing API endpoints. |
| Test evidence is local and ignored by Git. | Keep generated validation artifacts local until a controlled evidence-retention location is agreed. |
