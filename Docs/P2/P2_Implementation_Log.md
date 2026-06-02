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
- Transactional ValProbe import orchestration service that records uploaded-file evidence, parsed readings, and parser audit evidence together.
- Sanitized fixture governance note for CI-safe parser development.
- Verification IRTD table parser for already-extracted table rows.
- Verification IRTD parser uses the column immediately after `Time` as the reference column.
- Temperature import alignment helper links logger readings to IRTD reference readings by exact timestamp.
- Temperature import alignment records warnings for missing IRTD references and unit mismatches.
- Temperature import alignment rejects duplicate IRTD timestamps as ambiguous.
- Linked ValProbe import orchestration persists calibration XLSX evidence, verification PDF evidence, raw logger readings, raw IRTD readings, parser audit evidence, and alignment audit evidence in one transaction.
- Linked ValProbe import orchestration returns workbook parser, verification parser, and timestamp alignment warnings for import review.
- Linked ValProbe import orchestration rejects calibration and verification files from different jobs before parsing or persistence.
- Domain model for linked temperature readings that requires matching timestamp, DUT channel, and unit.
- SQLite persistence for immutable linked logger/IRTD temperature readings.
- Linked ValProbe import orchestration persists linked logger/IRTD pairs in the same transaction as raw readings and audit evidence.
- Database triggers reject linked logger/IRTD reading update and delete operations.
- Controlled temperature measurement-window selection service from persisted linked logger/IRTD readings.
- Temperature window selection filters linked readings by DUT channel and inclusive timestamp range.
- Temperature window selection persists the DUT indication readings as a selected measurement window and returns the paired IRTD references for review.
- Temperature window selection records `measurement_window_changed` audit evidence with setpoint, unit, selected range, channel, and linked-reading count.
- Temperature window selection rejects requests before the `data_entered` workflow state.
- Temperature window completion gate transitions jobs from `data_entered` to `windows_selected` only when every DUT on the job has at least one selected window.
- Temperature window completion records the existing workflow-transition audit evidence in the same transaction as the state update.

## Scope Not Implemented

