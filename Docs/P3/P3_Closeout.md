# P3 Closeout

Status: complete for the backend production-control and API-readiness milestone.

P3 closes the control layer that must exist before certificate rendering or broader workflow UI work: authenticated actors, role-controlled service boundaries, audited user administration, controlled schema bootstrap, API request lifecycle, certificate preview, and release gating.

## Completed P3 Scope

| Area | Status |
|---|---|
| User account and session persistence | Complete |
| Session-backed authenticated actor resolution | Complete |
| Session-backed wrappers for regulated temperature window and calculation actions | Complete |
| Controlled SQLite migration runner | Complete |
| Controlled SQLite baseline schema bootstrap for persistent API databases | Complete |
| Certificate preview model and service consuming locked calculation summaries | Complete |
| Certificate release gate requiring approved state and matching preview audit evidence | Complete |
| Immutable certificate/export artifact release evidence | Complete |
| Audited user-management service for create, role change, deactivate, and session revoke | Complete |
| FastAPI app factory, settings, scoped SQLite connection lifecycle, and endpoint tests | Complete |
| API endpoints for health, actor identity, certificate preview, and certificate release | Complete |

## Compliance Impact

- P3 does not change calculation formulas, CMC rules, uncertainty budgets, or reported result values.
- Regulated API-facing actions now resolve the authenticated actor from a session instead of accepting free-form user IDs.
- Certificate release is blocked unless the job is approved and a preview audit event matches the current summary IDs, template version, software version, calculation engine version, constant-set version, and budget version.
- User creation, role changes, deactivation, and session revocation now have service-level audit evidence with previous/new values and reasons where required.
- Persistent API databases use a controlled baseline schema bootstrap. Future schema changes must be explicit controlled migrations with checksum evidence.

## Intentionally Deferred To P4 Or Later

- PDF/XLSX rendering and storage of actual exported bytes.
- Visual matching against the approved certificate template.
- UI screens and frontend workflow.
- Admin API endpoints for user management.
- Password, MFA, SSO, or Azure/M365 identity-provider integration.
- D4 certificate-number and equipment-data adapter.
- Dedicated persisted preview table, unless template validation requires retaining preview payloads beyond audit evidence.
- Host/port/storage/identity runtime settings beyond `SIMVAL_DATABASE_PATH`.

## P4 Entry Recommendation

Start P4 with certificate rendering and export artifact generation:

1. Define the controlled renderer contract that consumes released preview/calculation data without recalculation.
2. Add tests for generated PDF/XLSX metadata, checksum creation, storage URI handling, and template version locking.
3. Implement a minimal certificate renderer/exporter that produces controlled artifact bytes.
4. Validate the generated output against the approved SIMVal certificate structure before extending UI scope.

Do not implement UI-driven release until rendered artifact generation and checksum evidence are validated.

## Verification

- P3 closeout default regression suite: 275 passed, 2 skipped on Python 3.12.10.
- The two skipped tests are controlled example-file tests that remain disabled for default CI unless controlled fixture execution is explicitly approved.
