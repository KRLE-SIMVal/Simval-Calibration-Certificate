**SIMVal Web Calibration Application**

_Requirements & Design Brief_

| **Field**    | **Value**                                                                                                                        |
| ------------ | -------------------------------------------------------------------------------------------------------------------------------- |
| Version      | 0.2 Draft for developer meeting                                                                                                  |
| Prepared for | SIMVal / KRLE                                                                                                                    |
| Date         | 2026-05-21                                                                                                                       |
| Primary goal | Controlled web application for temperature and pressure calibration certificates and uncertainty budgets.                        |
| Source basis | Existing design document, certificate examples, GUM uncertainty principles, and EURAMET CG-13 for temperature block calibrators. |

**Meeting objective**

Agree the MVP scope, calculation engine boundaries, data model, import formats, validation approach, and whether the application should integrate with D4 for certificate numbers and equipment calibration data.

**Recommended meeting agenda**

- Confirm scope: temperature and pressure certificates + uncertainty budgets.
- Confirm web application architecture and hosting model.
- Walk through legacy process flow and required calculation replication.
- Define MVP import flow for ValProbe RT / Kaye data and manual entry.
- Agree validation expectations: unit tests, traceability, audit trail, and locked versions of constants.
- Resolve open questions: D4 integration, digital signatures, batch certificates, and approval workflow.

# 1\. Purpose and background

**Purpose.** This document describes the functional and technical requirements for a web based application that creates calibration certificates and uncertainty budgets for temperature and pressure calibrations.

| **Source document / artefact**                  | **How it is used in this design**                                                                                           |
| ----------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Design_dokument_Certifikatskabelon_SIMVal.docx  | Earlier requirements document used as the baseline structure for this web-focused document.                                 |
| Datafelter på certifikat.pdf                    | Example output showing certificate header, results table, uncertainty statement, and reference equipment pages.             |
| DFM calibration -80_08-Apr-2026 15-45-00_1.xlsx | Example ValProbe RT / Kaye source data for import and parsing rules.                                                        |
| JCGM 100:2008 / GUM                             | Reference principle for uncertainty calculation, uncertainty reporting, coverage factor, and reproducibility.               |
| EURAMET CG-13                                   | Reference for temperature block calibrator uncertainty components and distinction between calibration and characterisation. |
|                                                 |                                                                                                                             |

# 2\. Scope

The intended product is a controlled web application for internal SIMVal use. It shall support certificate creation, calculation, review, export, and storage. The calculation engine shall be reusable and testable independently from the user interface.

| **In scope for MVP / early releases**                                                                                   | **Out of scope unless explicitly decided**                                       |
| ----------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| Temperature calibration certificates from imported or manually entered data.                                            | Full LIMS replacement.                                                           |
| Pressure calibration certificates, including gauge, absolute, and differential pressure where legacy logic is verified. | Automatic digital signing with qualified certificates unless required by SIMVal. |
| Uncertainty budget editor and calculation engine for temperature and pressure workflows.                                | Public customer portal.                                                          |
| Reference equipment library and constants database replacing Certifikatkonstanter.                                      | Uncontrolled editing of released certificates.                                   |
| PDF certificate export and, where useful, XLSX export for uncertainty budgets.                                          | Direct cloud storage without defined access controls and retention rules.        |
| Batch handling of multiple loggers/channels from one run.                                                               | Changes to calculation logic without version control and validation.             |

# 3\. Project Timeline

The project is estimated to start in June, where an estimate for this Design Document is made

# 4\. Proposed web application process flow

The flow below keeps the same intent as the legacy workflow but moves all intermediate data into structured objects and all formulas into a dedicated calculation engine.

1. Job metadata

Client, certificate no., task no., procedure, language

2. Select discipline and method

Temperature / pressure / differential pressure Manual / automatic

3. Select reference equipment

Equipment validity, range check, constants version

4. Import or enter data

ValProbe RT / CSV / XLSX / manual entry

Raw file retained with checksum

( 5. Select measurement windows }

Setpoints, stable windows, logger/channel mappin g

6. Calculation engine

Reference, indication, error, uncertainty

CMC floor and rounding rules

y

7. Review and approval

Warnings, calculation summary, certificate preview

8. Generate PDF / XLSX

