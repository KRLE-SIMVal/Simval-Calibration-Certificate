# Test Case Catalog

This catalog lists the initial automated test cases that must exist before or with production code.

The catalog must expand whenever requirements, calculations, workflows, or risks are added.

## Domain And Workflow

| Test ID | Purpose | Expected result |
|---|---|---|
| DOM-001 | Create calibration job with minimum valid metadata. | Job is created in `draft`. |
| DOM-002 | Reject job without required client. | Validation error. |
| DOM-003 | Reject invalid discipline. | Validation error. |
| DOM-003A | Reject invalid measurement mode. | Validation error. |
| DOM-004 | Create DUT with make/model/serial. | DUT linked to job. |
| DOM-005 | Reject duplicate DUT serial within same batch when not allowed. | Validation error or explicit batch rule. |
| DOM-006 | Job/domain timestamps are timezone-aware. | Naive timestamps are rejected where regulated timestamps are stored. |
| WF-001 | Wizard next/back preserves draft values. | Values remain unchanged. |
| WF-002 | Resume draft after interruption. | Draft loads with same state and data. |
| WF-003 | Invalid step cannot advance. | Blocking validation shown. |
| WF-010 | Select temperature discipline. | Temperature branch enabled. |
| WF-011 | Select pressure discipline. | Pressure branch enabled. |
| WF-012 | Select differential pressure discipline. | Differential branch enabled. |
| WF-020 | Manual mode requires manual readings. | Missing manual readings block calculation. |
| WF-021 | Automatic mode requires imported or parsed readings. | Missing readings block calculation. |
| WF-030 | Certificate metadata complete moves state. | State becomes `metadata_complete`. |
| WF-040 | Export before preview is blocked. | Export rejected and audited if attempted. |
| WF-050 | Workflow transition service records audit event. | State change and software version are captured in audit evidence. |
| WF-051 | Void/revision transition requires reason. | Transition is rejected without reason. |
| WF-052 | Invalid workflow state type at service boundary. | Transition is rejected with service validation error. |

## Roles And Permissions

| Test ID | Purpose | Expected result |
|---|---|---|
| RBAC-001 | Operator can create draft job. | Allowed. |
| RBAC-002 | Read Only cannot create draft job. | Denied. |
| RBAC-003 | Operator can enter readings. | Allowed. |
| RBAC-004 | QA Approver cannot silently edit readings in review. | Denied or requires controlled revision path. |
| RBAC-005 | Technical Reviewer can approve technical review. | Allowed. |
| RBAC-006 | Operator cannot approve own technical review by default. | Denied or exception requires audit. |
| RBAC-007 | QA Approver can release certificate. | Allowed. |
| RBAC-008 | Operator cannot release certificate. | Denied. |
| RBAC-009 | Admin can manage roles. | Allowed. |
| RBAC-010 | Inactive user cannot perform regulated action. | Denied. |
| RBAC-011 | Unauthorized user cannot view restricted audit trail. | Denied. |
| RBAC-012 | Read Only can view released certificate when permitted. | Allowed. |

## Statistics And Calculation Common

| Test ID | Purpose | Expected result |
|---|---|---|
| STAT-001 | Mean of positive readings. | Correct arithmetic mean. |
| STAT-002 | Mean of negative readings. | Correct arithmetic mean. |
| STAT-003 | Sample standard deviation uses n-1. | Correct sample stdev. |
| STAT-004 | Standard uncertainty of mean. | `stdev.s / sqrt(n)`. |
| STAT-005 | One reading cannot produce sample stdev. | Method-specific warning or block. |
| STAT-006 | Min/max retained for selected window. | Correct min/max. |
| CALC-001 | Error of indication common rule. | `indication - reference`. |
| CALC-002 | Raw values retained at full precision. | Stored raw values equal inputs. |
| CALC-003 | Calculation summary includes components. | Summary is independently recalculable. |
| CALC-004 | Calculation engine version is recorded. | Version stored with calculation run. |
| CALC-005 | Calculation summary records constant-set and budget versions. | Version references are present and immutable. |
| CALC-006 | Calculation summary protects the applicable CMC floor. | Reported U is never below CMC after reporting rounding. |
| CALC-007 | Two-significant-digit U uses normal AB11 rounding. | Rounded U may round down when still above CMC. |

