# Domain Model And Workflow

## Core Entities

| Entity | Purpose |
|---|---|
| User | Authenticated person with role, active status, and approval metadata. |
| Client | Customer identity and contact details. |
| CalibrationJob | Controlled work package for one calibration activity. |
| DeviceUnderTest | Calibrated item or logger/channel under the job. |
| UploadedFile | Stored raw input file with checksum and parser metadata. |
| Reading | Parsed measurement value with source traceability. |
| MeasurementWindow | Selected reading range for a setpoint and DUT/channel. |
| MeasurementPoint | Calculated result row for a certificate. |
| ReferenceEquipment | Equipment used to establish traceability. |
| ConstantSet | Versioned CMC, MPE, bath, pressure, and barometer constants. |
| UncertaintyBudget | Versioned and approved uncertainty method/budget. |
| UncertaintyContribution | Input component for uncertainty calculation. |
| Certificate | Controlled customer-facing certificate record. |
| ExportArtifact | Generated PDF/XLSX or validation artifact with checksum. |
| AuditEvent | Append-only evidence of regulated changes. |

## Calibration Job States

```text
draft
metadata_complete
equipment_selected
data_entered
windows_selected
calculated
technical_review
qa_review
approved
released
revised
voided
```

## State Transition Rules

| From | To | Required conditions |
|---|---|---|
| `draft` | `metadata_complete` | Required job metadata present. |
| `metadata_complete` | `equipment_selected` | Reference equipment selected and traceable. |
| `equipment_selected` | `data_entered` | Manual readings or uploaded/imported readings available. |
| `data_entered` | `windows_selected` | Required measurement windows selected or manual values confirmed. |
| `windows_selected` | `calculated` | Calculation run completes without blocking errors. |
| `calculated` | `technical_review` | Operator submits calculation summary for review. |
| `technical_review` | `qa_review` | Reviewer approves technical content. |
| `qa_review` | `approved` | QA/compliance approver approves release. |
| `approved` | `released` | Certificate artifact generated and locked. |
| `released` | `revised` | New revision created with reason and audit event. |
| any non-released state | `voided` | Authorized user voids with reason. |

Released certificates must not be edited in place.

## Blocking Conditions

The system must block approval/release when:

- Required metadata is missing.
- Required reference equipment is missing.
- Selected equipment is overdue, inactive, or outside approved range.
- CMC is missing or out of range.
- Calculation produced warnings classified as blocking.
- Required uncertainty budget is missing or not approved.
- Required reviewer/approver separation is violated.
- Audit reason is required but missing.
- Certificate preview/export validation fails.

## Audit Requirements

Audit events are required for:

- Job creation.
- Metadata changes.
- File upload.
- Parser selection and parse result.
- Manual reading entry or edit.
- Measurement window selection or change.
- Calculation run.
- Constant-set creation, change, approval, retirement.
- Budget creation, change, approval, retirement.
- Technical review.
- QA approval.
- Certificate release.
- Certificate revision.
- Certificate voiding.
- Export artifact generation.

Audit events must include:

- Entity type and id.
- Action.
- Authenticated user.
- Timestamp.
- Previous value where applicable.
- New value where applicable.
- Reason where applicable.
- Software version.
- Calculation-engine version where applicable.
- Constant-set and budget version where applicable.