Certificate, annex, uncertainty budget

9. Store final record

Audit trail, raw data, PDF, software/constants version

_Figure 1. Proposed web application flow from calibration job creation to certificate export and history storage._

# 5\. Functional requirements

## 5.1 Application launch, navigation and roles

| **ID** | **Requirement**                                                                                                                              | **Priority** |
| ------ | -------------------------------------------------------------------------------------------------------------------------------------------- | ------------ |
| F-001  | The application shall be accessible as a web application through a secure browser session.                                                   | Must         |
| F-002  | The home screen shall provide at least: Create Certificate, Create Uncertainty Budget, Equipment Library, Certificate History, and Settings. | Must         |
| F-003  | All workflows shall use a step-based wizard with back/next navigation without loss of entered data.                                          | Must         |
| F-004  | The application shall support user roles such as Operator, Reviewer/Approver, Admin, and Read-only viewer.                                   | Should       |
| F-005  | The application shall record the authenticated user, timestamp, and software/calculation-constants version for every calculation and export. | Must         |

## 5.2 Certificate creation

| **ID** | **Requirement**                                                                                                                                                                                                                                                                                                           | **Priority** |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ |
| F-010  | The user shall select measurement discipline: Temperature, Pressure, or Differential Pressure.                                                                                                                                                                                                                            | Must         |
| F-011  | The user shall select mode: Manual or Automatic. The selected mode controls required fields, import behavior, and calculation rules.                                                                                                                                                                                      | Must         |
| F-012  | The user shall select output language: Danish, English, or bilingual if enabled by template.                                                                                                                                                                                                                              | Should       |
| F-013  | The application shall capture certificate metadata: certificate number, task number, certificate date, calibration date, receipt date, client, purchase order, item calibrated, make/model, serial number, procedure, place, approved by, remarks, traceability statement, uncertainty statement, and ambient conditions. | Must         |
| F-014  | Certificate numbers shall be generated by a configured sequence or imported from/integrated with D4 if this is chosen as the master source.                                                                                                                                                                               | Should       |
| F-015  | The application shall support one certificate per DUT serial number and batch generation from one imported run.                                                                                                                                                                                                           | Must         |
| F-016  | Before export, the user shall review a certificate preview and calculation summary.                                                                                                                                                                                                                                       | Must         |

## 5.3 Data import and measurement selection

| **ID** | **Requirement**                                                                                                                                                | **Priority** |
| ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ |
| F-020  | The application shall support manual entry and file import for measurement data.                                                                               | Must         |
| F-021  | The application shall import ValProbe RT / Kaye XLSX files and extract sensor readings, timestamps, logger IDs, and study metadata.                            | Must         |
| F-022  | The import service shall store the original uploaded file unchanged and associate it with the calibration job.                                                 | Must         |
| F-023  | For CSV/XLSX files that do not match a known parser, the application shall provide interactive column mapping.                                                 | Should       |
| F-024  | For each setpoint, the user shall select a measurement window or accept an automatically suggested stable window.                                              | Must         |
| F-025  | The application shall calculate mean, standard deviation, standard uncertainty of the mean, minimum, maximum, and number of readings for each selected window. | Must         |
| F-026  | The application shall warn if a selected window has too few readings, excessive instability, missing data, or unexpected unit/range.                           | Should       |

## 5.4 Reference equipment and constants

| **ID** | **Requirement**                                                                                                                                                                                | **Priority**                |
| ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------- |
| F-030  | The application shall maintain an equipment library containing SIMVal ID, type, serial number, calibration date, due date, calibration certificate reference, range, unit, and current status. | Optional (Controlled in D4) |
| F-031  | The user shall select all reference equipment used. The selected equipment shall appear on the certificate reference equipment page.                                                           | Must                        |
| F-032  | The application shall warn or block export if selected reference equipment is overdue, inactive, outside range, or missing required uncertainty constants.                                     | Must                        |
| F-033  | CMC, MPE, thermostat/bath uncertainty, pressure reference uncertainty, barometer uncertainty, and similar constants shall be stored as versioned data, not hard-coded.                         | Must                        |
| F-034  | The application shall prevent reported uncertainty from being lower than the applicable CMC where CMC floor is required.                                                                       | Must                        |
| F-035  | All constants shall include source, effective date, approved-by, and change history.                                                                                                           | Must                        |

