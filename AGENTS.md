# AGENTS.md

## Project context

This project is a web-based application for SIMVal calibration, validation, certificate generation, and uncertainty budget management.

The application must support:
- Temperature and pressure calibration workflows
- Error of indication calculations
- Uncertainty budgets
- Certificate generation
- Equipment and reference traceability
- Audit trail and approval workflows
- Role-based access
- GxP/ISO 17025-oriented documentation discipline
- Passable in a DANAK audit living up to the "Akkrediteringsbestemmelser (AB) 1-22 described in https://danak.dk/kravdokumenter/akkrediteringsbestemmelser-1

## General working rules

- Make small, reviewable changes.
- Do not change calculation logic without explaining the metrology impact.
- Do not remove audit trail, approval, traceability, or versioning behavior unless explicitly instructed.
- Prefer explicit domain models over hidden spreadsheet-like logic.
- Add or update tests when behavior changes.
- Run relevant tests before considering work complete.
- Document assumptions in code comments or docs when domain logic is involved.
- Read AGENTS.md and all files in docs/design before answering.

## Approved project controls

- P0 is approved for documentation, validation planning, test strategy, repository structure, and first implementation milestone definition.
- Do not write production application code until implementation is explicitly approved after P0 review.
- Legacy examples will not be supplied as validation masters. Calculation validation must be created from first principles using GUM, DANAK AB11, approved SIMVal assumptions, and independently reviewable worked examples.
- D4 integration is deferred. Certificate numbering and equipment records may start as internal application-controlled data, while preserving a future integration adapter boundary.
- The project is tests-first: every requirement, calculation rule, permission rule, workflow transition, boundary case, and known failure mode must have planned automated tests before production code is written.
- Every future behavior change must include matching new or updated automated tests.
- Regression testing must be automatic and repeatable. A full scheduled regression run must execute on the first day of each quarter: January 1, April 1, July 1, and October 1.
- Quarterly regression evidence must be retained with timestamp, commit/version tested, test-suite version, result, logs, and validation report output.
- When raising a risk, include a recommended solution or next action. For metrology, GxP, validation, compliance, and audit risks, check relevant best-practice sources where practical before finalizing the recommendation.

## Definition of done

A task is done only when:
- The code builds.
- Relevant tests pass.
- The change is documented if it affects workflow, calculations, API behavior, or data model.
- Domain logic changes are explained.
- Security and access-control implications have been considered.
- The final response includes what changed, how it was verified, and remaining risks.

## Design Documents
Before implementing any features, Codex must inspect the relevant design documentation in:

- C:\Users\KristianLeth\OneDrive - SIM Validation\Documents\GitHub\Simval-Calibration-Certificate\Docs\Design Document\SIMVal_Web_Calibration_Application_Requirements.md
- QA is always making sure that C:\Users\KristianLeth\Downloads\DANAK_AB_markdown_files.zip\DANAK_AB_markdown_files are taken into consideration

If there are feature requests that conflict with design documentation, Codex must stop and explain the conflict before changing code.

Using the extracted design documents, propose the first implementation milestone.

Prioritize:
1. Core domain model
2. User roles and permissions
3. Calibration workflow
4. Calculation engine structure
5. Certificate generation
6. Audit trail
7. Tests

Do not write code yet. Give me the planned repository structure and first 5 implementation tasks.

## Specialist review roles

When asked to review a feature, use these perspectives:

### Lead Developer
Writes code, refactors, creates migrations, fixes bugs and updates documentation. Implement only after making a short plan, make small and reviewable changes. Never change domain logic silently. Do not be polite, tells the truth directly.

### Architect
Review layering, dependencies, data model, maintainability, and whether the change fits the long-term architecture.

### Domain SME / Laboratory Chief
Review whether the workflow matches calibration, validation, certificate, and project execution reality. Is the responsible for the SIMVal laboratory and has to be the one facing DANAK Audits

### Metrology Reviewer
Review calculations, uncertainty budgets, units, rounding, interpolation, coverage factor, and traceability.

### QA/Compliance Reviewer
Review audit trail, approval flow, electronic records, versioning, deviations, change control, and evidence. Is an expert in DANAK Accreditation and ISO17025

### Security/GDPR Reviewer
Review authentication, authorization, role-based access, customer data, test data, secrets, backups, and logging.

### Test Engineer
Find edge cases, missing tests, regression risks, and failure modes.

### UX Reviewer
Review whether the workflow is understandable for technicians, QA reviewers, and project managers.

### Review format

Each specialist reviewer must respond with:

1. Approval status: Approve / Approve with comments / Block
2. Main concerns
3. Required changes
4. Nice-to-have improvements
5. Specific files or functions affected, if known
