# P1 Closeout

Status: complete for the backend foundation milestone.

This closes P1 as the controlled backend foundation approved after P0. It does not close the full temperature certificate MVP.

## Completed Foundation

| Area | Status |
|---|---|
| Test framework and CI skeleton | Complete |
| Quarterly scheduled regression trigger | Complete |
| Core domain entities | Complete |
| Workflow state machine | Complete |
| Role and permission matrix | Complete |
| Audit event model | Complete |
| Audit-aware workflow service boundary | Complete |
| Reference equipment traceability checks | Complete |
| Constant-set and budget version locks | Complete |
| Common calculation primitives | Complete |
| CMC lookup and floor rules | Complete |
| AB11 reporting rounding | Complete |
| Measurement-point calculation summary model | Complete |
| Immutable certificate/export/revision record skeleton | Complete |
| Controlled fixture classification and parser-contract tests | Complete |

## Intentionally Deferred

These are outside the P1 backend foundation scope and should start in the next implementation phase:

- FastAPI endpoints.
- Database schema, migrations, and repositories.
- Full KAYE / ValProbe RT XLSX parser.
- Verification PDF table extraction.
- Production temperature certificate calculation workflow.
- Certificate PDF generation and visual template matching.
- Frontend wizard and review screens.
- Database-backed audit transactions.
- Sanitized CI fixtures for controlled example-file regression.

## Closeout Assessment

P1 establishes the controlled objects and rules needed before production workflow implementation:

- Raw and parsed data can be traced to source file evidence.
- Measurement windows are explicit and validated.
- Equipment suitability is checked before release.
- Constants and uncertainty budgets require approved version locks.
- Measurement summaries retain raw values, CMC floor, reporting values, and version references.
- Released certificate records are immutable and tied to export artifact checksums.
- Workflow transitions have audit evidence.

## Remaining Risks And Recommended Solutions

| Risk | Recommended solution |
|---|---|
| Controlled customer/example files cannot run in default CI. | Create sanitized XLSX/PDF fixtures before implementing full parser regression in CI. |
| No database-backed audit transaction exists yet. | Implement persistence repositories and transactional audit writes early in the next phase before API endpoints. |
| No production parser exists yet. | Select boring, testable XLSX/PDF dependencies and implement parser behind existing contract tests. |
| No full temperature certificate calculation workflow exists yet. | Build from first-principles worked examples using GUM/AB11, with every formula covered before certificate rendering. |
| No certificate rendering exists yet. | Add rendering only after calculation summaries and release records are stable, so rendering consumes locked data and does not recalculate. |

## Recommended Next Phase

Start the temperature certificate workflow implementation:

1. Persistence model and repositories for P1 domain objects.
2. Transactional audit write path.
3. Parser dependency selection and sanitized fixture creation.
4. XLSX calibration parser behind contract tests.
5. Verification PDF IRTD parser behind contract tests.
6. First-principles temperature calculation worked examples.