# 6\. Calculation engine requirements

**Calculation principle**

The frontend shall never contain authoritative calculation formulas. All measurement calculations, uncertainty budgets, rounding decisions, CMC/MPE lookups, and pass/fail flags shall be performed by a backend calculation engine with unit tests and versioned constants.

The calculation engine shall implement the following common result model for each certificate result row:

Reference value = reference mean for the selected point/window  
Indication = DUT mean or operator-entered indicated value  
Error of indication = Indication - Reference value  
Reported result = Error of indication ± expanded uncertainty U, k=2

Temperature calculation path

Read reference values R\_i

and indication values |\_i

Calculate means

R =mean(R\_i)

|=mean(l\_i)

( Pressure calculation path

Ge repeatability|

u\_ref=stdev(R\_i)/sqrt(n)

u\_ind = stdev(I\_i)/sqrt(n)

U\_ref\_MPE,fromactiveLookupconstantsU\_bath,constants| CMC(R)version

Reference-side uncertainty U\_ref\_side = 2\*sqrt((U\_bath/2)2

+ (U\_ret\_MPE/2)\*2 + u\_ref\*2)

(u|\_ref\_side= max(U\_ret\_side, CMC(R))

Apply CMCfloor )

+u\_ind\*2 + Mrsolutos isan(25)°2) }-—

om mu aef deny"

y,

& reference pressure R

j

and DUT indication |\_i (up/down if applicable)

. Calculate meansP wo R =mean(R\_i)

mean(I\_i) or average u

Calculate repeatability u\_ref and u\_ind

if automatic mode

U\_ref\_MPE+ U\_barometerLookup= MPE\_Tryk(reference,|ifconstantsabsolute pressureR)

Final U, k=2

U = 2\*sqrt((U\_ret\_MPE/2)\*2 +u\_ref\*2 + u\_ind\*2

+ (U\_barometer/2)\*2
+ (resolution/sqrt(12))\*2)

ReferenceCertificate| Indicationresult |rowError+ }. ..........

with rounding/display rules


## 6.1 Temperature calibration logic

Automatic temperature mode should use logic where reference values come from the reference sensor readings and indications come from the DUT/loggers. The current workbook treats constants such as reference MPE and thermostat/bath uncertainty as expanded uncertainties with k=2; therefore they are divided by 2 before RSS combination and multiplied by 2 again for the reported expanded uncertainty.

| **Symbol / variable** | **Meaning**                                                                   |
| --------------------- | ----------------------------------------------------------------------------- |
| R_i                   | Reference sensor readings within the selected measurement window.             |
| I_i                   | DUT/logger readings within the selected measurement window.                   |
| R                     | Reference value for the certificate row: mean(R_i).                           |
| I                     | Indication for the certificate row: mean(I_i) or manual indication.           |
| u_ref                 | Type A standard uncertainty of reference mean: stdev.s(R_i)/sqrt(n_ref).      |
| u_ind                 | Type A standard uncertainty of DUT indication mean: stdev.s(I_i)/sqrt(n_ind). |
| U_ref_MPE             | Expanded uncertainty / MPE of selected reference probe at R.                  |
| U_bath                | Expanded uncertainty of selected bath/thermostat at R.                        |
| CMC(R)                | Applicable laboratory CMC at R.                                               |
| res                   | DUT indication resolution.                                                    |

Automatic temperature calculation:

R = mean(R_i)  
I = mean(I_i)  
Error = I - R  
u_ref = stdev.s(R_i) / sqrt(n_ref)  
u_ind = stdev.s(I_i) / sqrt(n_ind)  
<br/>U_ref_side = 2 \* sqrt((U_bath / 2)^2 + (U_ref_MPE / 2)^2 + u_ref^2)  
U_ref_side = max(U_ref_side, CMC(R))  
<br/>U_total = 2 \* sqrt((U_ref_side / 2)^2 + u_ind^2 + (res / sqrt(12))^2)

Manual temperature calculation:

