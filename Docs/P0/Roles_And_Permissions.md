# Roles And Permissions

## Roles

| Role | Description |
|---|---|
| Operator | Creates jobs, enters data, imports files, selects windows, runs calculations, submits for review. |
| Technical Reviewer | Reviews measurement selection, equipment traceability, and calculation summary. |
| QA Approver | Reviews compliance, certificate readiness, audit trail, and release decision. |
| Admin | Manages users, roles, settings, templates, constants, and system configuration. |
| Read Only | Views released records and permitted history without making changes. |

One person may hold multiple roles in the system, but workflow rules may require reviewer independence for a specific certificate.

## Permission Matrix

| Action | Operator | Technical Reviewer | QA Approver | Admin | Read Only |
|---|---:|---:|---:|---:|---:|
| Create calibration job | Yes | Yes | No | Yes | No |
| Edit draft job metadata | Yes | Yes | No | Yes | No |
| Upload/import measurement file | Yes | Yes | No | Yes | No |
| Enter manual readings | Yes | Yes | No | Yes | No |
| Select measurement windows | Yes | Yes | No | Yes | No |
| Run calculation | Yes | Yes | No | Yes | No |
| Submit for technical review | Yes | Yes | No | Yes | No |
| Approve technical review | No | Yes | No | Yes | No |
| Approve QA release | No | No | Yes | Yes | No |
| Release certificate | No | No | Yes | Yes | No |
| Revise released certificate | No | No | Yes | Yes | No |
| Void certificate | No | No | Yes | Yes | No |
| View audit trail | Limited | Yes | Yes | Yes | Limited |
| Create constants | No | No | No | Yes | No |
| Approve constants | No | No | Yes | Yes | No |
| Create uncertainty budget | No | Yes | No | Yes | No |
| Approve uncertainty budget | No | No | Yes | Yes | No |
| Manage users and roles | No | No | No | Yes | No |

## Separation Of Duties

Default rule:

- The same user may create and calculate a draft.
- Technical review should be performed by a user other than the operator when possible.
- QA release approval must be performed by an authorized QA Approver.
- Any exception must be explicitly audited with reason.

## Security Test Requirements

Every permission in the matrix requires automated tests for:

- Authorized access succeeds.
- Unauthorized access fails.
- Inactive users cannot act.
- Released records cannot be modified by normal edit paths.
- Audit records are visible only to permitted roles.