## Temperature

| Test ID | Purpose | Expected result |
|---|---|---|
| TEMP-001 | Example: R 0.000, I -0.010, U 0.010. | Error -0.010, displayed -0.01 +/- 0.01 deg C. |
| TEMP-002 | Example: R -90.032, I -90.130, U 0.010. | Error -0.098, displayed -0.10 +/- 0.01 deg C. |
| TEMP-003 | Negative reference and less negative indication. | Correct positive/negative sign. |
| TEMP-004 | Zero crossing readings. | Mean and error correct. |
| TEMP-010 | Automatic mode reference mean. | R equals mean of selected reference readings. |
| TEMP-011 | Automatic mode DUT mean. | I equals mean of selected DUT readings. |
| TEMP-012 | Automatic mode repeatability. | Type A terms computed from selected windows. |
| TEMP-020 | DUT resolution contribution. | `(resolution / 2) / sqrt(3)`. |
| TEMP-021 | Reference expanded uncertainty conversion. | `u = U / k`. |
| TEMP-022 | Bath expanded uncertainty conversion. | `u = U / k`. |
| TEMP-030 | Manual indication used as I. | Error uses manual indication. |
| TEMP-031 | Manual mode missing indication. | Calculation blocked. |
| TEMP-040 | U below CMC. | Reported U raised to CMC floor. |
| TEMP-041 | Missing CMC. | Approval/export blocked. |
| TEMP-042 | Reference outside CMC range. | Approval/export blocked. |

## Pressure

| Test ID | Purpose | Expected result |
|---|---|---|
| PRESS-001 | Common pressure error rule. | `indication - reference_pressure`. |
| PRESS-010 | Manual gauge pressure up/down average. | Indication average used where method requires. |
| PRESS-011 | Gauge pressure omits barometer by default. | No barometer contribution. |
| PRESS-020 | Automatic pressure reference mean. | Reference pressure mean computed. |
| PRESS-021 | Automatic pressure DUT mean. | DUT pressure mean computed. |
| PRESS-030 | Absolute pressure includes barometer. | Barometer contribution present. |
| PRESS-031 | Missing barometer for absolute mode. | Calculation or approval blocked. |
| PRESS-040 | Differential pressure unit mismatch. | Calculation blocked. |
| PRESS-041 | Differential pressure range mismatch. | Approval/export blocked. |

## Uncertainty Budget

| Test ID | Purpose | Expected result |
|---|---|---|
| UB-001 | Select temperature certificate budget. | Correct required contribution family. |
| UB-010 | Contribution requires name/value/unit/source. | Missing required field rejected. |
| UB-011 | Contribution requires distribution or divisor. | Missing uncertainty model rejected. |
| UB-020 | Combine independent standard uncertainties. | RSS result correct. |
| UB-021 | Sensitivity coefficient applied. | Effective contribution uses `abs(c) * u`. |
| UB-030 | Normal expanded uncertainty conversion. | `u = U / k`. |
| UB-031 | Rectangular distribution conversion. | `u = a / sqrt(3)`. |
| UB-032 | Triangular distribution conversion. | `u = a / sqrt(6)`. |
| UB-033 | U-shaped distribution conversion. | `u = a / sqrt(2)`. |
| UB-040 | Approved budget cannot be edited in place. | Revision required. |
| UB-041 | Certificate links to approved budget version. | Link stored and immutable after release. |
| UB-042 | Approved budget requires approval evidence. | Approver and approval timestamp are required. |
| UB-043 | Budget links to a constant-set version. | Missing linked constant-set version is rejected. |
| UB-060 | Required contribution missing. | Warning or block according to method rule. |

## Constant Sets And Version Locks