R = mean(R_i)  
I = (entered_start_indication + entered_end_indication) / 2  
Error = I - R  
u_ref = stdev.s(R_i) / sqrt(n_ref)  
<br/>U_ref_side = 2 \* sqrt((U_bath / 2)^2 + (U_ref_MPE / 2)^2 + u_ref^2)  
U_ref_side = max(U_ref_side, CMC(R))  
<br/>U_total = 2 \* sqrt((U_ref_side / 2)^2 + (res / sqrt(12))^2)

| **Example input**                                           | **Calculation**                        | **Expected displayed result** |
| ----------------------------------------------------------- | -------------------------------------- | ----------------------------- |
| Reference = -90.032 °C; Indication = -90.13 °C; U = 0.01 °C | Error = -90.13 - (-90.032) = -0.098 °C | \-0.10 ± 0.01 °C              |
| Reference = -80.036 °C; Indication = -80.11 °C; U = 0.01 °C | Error = -80.11 - (-80.036) = -0.074 °C | \-0.07 ± 0.01 °C              |
| Reference = -50.027 °C; Indication = -50.05 °C; U = 0.01 °C | Error = -50.05 - (-50.027) = -0.023 °C | \-0.02 ± 0.01 °C              |

## 6.2 Pressure calibration logic

Pressure certificates follow the same core result rule: error of indication is indication minus reference pressure. The application shall support both manual and automatic pressure workflows. Absolute pressure shall include barometer uncertainty where applicable; gauge pressure shall omit that term.

| **Pressure mode**     | **Reference / indication**                                                                                                                                                | **Uncertainty terms**                                                                                                                |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| Manual pressure       | Reference pressure from imported/raw file. Indication values may include up/down readings. The reported indication is the average of up and down where applicable.        | Reference pressure MPE, DUT resolution, and barometer uncertainty for absolute pressure.                                             |
| Automatic pressure    | Separate reference and DUT files/ranges. Reference and DUT means are calculated from selected windows. Up/down averaging is applied when the method uses both directions. | Reference pressure MPE, reference repeatability, DUT repeatability, DUT resolution, and barometer uncertainty for absolute pressure. |
| Differential pressure | Reference and indication are differential pressure values. Units and ranges must be validated against the selected reference.                                             | Differential pressure reference MPE and DUT resolution/repeatability according to selected mode.                                     |

Manual pressure uncertainty model:

I_avg = (I_up + I_down) / 2 # if up/down readings are used  
Error = I_avg - R  
<br/>U_total = 2 \* sqrt((U_ref_MPE / 2)^2 + (res / sqrt(12))^2)  
<br/>\# Absolute pressure adds:  
\+ (U_barometer / 2)^2 inside the square root

Automatic pressure uncertainty model:

R = mean(reference_pressure_values)  
I = mean(DUT_pressure_values) or average of up/down means  
Error = I - R  
u_ref = stdev.s(reference_pressure_values) / sqrt(n_ref)  
u_ind = stdev.s(DUT_pressure_values) / sqrt(n_ind)  
<br/>U_total = 2 \* sqrt((U_ref_MPE/2)^2 + u_ref^2 + u_ind^2 + (res/sqrt(12))^2)  
<br/>\# Absolute pressure adds:  
\+ (U_barometer / 2)^2 inside the square root

## 6.3 Rounding and display

| **Rule**             | **Requirement**                                                                                                                                   |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Full precision       | All calculations shall be stored and performed with full numeric precision. Display rounding shall not feed back into calculation.                |
| Reported uncertainty | Expanded uncertainty U shall be rounded according to the approved SIMVal reporting rule. The rounding rule shall be configurable and unit tested. |
| Error display        | The error of indication shall be displayed to the same decimal place or agreed reporting precision as the uncertainty.                            |
| Raw result retention | The unrounded R, I, error, uncertainty components, and final U shall be retained in the certificate calculation record.                           |
| Rounding audit       | The calculation summary shall show both stored values and reported values when reviewed by an approver.                                           |

# 7\. Uncertainty budget module

The uncertainty budget module shall allow SIMVal to create, version, approve, and link uncertainty budgets to certificate types, reference equipment, and methods. It shall be generic enough to support current legacy calculations and future budgets for calibrators, probes, pressure references, and method-specific budgets.

