# Architecture And Repository Structure

## Architecture Principles

- The frontend must never contain authoritative calculation formulas.
- The calculation engine must be pure, deterministic, independently testable, and versioned.
- Released certificates must be reproducible from stored inputs, selected measurement windows, constants version, budget version, calculation-engine version, and rendering template version.
- Audit, approval, traceability, and versioning behavior are core domain behavior, not optional logging.
- D4 is deferred and must be represented as a future integration boundary, not as a required dependency.

## Proposed Repository Structure

```text
app/
  backend/
    api/
    auth/
    audit/
    certificates/
    domain/
    imports/
    persistence/
    services/
  calculation_engine/
    cmc/
    common/
    pressure/
    rounding/
    temperature/
    uncertainty/
  frontend/
    components/
    routes/
    services/
    state/
  tests/
    compliance/
    e2e/
    fixtures/
    integration/
    regression/
    unit/
Docs/
  Decisions/
  P0/
  Validation/
scripts/
  ci/
  validation/
  test_reports/
```

The physical casing may be adapted to the selected stack, but these boundaries must remain visible.

## Module Responsibilities

| Module | Responsibility |
|---|---|
| `backend/api` | HTTP/API contracts, request validation, response models. |
| `backend/auth` | Authentication, roles, permission checks, session/user context. |
| `backend/audit` | Append-only audit event creation and retrieval. |
| `backend/certificates` | Certificate lifecycle, artifact references, rendering orchestration. |
| `backend/domain` | Domain entities, value objects, workflow state rules. |
| `backend/imports` | File metadata, parser orchestration, raw-file checksum handling. |
| `backend/persistence` | Database models, repositories, transaction boundaries. |
| `backend/services` | Use-case orchestration and workflow transitions. |
| `calculation_engine` | Pure calculation functions and calculation result models. |
| `frontend` | User workflow, review screens, warnings, and certificate preview. |
| `tests` | Automated test suites and fixtures. |
| `docs/validation` | Validation plans, reports, and retained evidence templates. |
| `scripts/validation` | Validation report generation and scheduled regression tooling. |

## Dependency Rules

- Frontend may call backend APIs, but may not duplicate calculation rules.
- Backend services may call the calculation engine.
- Calculation engine must not depend on database, web framework, UI code, or mutable global state.
- Audit event creation must be part of workflow transactions for regulated changes.
- Certificate rendering must consume approved domain data and calculation summaries, not recalculate silently.

## First Implementation Milestone

The first implementation milestone after P0 is:

1. Automated test framework and CI skeleton.
2. Core domain models and workflow state machine.
3. Roles and permission checks.
4. Calculation-engine interfaces with failing tests written first.
5. Audit event model and immutable released-record strategy.

Production calculation formulas are not implemented until their test cases and worked examples are approved.