- No production database migration toolchain yet.
- No API endpoints.
- No user/session persistence.
- No parser result orchestration around the uploaded-file, DUT, reading, or measurement-window repositories.
- No controlled-file parser regression in default CI until sanitized customer-safe fixtures are approved.
- No production PDF text/table extraction dependency yet.
- No D4 certificate-number adapter yet.
- No certificate result calculation from linked logger/IRTD readings yet.
- No automatic plateau/stability window suggestion yet.
- No automatic transition from `data_entered` to `windows_selected` immediately after selecting an individual window; completion remains an explicit service action.
- No required setpoint-plan model yet, so window completeness currently checks DUT coverage only.

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
- ValProbe import orchestration records `parser_result_recorded` audit evidence with parser version, reading count, and warning count.
- Verification PDF file extraction remains explicitly deferred until a dependency is approved; the implemented parser only handles sanitized/extracted table rows.
- Temperature import alignment does not calculate errors, averages, uncertainty, or certificate results.
- Temperature import alignment preserves the original logger and IRTD reading objects so source-row and source-column traceability remains available downstream.
- Temperature import alignment does not convert units silently; unit mismatches are reported as warnings and skipped until an approved conversion rule exists.
- Linked ValProbe import orchestration records an `import_alignment_recorded` audit event on the calibration job with file IDs, linked-reading count, and alignment-warning count.
- Linked ValProbe import orchestration keeps calibration XLSX and verification PDF evidence separate so each parsed reading remains traceable to its own uploaded file.
- Linked logger/IRTD pairs preserve both original source locations and raw values; they do not calculate error of indication, mean values, uncertainty, or reported results.
- Linked logger/IRTD persistence rejects source files from another calibration job at database level.
- Temperature window selection does not calculate mean reference, mean indication, standard deviation, uncertainty, error of indication, or reported certificate results.
- Temperature window selection requires the selected DUT to belong to the job and match the selected logger channel.
- Temperature window selection is allowed only after source data is entered/imported, keeping workflow ordering explicit.
- Temperature window completion does not classify stability or calculate results; it only checks selected-window coverage and records the workflow transition.
- Temperature window completion currently requires at least one selected window per DUT because required setpoints are not modeled yet.

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
- Focused ValProbe import orchestration suite: 3 passed on Python 3.12.10.
- Import orchestration, parser, parsed-reading, and controlled-fixture contract suite: 13 passed, 2 skipped on Python 3.12.10.
- Default regression suite after ValProbe import orchestration slice: 159 passed, 2 skipped on Python 3.12.10.
- Focused verification IRTD table and controlled-fixture contract suite: 8 passed, 2 skipped on Python 3.12.10.
- Default regression suite after verification IRTD table parser slice: 164 passed, 2 skipped on Python 3.12.10.
- Focused temperature reading alignment suite: 4 passed on Python 3.12.10.
- Import parser and alignment suite: 16 passed on Python 3.12.10.
- Default regression suite after temperature reading alignment slice: 168 passed, 2 skipped on Python 3.12.10.
- Focused linked ValProbe import orchestration suite: 7 passed on Python 3.12.10.
- Import parser, alignment, and controlled-fixture contract suite: 23 passed, 2 skipped on Python 3.12.10.
- Default regression suite after linked ValProbe import orchestration slice: 172 passed, 2 skipped on Python 3.12.10.
- Focused linked temperature reading domain, persistence, and service suite: 30 passed on Python 3.12.10.
- Persistence, import, alignment, and controlled-fixture contract suite: 43 passed, 2 skipped on Python 3.12.10.
- Default regression suite after linked temperature reading persistence slice: 177 passed, 2 skipped on Python 3.12.10.
- Focused temperature measurement-window selection suite: 7 passed on Python 3.12.10.
- Source-data, workflow, and temperature window-selection suite: 39 passed on Python 3.12.10.
- Default regression suite after temperature measurement-window selection slice: 184 passed, 2 skipped on Python 3.12.10.
- Focused temperature window completion and selection suite: 11 passed on Python 3.12.10.
- Source-data, workflow, and temperature window-completion suite: 37 passed on Python 3.12.10.
- Default regression suite after temperature window-completion gate slice: 188 passed, 2 skipped on Python 3.12.10.
- JUnit XML evidence was generated at `Docs/Validation/evidence/latest/pytest.xml`.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| SQLite schema is currently initialized directly, not via controlled migrations. | Add a migration/version table or Alembic/SQL migration runner before production deployment. |
| Parser tests currently use generated sanitized XLSX workbooks, not the controlled customer workbook. | Create and approve customer-safe sanitized fixtures that mirror the observed workbook structure before production parser validation. |
| Verification PDF table extraction dependency is not approved yet. | Keep file-level extraction blocked and add a small dependency-selection review before implementing PDF text/table extraction. |
| Logger and IRTD alignment currently requires exact timestamps. | Keep exact matching as the default compliance-safe rule and add a council-reviewed tolerance/window rule only if real verification exports show timestamp drift. |
| Window completion does not yet determine whether all required setpoint windows are complete. | Add a required setpoint-plan model before multi-setpoint calculation runs consume windows. |
| Window selection is manual timestamp-range only. | Keep manual selection as the validated default and add automatic stable-window suggestion later with transparent thresholds and review/override evidence. |
| D4 is still not integrated as the external certificate-number source. | Keep the internal sequence as the approved interim source and add a D4 adapter only when interface requirements are known. |
| Audit actor identity is accepted as a user ID string only. | Add user repository/session integration before exposing API endpoints. |
| Test evidence is local and ignored by Git. | Keep generated validation artifacts local until a controlled evidence-retention location is agreed. |