| **ID** | **Requirement**                                                                                                                                                                                           | **Priority** |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ |
| UB-001 | The user shall select budget type: temperature certificate, pressure certificate, temperature calibrator, temperature reference probe, pressure reference, or custom method budget.                       | Must         |
| UB-002 | Each budget shall contain multiple uncertainty contributions with name, description, unit, value, probability distribution, divisor, sensitivity coefficient, standard uncertainty, and source/reference. | Must         |
| UB-003 | The application shall calculate standard uncertainty per contribution, combined standard uncertainty by RSS, expanded uncertainty U, and coverage factor k.                                               | Must         |
| UB-004 | Distributions shall support at least normal, rectangular, triangular, and U-shaped. Divisors shall be explicit and editable by authorized users.                                                          | Must         |
| UB-005 | Budgets shall be versioned. Certificates shall link to a specific approved budget version and constants version.                                                                                          | Must         |
| UB-006 | The budget view shall support export to PDF/XLSX and include enough information for independent recalculation.                                                                                            | Must         |
| UB-007 | The budget editor shall warn when a required contribution is missing for the selected method.                                                                                                             | Should       |

| **Budget family**                   | **Typical contributions to support**                                                                                                                                                                     |
| ----------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Temperature certificate uncertainty | Reference probe MPE/certificate uncertainty, bath/thermostat uncertainty, reference repeatability, DUT repeatability, DUT resolution, CMC floor.                                                         |
| Temperature calibrator / dry block  | Reference probe CMC/certificate uncertainty, probe resolution, stability, axial uniformity, radial uniformity, repeatability/thermal contact, load effect, hysteresis, heat conduction where applicable. |
| Temperature reference probe         | External calibration uncertainty, drift/linearity, resolution, reference equipment CMC, repeatability, environmental effects where applicable.                                                           |
| Pressure certificate uncertainty    | Reference pressure MPE, barometer uncertainty for absolute pressure, reference repeatability, DUT repeatability, DUT resolution.                                                                         |

# 8\. Proposed web architecture

**Architectural principle**

The developer may propose the final stack, but the architecture shall keep UI, calculation logic, data persistence, PDF generation, and audit logging separated. Calculation code must be deterministic, testable, and versioned.

| **Layer**          | **Preferred responsibility**                                                                             | **Example technology options to discuss**                                                              |
| ------------------ | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| Frontend           | Wizard screens, imports, measurement window selection, review tables, certificate preview, settings UI.  | React / Next.js, Blazor, Vue, or similar.                                                              |
| Backend API        | Authentication, workflow orchestration, business rules, calculation API, database access, audit events.  | Python FastAPI, .NET Web API, Node/NestJS.                                                             |
| Calculation engine | Pure functions for CMC/MPE lookup, averages, repeatability, uncertainty, rounding, and validation flags. | Backend library with unit tests; no spreadsheet formulas.                                              |
| Database           | Jobs, certificates, equipment, constants, budgets, users, audit trail, file metadata.                    | PostgreSQL, SQL Server, or similar relational database.                                                |
| File storage       | Raw imports, generated PDFs, XLSX exports, templates, signatures if used.                                | Controlled file share, Azure Blob Storage, S3-compatible storage, or database-backed document storage. |
| PDF rendering      | Certificate and budget output from approved templates.                                                   | HTML-to-PDF service, server-side template engine, or document rendering library.                       |
| Integration layer  | D4 certificate numbering, D4 equipment dates, future QMS/LIMS interfaces.                                | API connector or scheduled import/export depending on D4 capabilities.                                 |

## 8.1 Backend service boundaries

| **Service / module**          | **Responsibility**                                                                           |
| ----------------------------- | -------------------------------------------------------------------------------------------- |
| Auth and authorization        | Login, roles, permissions, and access control to released certificates and settings.         |
| Calibration job service       | Create/edit calibration jobs, manage workflow state, batch grouping, and metadata.           |
| Import service                | Parse known file formats, store raw file, validate data, and create reading records.         |
| Measurement window service    | Handle manual/automatic stable-window selection and setpoint grouping.                       |
| Calculation service           | Calculate result rows, uncertainty budgets, CMC/MPE lookup, rounding, and flags.             |
| Equipment service             | Manage reference equipment, due dates, calibration certificates, ranges, and status.         |
| Constants service             | Version and approve CMC/MPE/bath/pressure/barometer constants.                               |
| Certificate rendering service | Render approved certificate templates into PDF/XLSX artefacts.                               |
| Audit service                 | Record who changed what, when, previous/new values, software version, and constants version. |