| Test ID | Purpose | Expected result |
|---|---|---|
| CONST-001 | Approved constant set requires approval evidence. | Approver and approval timestamp are required. |
| CONST-002 | Draft constant set cannot be used for release. | Release blocker is returned. |
| CONST-003 | Missing approved constant set. | Approval/export blocked. |
| CONST-004 | Budget linked constant version differs from selected constant set. | Approval/export blocked. |
| CONST-005 | Budget discipline differs from selected constant set. | Approval/export blocked. |

## CMC And Rounding

| Test ID | Purpose | Expected result |
|---|---|---|
| CMC-001 | U calculated below CMC. | U after CMC equals CMC or higher after rounding. |
| CMC-002 | U calculated above CMC. | U after CMC equals calculated U. |
| CMC-003 | Missing CMC table. | Approval/export blocked. |
| CMC-004 | Out-of-range CMC lookup. | Approval/export blocked. |
| CMC-005 | Boundary at lower range limit. | Correct CMC selected. |
| CMC-006 | Boundary at upper range limit. | Correct CMC selected. |
| CMC-007 | Linear segment midpoint. | Interpolated CMC equals approved linear result. |
| CMC-008 | Linear segment off-midpoint. | Interpolated CMC equals approved linear result. |
| CMC-009 | Discrete table without interpolation. | Worst-case CMC in interval is used. |
| CMC-010 | Formula CMC. | Formula result is used and versioned. |
| CMC-011 | Matrix CMC without interpolation. | Correct matrix cell is selected. |
| CMC-012 | Matrix interpolation without approval. | Approval/export blocked. |
| CMC-013 | Open interval CMC expression. | CMC entry rejected. |
| CMC-014 | Ambiguous PPM/PPB unit. | CMC entry rejected until unit scale is explicit. |
| CMC-015 | Overlapping ranges with clear specificity. | More specific CMC entry is selected. |
| CMC-016 | Overlapping ranges with equal specificity and conflict. | Approval/export blocked. |
| CMC-017 | Range gap. | Approval/export blocked. |
| CMC-018 | Display rounding below CMC. | Displayed U is rounded upward to remain >= CMC. |
| RND-001 | U reported with two significant digits. | Display value has max two significant digits. |
| RND-002 | Result rounded to least significant digit of U. | Result precision follows U. |
| RND-003 | Negative result rounding. | Correct sign and precision. |
| RND-004 | Small decimal U. | Leading zeros do not count as significant digits. |
| RND-005 | Rounding must not report U below CMC. | Displayed U remains >= CMC. |
| RND-006 | One significant digit uncertainty. | U is rounded upward per AB11. |
| RND-007 | More than two significant digits requested. | Reporting rounding rejects the request. |

## Import, Data Integrity, And Equipment