## 8.2 Frontend screens

| **Screen**                 | **Purpose**                                                                                           |
| -------------------------- | ----------------------------------------------------------------------------------------------------- |
| Dashboard                  | Start new job, open drafts, view pending approvals, access history.                                   |
| Create Certificate wizard  | Metadata, discipline, method, reference equipment, import/manual entry, review, export.               |
| Import review              | Show parsed files, channels/loggers, timestamps, units, and parser warnings.                          |
| Measurement selection      | Graph/table view for setpoint windows with manual range selection and optional stability suggestions. |
| Results review             | Certificate result rows, uncertainty components, CMC floor indicators, rounding preview, warnings.    |
| Uncertainty budget editor  | Contribution table, formulas, distributions, combined U, version status, approval.                    |
| Equipment library          | Reference equipment, calibration due dates, constants, certificate references.                        |
| Certificate preview/export | Page preview, PDF export, export validation checklist.                                                |
| Settings/constants         | Templates, fixed text blocks, procedure references, CMC/MPE tables, users and roles.                  |

# 9\. Data model overview

The application should store raw data, processed measurement windows, calculations, constants, budgets, and generated certificates separately. A certificate must be reproducible from the saved raw data, selected windows, constants version, and calculation engine version.

| **Entity**              | **Key fields / relationships**                                                                       |
| ----------------------- | ---------------------------------------------------------------------------------------------------- |
| User                    | id, name, email, role, active, signature/approval metadata.                                          |
| Client                  | name, address, contact, customer number, recent entries.                                             |
| CalibrationJob          | id, job_number, discipline, method, status, language, client_id, created_by, created_at.             |
| UploadedFile            | job_id, original_filename, checksum, parser_version, storage_uri, upload_time.                       |
| DeviceUnderTest         | job_id, make, model, serial_number, equipment_id, channel/logger id.                                 |
| Reading                 | uploaded_file_id, timestamp, channel_id, value, unit, source_row, quality_flag.                      |
| MeasurementWindow       | job_id, DUT/channel, setpoint, start_time/row, end_time/row, selected_by, stability metrics.         |
| MeasurementPoint        | window_id, reference_value, indication, error, expanded_uncertainty, displayed values.               |
| ReferenceEquipment      | SIMVal ID, type, serial no., range, due date, calibration certificate ref, status.                   |
| ConstantSet             | version, effective_date, approved_by, CMC tables, MPE tables, bath/pressure/barometer constants.     |
| UncertaintyBudget       | budget_type, method, version, status, linked_constant_set, approved_by.                              |
| UncertaintyContribution | budget_id, name, value, unit, distribution, divisor, sensitivity, standard uncertainty, source.      |
| Certificate             | job_id, certificate_number, status, approved_by, linked_budget_version, linked_constant_set_version. |
| ExportArtifact          | certificate_id, type, filename, checksum, storage_uri, generated_at, generated_by.                   |
| AuditEvent              | entity_type, entity_id, action, user, timestamp, previous_value, new_value, reason.                  |

# 10\. Certificate and output requirements

| **Output part**             | **Requirement**                                                                                                                                                                                                           |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Certificate page 1          | Header with laboratory identity, certificate number/date, task number, client, item calibrated, calibration and receipt dates, traceability statement, procedure, place, uncertainty statement, approval/signature block. |
| Certificate page 2          | Item calibrated repeated, remarks, measurement conditions, temperature scale or pressure unit, and results table: Reference \| Indication \| Error of indication ± U.                                                     |
| Certificate page 3          | Reference equipment table with selected equipment and relevant identifiers.                                                                                                                                               |
| Annex / Bilag               | Optional annex pages with raw or summary data, method-specific information, or uncertainty budget where required.                                                                                                         |
| Uncertainty budget PDF/XLSX | Contribution table, standard uncertainties, combined standard uncertainty, expanded uncertainty, coverage factor, constants version, and approval information.                                                            |
| Batch export                | One PDF per DUT serial number and/or one combined batch report, depending on chosen template.                                                                                                                             |

| **ID** | **Requirement**                                                                                                                                                                                                               | **Priority** |
| ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ |
| O-001  | The output shall visually match the approved SIMVal certificate template, including bilingual labels where required. DANAK Logo including reg. number and SIMVal Logo must be shown with SIMVal being larger than DANAK Logo. | Must         |
| O-002  | Generated files shall include certificate number, date, and configurable naming convention.                                                                                                                                   | Must         |
| O-003  | Exported PDFs shall be locked/finalized after approval so that regeneration requires a new revision or audit event.                                                                                                           | Should       |
| O-004  | All generated artefacts shall be retrievable from certificate history.                                                                                                                                                        | Must         |
| O-005  | The certificate shall include software version and constants/budget version either visibly or in an internal audit record.                                                                                                    | Must         |

# 11\. Validation, traceability and auditability

The application will be used in a regulated metrology context. The calculation and reporting logic must therefore be validated against known examples

| **Requirement area**      | **Expected implementation**                                                                                                                       |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Unit tests                | Each formula and lookup function shall have unit tests, including edge cases at range boundaries and negative temperatures/pressures.             |
| Golden master tests       | Known input files from the workflow shall be processed by the new app and compared with expected certificate rows and uncertainty results.        |
| Version locking           | A released certificate shall reference the exact software version, constants version, and budget version used.                                    |
| Audit trail               | All changes to metadata, selected windows, results, constants, budgets, approval status, and export artefacts shall be recorded.                  |
| Access control            | Only authorized roles may edit constants, approve budgets, approve certificates, or regenerate released outputs.                                  |
| Data integrity            | Raw files shall be stored unchanged with checksum. Parsed data shall trace back to source file, sheet, row, column, and timestamp where possible. |
| Independent recalculation | Calculation summaries shall include enough information to independently reproduce results: inputs, components, constants, formulas, and rounding. |
| Validation package        | The developer should be able to produce IQ/OQ/PQ-style evidence or an equivalent test report from automated tests and manual test scripts.        |

## 11.1 Initial test cases for developer

| **Test ID**  | **Scenario**                                                        | **Expected result**                                                                                          |
| ------------ | ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| TC-TEMP-001  | Temperature result row: R = 0.000 °C, I = -0.01 °C, U = 0.01 °C.    | Error = -0.01 °C; displayed result -0.01 ± 0.01 °C.                                                          |
| TC-TEMP-002  | Temperature result row: R = -90.032 °C, I = -90.13 °C, U = 0.01 °C. | Unrounded error = -0.098 °C; displayed result -0.10 ± 0.01 °C.                                               |
| TC-TEMP-003  | Temperature uncertainty calculated below applicable CMC.            | Reported U shall be raised to at least the applicable CMC floor.                                             |
| TC-TEMP-004  | Automatic temperature import with multiple logger channels.         | Application generates one result set per logger/channel and supports batch certificate review.               |
| TC-PRESS-001 | Manual gauge pressure with up/down indications.                     | Reported indication is average of up/down where applicable; error = average indication - reference pressure. |
| TC-PRESS-002 | Absolute pressure calculation.                                      | Barometer uncertainty contribution is included; gauge pressure omits it.                                     |
| TC-CONST-001 | Reference equipment outside selected temperature/pressure range.    | Application warns or blocks calculation/export.                                                              |
| TC-AUDIT-001 | Released certificate regenerated after constants change.            | Old certificate remains tied to original constants version; new generation creates revision/audit event.     |

# 12\. Open questions for the developer meeting