| Test ID | Purpose | Expected result |
|---|---|---|
| IMP-001 | Manual reading entry stores source as manual. | Source traceability stored. |
| IMP-002 | Known parser records parser version. | Parser version stored. |
| IMP-003 | Unknown format requires mapping. | Import not silently accepted. |
| IMP-020 | Uploaded raw file checksum stored. | Checksum matches file. |
| IMP-021 | Raw file is immutable. | Edit attempt denied. |
| IMP-022 | Uploaded raw file checksum format validated. | Non-SHA-256 values are rejected and valid digests are normalized. |
| IMP-023 | Uploaded raw file kind is controlled. | Unknown file-kind values are rejected. |
| IMP-040 | KAYE verification PDF table detection. | Parser contract identifies the table containing `Time`. |
| IMP-041 | KAYE verification PDF IRTD source column. | Parser contract treats the second column next to `Time` as IRTD/reference value. |
| IMP-042 | Linked XLSX/PDF timestamp alignment. | Logger readings can be matched to corresponding IRTD/reference readings or produce blocking warnings. |
| IMP-043 | Missing verification PDF for calibration requiring IRTD. | Calculation approval/export blocked. |
| IMP-044 | Verification PDF extraction failure. | Blocking parser warning and no silent fallback. |
| IMP-045 | IRTD value missing for a logger reading. | Blocking parser warning for affected row/channel. |
| IMP-046 | Sanitized ValProbe XLSX parser reads logger channels. | Parser returns timezone-aware readings with logger channel, value, unit, and source row/column. |
| IMP-047 | Sanitized ValProbe XLSX parser skips blank measurement cells. | Blank cells are ignored without creating readings. |
| IMP-048 | Sanitized ValProbe XLSX parser rejects missing Temperature sheet. | Parser raises a controlled parser error. |
| IMP-049 | Sanitized ValProbe XLSX parser reports nonnumeric measurement cells. | Parser records a warning and does not silently convert invalid values. |
| DATA-001 | Parsed reading stores source row/column where available. | Traceability stored. |
| DATA-002 | Parsed reading timestamp is timezone-aware. | Naive timestamps are rejected. |
| DATA-003 | Parsed reading value is finite. | NaN and infinite values are rejected. |
| EQ-001 | Create reference equipment. | Equipment stored with status and due date. |
| EQ-002 | Equipment due date in future. | Selection allowed. |
| EQ-003 | Reference equipment certificate reference missing. | Equipment record rejected. |
| EQ-004 | Reference equipment range inverted. | Equipment range rejected. |
| EQ-030 | Overdue equipment selected. | Approval/export blocked or warning per rule. |
| EQ-031 | Inactive equipment selected. | Approval/export blocked. |
| EQ-032 | Equipment range incompatible with point. | Approval/export blocked. |
| EQ-033 | Equipment unit incompatible with point. | Approval/export blocked. |
| EQ-034 | Equipment discipline incompatible with point. | Approval/export blocked. |
| EQ-035 | Multiple equipment suitability failures. | All applicable blockers are returned in deterministic order. |

## Measurement Windows

| Test ID | Purpose | Expected result |
|---|---|---|
| WIN-001 | Selected window contains readings from one channel only. | Mixed channels are rejected. |
| WIN-002 | Selected window contains readings in one unit only. | Mixed units are rejected. |
| WIN-003 | Selected window contains at least one reading. | Empty window is rejected. |
| WIN-004 | Selected window readings are chronological. | Non-chronological readings are rejected. |
| WIN-005 | Selected window exposes start/end timestamps and reading count. | Traceable summary values are available. |

## Certificate, Audit, Validation, And Regression

| Test ID | Purpose | Expected result |
|---|---|---|
| CERT-001 | Allocate internal certificate number. | Unique sequential or configured value. |
| CERT-002 | Prevent duplicate certificate number. | Duplicate rejected. |
| CERT-003 | Allocate next number from internal sequence. | Number uses configured prefix and zero padding, then increments the stored next value. |
| CERT-004 | Allocate number from missing sequence. | Allocation is rejected until the sequence is configured. |
| CERT-005 | Configure invalid internal sequence. | Blank prefix, non-positive next value, and invalid padding are rejected. |
| CERT-020 | One artifact per DUT. | Correct artifact count. |
| CERT-021 | Combined batch summary. | Summary references all DUTs. |
| CERT-030 | Preview required before export. | Export blocked without preview. |
| CERT-050 | Released certificate tied to constants version. | Later constants changes do not alter released record. |
| CERT-051 | Released certificate tied to uncertainty budget version. | Later budget changes do not alter released record. |
| CERT-052 | Released certificate tied to calculation summary IDs. | Released record contains immutable calculation summary references. |
| CERT-053 | Released certificate tied to software, calculation engine, and template versions. | Version references are present and immutable. |
| CERT-100 | DANAK mark/reference area present when accredited. | Required text/logo placeholder present. |
| CERT-120 | Released PDF immutable. | Regeneration creates revision path. |
| CERT-121 | Export artifact checksum stored. | Artifact checksum is a valid SHA-256 digest. |
| CERT-122 | Released certificate requires export artifact. | Release record is rejected without artifact evidence. |
| CERT-123 | Certificate revision requires reason. | Revision record is rejected without reason and links original release. |
| AUD-001 | Job creation audit event. | Event includes user/timestamp/action. |
| AUD-002 | Metadata change audit event. | Previous and new values stored. |
| AUD-003 | Calculation run audit event. | Calculation version and inputs reference stored. |
| AUD-004 | Approval audit event. | Approver and timestamp stored. |
| AUD-005 | Release audit event. | Artifact checksum and version refs stored. |
| AUD-006 | Workflow transition audit event. | Previous and new workflow states are stored. |
| PERSIST-001 | Store and reload a calibration job. | Client, discipline, mode, state, and created timestamp round-trip unchanged. |
| PERSIST-002 | Store duplicate calibration job ID. | Duplicate is rejected and existing record is unchanged. |
| PERSIST-003 | Append audit events and read by entity. | Events are returned in append order with JSON values and version references preserved. |
| PERSIST-004 | Attempt to update or delete an audit event. | Database rejects mutation because audit events are append-only. |
| PERSIST-005 | Workflow transition persistence writes state and audit together. | Job state changes and exactly one audit event is appended in the same transaction. |
| PERSIST-006 | Invalid persisted workflow transition. | Job state remains unchanged and no audit event is appended. |
| PERSIST-007 | Stale workflow state update. | Update is rejected and persisted state remains unchanged. |
| PERSIST-008 | Store and reload uploaded-file evidence. | Filename, checksum, file kind, parser version, storage URI, and upload timestamp round-trip unchanged. |
| PERSIST-009 | Store uploaded file for unknown job. | Insert is rejected by referential integrity. |
| PERSIST-010 | Store and list DUT records for a job. | DUT identity fields round-trip unchanged and list in deterministic order. |
| PERSIST-011 | Store duplicate DUT identity in same job. | Duplicate job/serial/channel identity is rejected. |
| PERSIST-012 | Store and reload selected measurement window with readings. | Readings, source file IDs, source rows/columns, timestamps, and selected-window metadata round-trip unchanged. |
| PERSIST-013 | Store measurement window with unknown source file ID. | Insert is rejected by referential integrity. |
| PERSIST-014 | Store measurement window for unknown DUT. | Insert is rejected by referential integrity. |
| PERSIST-015 | Store and reload measurement-point calculation summary. | Raw values, rounded values, decimals, CMC floor, and version references round-trip unchanged. |
| PERSIST-016 | Store calculation summary for unknown measurement window. | Insert is rejected by referential integrity. |
| PERSIST-017 | Store and reload released certificate record. | Summary IDs, export artifacts, approval/release evidence, and version references round-trip unchanged. |
| PERSIST-018 | Store duplicate certificate number. | Duplicate certificate number is rejected. |
| PERSIST-019 | Mutate released certificate row directly. | Database rejects update/delete because released certificate records are immutable. |
| PERSIST-020 | Store released certificate with unknown calculation summary. | Insert is rejected by referential integrity. |
| PERSIST-021 | Store and reload certificate revision evidence. | Revision reason, original certificate link, user, and timestamp round-trip unchanged. |
| PERSIST-022 | Store and reload constant-set version record. | Discipline, status, effective date, and approval evidence round-trip unchanged. |
| PERSIST-023 | Store duplicate constant-set version. | Duplicate version is rejected. |
| PERSIST-024 | Store and reload uncertainty-budget version record. | Budget type, method, discipline, linked constant set, status, and approval evidence round-trip unchanged. |
| PERSIST-025 | Store budget linked to unknown constant-set version. | Insert is rejected by referential integrity. |
| PERSIST-026 | List approved constant and budget versions. | Only approved records are returned, ordered by version. |
| PERSIST-027 | Initialize SQLite schema. | Schema version marker is recorded once with a timezone-aware applied timestamp. |
| VAL-001 | Validation report generated from automated test run. | Report includes suite, version, result, evidence paths. |
| ENV-001 | Clean Python 3.12 environment installs project test dependencies. | `pip install -e .[test]` succeeds without packaging unrelated folders. |
| REG-001 | Quarterly schedule exists. | Cron/scheduler definition present when CI exists. |
| REG-002 | Quarterly run stores evidence. | Evidence artifact retained. |
| REG-003 | Regression failure creates issue/deviation. | Failure path records tracked item. |