| **Question**                                                                             | **Why it matters / recommendation**                                                                                                                                                                                       |
| ---------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Should the system be hosted internally, in Azure/M365 environment, or by the developer?  | Affects authentication, data storage, backups, responsibility, and GDPR/security controls.                                                                                                                                |
| Will D4 remain the master source for certificate numbers and equipment due dates?        | If yes, define API/import/export method early. If no, implement internal sequence/equipment library with reconciliation.                                                                                                  |
| How should measurement windows be selected in v1?                                        | Manual selection is easiest to validate. Automatic plateau detection can be added later with transparent thresholds and override.                                                                                         |
| Should pressure be included in MVP or phase 2?                                           | Temperature has the clearest immediate path. Pressure adds more method branches but should be designed into the data model from day one.                                                                                  |
| What approval/signature level is required?                                               | A visual signature image is simpler; cryptographic PDF signing requires additional infrastructure and policy decisions.                                                                                                   |
| Should each logger receive its own certificate or should batch certificates be combined? | The previous requirement suggests batch handling. Confirm desired final customer-facing format. Batch handling is recommended, meaning a summary report for all the DUT (Device under test) for a single calibration run. |
| How much of the uncertainty budget should be visible on the certificate?                 | Could be a concise U only, a summary, or a full annex depending on SIMVal/DANAK expectations.                                                                                                                             |
| Who can edit constants and budgets?                                                      | Changes to constants directly affect certificates. Edits should require role control and approval.                                                                                                                        |
| What data retention period applies to raw files, drafts, certificates, and audit logs?   | Affects storage, GDPR, QMS, backup, and deletion rules.                                                                                                                                                                   |

# 13\. Suggested development phases

| **Phase**                                 | **Scope**                                                                                                                                                             | **Acceptance target**                                                                           |
| ----------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| Phase 0: Discovery and validation mapping | Developer reviews legacy workbook, extracts formulas/constants, confirms all certificate types, and produces a calculation mapping document.                          | SIMVal signs off on calculation scope and known test examples.                                  |
| Phase 1: Temperature certificate MVP      | Web wizard, equipment library, constants tables, ValProbe RT import, manual entry fallback, measurement window selection, temperature calculation engine, PDF export. | New app reproduces selected legacy temperature examples within agreed rounding rules.           |
| Phase 2: Uncertainty budget module        | Generic budget editor, contribution library, budget versioning, budget approval, PDF/XLSX export, linking budget to certificates.                                     | Approved budgets can populate certificate U values and produce traceable calculation summaries. |
| Phase 3: Pressure certificates            | Manual/automatic pressure workflows, gauge/absolute/differential branches, pressure constants, pressure PDF template.                                                 | New app reproduces pressure legacy examples and validates absolute/gauge contributions.         |
| Phase 4: Workflow hardening               | Approval workflow, digital signature decision, D4 integration, certificate history, advanced batch reporting, user management.                                        | Validated and controlled release ready for routine use.                                         |

# Appendix A. Notes on standards and method assumptions

- The GUM approach treats uncertainty components as standard uncertainties before combining them. Existing expanded uncertainties with k=2 must be converted to standard uncertainty by division before RSS combination.
- Coverage factor k=2 is used in the legacy certificate language and is commonly associated with approximately 95% coverage under appropriate assumptions.
- Uncertainty budgets should list all significant components and their evaluation method, source, unit, distribution, divisor, and sensitivity coefficient.
- For temperature block calibrator budgets, EURAMET CG-13 distinguishes calibration from characterisation and highlights contributions such as axial/radial distribution, stability, loading, and heat conduction/thermal contact.
- The application shall not silently change a calculation method after certificates have been issued. Method changes require a new calculation engine version and validation evidence.

# Appendix B. Minimal API endpoint sketch

| **Endpoint group**  | **Example operations**                                                                                                       |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Auth                | GET /me; POST /login or SSO callback; GET /roles.                                                                            |
| Calibration jobs    | POST /calibration-jobs; GET /calibration-jobs/{id}; PATCH /calibration-jobs/{id}; POST /calibration-jobs/{id}/submit-review. |
| Files/imports       | POST /calibration-jobs/{id}/files; POST /imports/{id}/parse; GET /imports/{id}/warnings.                                     |
| Measurement windows | POST /measurement-windows; PATCH /measurement-windows/{id}; GET /calibration-jobs/{id}/windows.                              |
| Calculations        | POST /calculation-runs; GET /calculation-runs/{id}; GET /calculation-runs/{id}/summary.                                      |
| Equipment           | GET/POST/PATCH /reference-equipment; GET /reference-equipment/{id}/constants.                                                |
| Budgets             | GET/POST/PATCH /uncertainty-budgets; POST /uncertainty-budgets/{id}/approve.                                                 |
| Certificates        | POST /certificates; GET /certificates/{id}; POST /certificates/{id}/render; POST /certificates/{id}/approve.                 |
| Audit               | GET /audit-events?entity_type=&entity_id=.                                                                                   |