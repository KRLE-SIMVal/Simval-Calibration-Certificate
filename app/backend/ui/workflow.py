"""Workflow contract and HTML shell for the SIMVal browser UI."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class WorkflowAction:
    label: str
    method: str
    path: str
    required_roles: tuple[str, ...]
    requires_session: bool = True


@dataclass(frozen=True, slots=True)
class WorkflowStep:
    step_id: str
    label: str
    status: str
    actions: tuple[WorkflowAction, ...]
    evidence: tuple[str, ...]
    deferred: tuple[str, ...] = ()


def browser_workflow_contract() -> dict[str, Any]:
    """Return the regulated workflow sequence exposed to the browser shell."""
    return {
        "application": "SIMVal Calibration Certificate",
        "status": "p6_browser_workflow",
        "equipment_library_policy": (
            "Reference equipment master data is populated manually before "
            "production use; the browser workflow selects immutable equipment "
            "snapshots for certificate evidence."
        ),
        "steps": tuple(asdict(step) for step in _workflow_steps()),
    }


def browser_workflow_html() -> str:
    """Return a dependency-free HTML shell for the controlled workflow."""
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SIMVal Calibration Certificate</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #1f2933;
      --muted: #52606d;
      --line: #d9e2ec;
      --surface: #ffffff;
      --band: #f5f7fa;
      --accent: #005f73;
      --focus: #0f7c90;
      --danger: #9b1c1c;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      color: var(--ink);
      background: var(--band);
    }
    header {
      min-height: 94px;
      padding: 18px 28px;
      background: var(--surface);
      border-bottom: 1px solid var(--line);
      display: grid;
      grid-template-columns: auto 1fr auto;
      gap: 18px;
      align-items: center;
    }
    header img { display: block; max-height: 58px; width: auto; }
    h1 { margin: 0; font-size: 1.35rem; font-weight: 700; }
    .subhead { margin-top: 5px; color: var(--muted); font-size: .92rem; }
    main { padding: 18px 24px 30px; }
    .toolbar {
      display: grid;
      grid-template-columns: minmax(220px, 320px) minmax(220px, 320px) 1fr;
      gap: 12px;
      margin-bottom: 18px;
      align-items: end;
    }
    label { display: grid; gap: 5px; font-size: .82rem; color: var(--muted); }
    input, textarea, select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 9px 10px;
      font: inherit;
      color: var(--ink);
      background: var(--surface);
    }
    textarea { min-height: 170px; resize: vertical; font-family: Consolas, monospace; }
    button {
      min-height: 38px;
      border: 1px solid var(--accent);
      border-radius: 6px;
      padding: 8px 12px;
      color: white;
      background: var(--accent);
      font-weight: 700;
      cursor: pointer;
    }
    button.secondary {
      color: var(--accent);
      background: var(--surface);
    }
    button:focus, input:focus, textarea:focus, select:focus {
      outline: 3px solid rgba(15, 124, 144, .25);
      outline-offset: 1px;
    }
    .workflow {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }
    .step {
      min-height: 136px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      padding: 13px;
      display: grid;
      align-content: start;
      gap: 9px;
    }
    .step h2 { margin: 0; font-size: 1rem; }
    .step p { margin: 0; color: var(--muted); font-size: .86rem; line-height: 1.38; }
    .step .actions { display: flex; gap: 8px; flex-wrap: wrap; }
    .app-nav {
      min-height: 52px;
      display: flex;
      gap: 8px;
      align-items: center;
      padding: 0 0 16px;
      overflow-x: auto;
    }
    .nav-item {
      min-width: max-content;
      color: var(--ink);
      border-color: var(--line);
      background: var(--surface);
      font-weight: 700;
    }
    .nav-item.active {
      color: white;
      border-color: var(--accent);
      background: var(--accent);
    }
    .workspace-layout {
      display: grid;
      grid-template-columns: minmax(260px, 340px) minmax(0, 1fr);
      gap: 16px;
      align-items: start;
    }
    .side-panel {
      display: grid;
      gap: 12px;
    }
    .side-panel .workflow {
      grid-template-columns: 1fr;
      margin-bottom: 0;
    }
    .side-panel .step {
      min-height: 0;
      border-radius: 6px;
      padding: 11px;
    }
    .side-panel .step h2 { font-size: .92rem; }
    .side-panel .step p { font-size: .78rem; }
    .certificate-board {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      overflow: hidden;
    }
    .board-header {
      display: grid;
      grid-template-columns: minmax(220px, 1fr) minmax(260px, 460px);
      gap: 14px;
      align-items: end;
      padding: 16px;
      border-bottom: 1px solid var(--line);
      background: #fbfcfd;
    }
    .board-header h2 { margin: 0; font-size: 1.15rem; }
    .board-header p { margin: 5px 0 0; color: var(--muted); font-size: .86rem; }
    .mode-strip {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }
    .wizard-steps {
      display: grid;
      grid-template-columns: repeat(6, minmax(96px, 1fr));
      border-bottom: 1px solid var(--line);
      background: var(--band);
    }
    .wizard-step {
      min-height: 54px;
      border: 0;
      border-right: 1px solid var(--line);
      border-radius: 0;
      color: var(--ink);
      background: transparent;
      font-size: .82rem;
    }
    .wizard-step:last-child { border-right: 0; }
    .wizard-step.active {
      color: white;
      background: var(--focus);
    }
    .wizard-body {
      display: grid;
      gap: 14px;
      padding: 16px;
    }
    .wizard-section {
      display: grid;
      gap: 12px;
    }
    .wizard-section[hidden] { display: none; }
    .section-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
    }
    .section-head h3 { margin: 0; font-size: 1rem; }
    .status-pill {
      min-width: 76px;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 5px 9px;
      color: var(--muted);
      background: #f8fafc;
      font-size: .75rem;
      font-weight: 700;
      text-align: center;
    }
    .status-pill.done {
      color: #0f5132;
      border-color: #9ad0b2;
      background: #eaf7ef;
    }
    .status-pill.active {
      color: #084c61;
      border-color: #87c7d4;
      background: #e9f7fa;
    }
    .summary-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(120px, 1fr));
      gap: 10px;
    }
    .summary-item {
      min-height: 74px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      background: #fbfcfd;
    }
    .summary-item span {
      display: block;
      color: var(--muted);
      font-size: .76rem;
      margin-bottom: 7px;
    }
    .summary-item strong {
      display: block;
      overflow-wrap: anywhere;
      font-size: .95rem;
    }
    .wizard-nav {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      border-top: 1px solid var(--line);
      padding-top: 12px;
    }
    details.advanced-console {
      margin-top: 16px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
    }
    details.advanced-console summary {
      cursor: pointer;
      padding: 13px 14px;
      color: var(--ink);
      font-weight: 700;
    }
    details.advanced-console .advanced-inner {
      padding: 0 14px 14px;
      border-top: 1px solid var(--line);
    }
    .split {
      display: grid;
      grid-template-columns: minmax(300px, 1fr) minmax(300px, 1fr);
      gap: 14px;
    }
    .task-grid {
      display: grid;
      grid-template-columns: minmax(300px, 1fr) minmax(300px, 1fr);
      gap: 14px;
      margin-bottom: 18px;
    }
    section.panel {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      padding: 14px;
    }
    section.panel h2 { margin: 0 0 12px; font-size: 1rem; }
    .field-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(160px, 1fr));
      gap: 10px;
    }
    .wide { grid-column: 1 / -1; }
    .panel-actions { margin-top: 12px; display: flex; gap: 8px; flex-wrap: wrap; }
    .run-status {
      margin-top: 12px;
      min-height: 96px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      background: #111827;
      color: #f9fafb;
      font-family: Consolas, monospace;
      font-size: .82rem;
      line-height: 1.45;
      white-space: pre-wrap;
    }
    a.button-link {
      min-height: 38px;
      border: 1px solid var(--accent);
      border-radius: 6px;
      padding: 8px 12px;
      color: var(--accent);
      background: var(--surface);
      font-weight: 700;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
    }
    a.button-link[hidden] { display: none; }
    pre {
      margin: 0;
      min-height: 248px;
      max-height: 460px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 12px;
      background: #111827;
      color: #f9fafb;
      font-size: .82rem;
      line-height: 1.45;
      white-space: pre-wrap;
    }
    .danger { color: var(--danger); font-weight: 700; }
    @media (max-width: 780px) {
      header { grid-template-columns: 1fr; }
      .toolbar, .split, .task-grid, .field-grid, .workspace-layout,
      .board-header, .mode-strip, .summary-grid { grid-template-columns: 1fr; }
      .wizard-steps { grid-template-columns: repeat(2, minmax(120px, 1fr)); }
      .wide { grid-column: auto; }
    }
  </style>
</head>
<body>
  <header>
    <img src="/design-assets/simval-logo" alt="SIMVal">
    <div>
      <h1>SIMVal Calibration Certificate</h1>
      <div class="subhead">Controlled certificate workflow</div>
    </div>
    <button class="secondary" id="loadContract">Refresh</button>
  </header>
  <main id="certificateWorkspace">
    <nav class="app-nav" aria-label="Application areas">
      <button class="nav-item active" type="button">Create Certificate</button>
      <button class="nav-item" type="button">Create Uncertainty Budget</button>
      <button class="nav-item" type="button">Equipment Library</button>
      <button class="nav-item" type="button">Certificate History</button>
      <button class="nav-item" type="button">Settings</button>
    </nav>
    <div class="workspace-layout">
      <aside class="side-panel">
        <section class="panel">
          <h2>Local Session</h2>
          <label>Session ID
            <input id="sessionId" autocomplete="off" placeholder="X-Session-Id">
          </label>
        </section>
        <section class="panel">
          <h2>Workflow Evidence</h2>
          <div class="workflow" id="workflow"></div>
        </section>
      </aside>
      <section class="certificate-board" id="manualPressureWizard">
        <div class="board-header">
          <div>
            <h2>Create Certificate</h2>
            <p>Manual pressure certificate draft</p>
          </div>
          <div class="mode-strip">
            <label>Discipline
              <select id="jobDiscipline">
                <option value="pressure" selected>Pressure</option>
                <option value="temperature">Temperature</option>
              </select>
            </label>
            <label>Mode
              <select id="measurementMode">
                <option value="manual" selected>Manual</option>
                <option value="automatic">Automatic</option>
              </select>
            </label>
          </div>
        </div>
        <div class="wizard-steps" role="tablist" aria-label="Certificate workflow">
          <button class="wizard-step active" type="button" data-step-target="job">1 Job</button>
          <button class="wizard-step" type="button" data-step-target="metadata">2 Metadata</button>
          <button class="wizard-step" type="button" data-step-target="equipment">3 Equipment</button>
          <button class="wizard-step" type="button" data-step-target="measurement">4 Measurement</button>
          <button class="wizard-step" type="button" data-step-target="calculation">5 Calculation</button>
          <button class="wizard-step" type="button" data-step-target="review">6 Review</button>
        </div>
        <div class="wizard-body">
          <section class="wizard-section" data-wizard-panel="job">
            <div class="section-head">
              <h3>Job</h3>
              <span class="status-pill active" data-step-status="job">Active</span>
            </div>
            <div class="field-grid">
              <label>Job ID
                <input id="manualPressureJobId" autocomplete="off">
              </label>
              <label>Client
                <input id="clientName" autocomplete="off" value="SIMVal pressure customer">
              </label>
              <label class="wide">Client address
                <input id="clientAddress" autocomplete="off" value="Pressure Road 1, 2800 Lyngby">
              </label>
              <label class="wide">Method
                <input id="jobMethod" autocomplete="off" value="SIMVal manual pressure calibration method">
              </label>
              <label>Software version
                <input id="uploadSoftwareVersion" autocomplete="off" value="app-0.1.0">
              </label>
              <input id="jobId" type="hidden" value="job-001">
            </div>
            <div class="panel-actions">
              <button id="createJob">Save Job</button>
            </div>
          </section>
          <section class="wizard-section" data-wizard-panel="metadata" hidden>
            <div class="section-head">
              <h3>Certificate Metadata</h3>
              <span class="status-pill" data-step-status="metadata">Pending</span>
            </div>
            <div class="field-grid">
              <label>Certificate number
                <input id="manualPressureCertificateNumber" autocomplete="off" value="SIMVAL-MANUAL-PRESSURE-0001">
              </label>
              <label>Task number
                <input id="taskNumber" autocomplete="off" value="TASK-PRESSURE-2026-001">
              </label>
              <label>Purchase order
                <input id="purchaseOrder" autocomplete="off" value="PO-PRESSURE-12345">
              </label>
              <label>Certificate date
                <input id="certificateDate" autocomplete="off" value="2026-06-17">
              </label>
              <label>Calibration date
                <input id="calibrationDate" autocomplete="off" value="2026-06-17">
              </label>
              <label>Receipt date
                <input id="receiptDate" autocomplete="off" value="2026-06-16">
              </label>
              <label>Procedure
                <input id="procedure" autocomplete="off" value="SIMVal SOP-PRESS-001">
              </label>
              <label>Place
                <input id="place" autocomplete="off" value="SIMVal Pressure Laboratory, Lyngby">
              </label>
              <label>Approved by
                <input id="approvedByLabel" autocomplete="off" value="QA Preview User">
              </label>
              <label class="wide">Remarks
                <input id="remarks" autocomplete="off" value="Manual pressure readings entered from controlled source evidence.">
              </label>
              <label class="wide">Traceability statement
                <input id="traceabilityStatement" autocomplete="off" value="Pressure measurements are traceable through the selected reference pressure standard.">
              </label>
              <label class="wide">Uncertainty statement
                <input id="uncertaintyStatement" autocomplete="off" value="Expanded uncertainty is reported with coverage factor k=2.">
              </label>
              <label class="wide">Ambient conditions
                <input id="ambientConditions" autocomplete="off" value="Room temperature 23 +/- 2 deg C; stable laboratory conditions.">
              </label>
            </div>
            <div class="panel-actions">
              <button class="secondary" id="captureMetadata">Capture Metadata</button>
            </div>
          </section>
          <section class="wizard-section" data-wizard-panel="equipment" hidden>
            <div class="section-head">
              <h3>Reference Equipment</h3>
              <span class="status-pill" data-step-status="equipment">Pending</span>
            </div>
            <div class="summary-grid">
              <div class="summary-item"><span>SIMVal ID</span><strong>SIM-P-001</strong></div>
              <div class="summary-item"><span>Type</span><strong>Pressure calibrator</strong></div>
              <div class="summary-item"><span>Range</span><strong>0 to 20 bar</strong></div>
            </div>
            <div class="panel-actions">
              <button class="secondary" id="selectReferenceEquipment">Select Equipment</button>
              <button class="secondary" id="approveConstantSet">Approve Constants</button>
              <button class="secondary" id="approveUncertaintyBudget">Approve Budget</button>
            </div>
          </section>
          <section class="wizard-section" data-wizard-panel="measurement" hidden>
            <div class="section-head">
              <h3>Manual Measurement</h3>
              <span class="status-pill" data-step-status="measurement">Pending</span>
            </div>
            <div class="field-grid">
              <label>Reference pressure
                <input id="manualPressureReference" autocomplete="off" value="10.000">
              </label>
              <label>Unit
                <input id="manualPressureUnit" autocomplete="off" value="bar">
              </label>
              <label>DUT make
                <input id="dutMake" autocomplete="off" value="PressureCo">
              </label>
              <label>DUT model
                <input id="dutModel" autocomplete="off" value="Gauge">
              </label>
              <label>DUT serial
                <input id="dutSerialNumber" autocomplete="off" value="PG-001">
              </label>
              <label>DUT channel
                <input id="dutChannelId" autocomplete="off" value="PG-001">
              </label>
              <label>Indication 1
                <input id="manualPressureIndicationA" autocomplete="off" value="10.004">
              </label>
              <label>Indication 2
                <input id="manualPressureIndicationB" autocomplete="off" value="10.006">
              </label>
              <label>Source file
                <input id="sourceFile" type="file">
              </label>
              <label>File kind
                <select id="uploadFileKind">
                  <option value="calibration_xlsx">Calibration XLSX</option>
                  <option value="verification_pdf">Verification PDF</option>
                  <option value="certificate_reference_pdf">Certificate reference PDF</option>
                  <option value="other" selected>Other</option>
                </select>
              </label>
            </div>
            <div class="panel-actions">
              <button id="uploadSourceFile">Upload File</button>
              <button class="secondary" id="reviewImports">Review Imports</button>
            </div>
            <div class="run-status" id="sourceFileStatus"></div>
          </section>
          <section class="wizard-section" data-wizard-panel="calculation" hidden>
            <div class="section-head">
              <h3>Uncertainty Budget and Calculation</h3>
              <span class="status-pill" data-step-status="calculation">Pending</span>
            </div>
            <div class="field-grid">
              <label class="wide">Budget method
                <input id="budgetMethod" autocomplete="off" value="SIMVal manual pressure calibration method">
              </label>
              <label>Pressure kind
                <select id="pressureKind">
                  <option value="gauge" selected>Gauge</option>
                  <option value="absolute">Absolute</option>
                </select>
              </label>
              <label>CMC floor
                <input id="cmcFloor" autocomplete="off" value="0.001">
              </label>
              <label>Reference U
                <input id="referenceExpandedUncertainty" autocomplete="off" value="0.004">
              </label>
              <label>Reference k
                <input id="referenceCoverageFactor" autocomplete="off" value="2.0">
              </label>
              <label>DUT resolution
                <input id="dutResolution" autocomplete="off" value="0.002">
              </label>
              <label>Barometer U
                <input id="barometerExpandedUncertainty" autocomplete="off" value="0.0">
              </label>
              <label>Barometer k
                <input id="barometerCoverageFactor" autocomplete="off" value="2.0">
              </label>
              <label>Coverage factor
                <input id="coverageFactor" autocomplete="off" value="2.0">
              </label>
              <label>Calculation engine
                <input id="calculationEngineVersion" autocomplete="off" value="calc-engine-0.1.0">
              </label>
              <label>Constants version
                <input id="constantSetVersion" autocomplete="off" value="constants-2026-001">
              </label>
              <label>Budget version
                <input id="budgetVersion" autocomplete="off" value="budget-pressure-001">
              </label>
            </div>
            <div class="panel-actions">
              <button class="secondary" id="createUncertaintyBudget">Create Budget</button>
              <button class="secondary" id="calculatePressure">Calculate Pressure</button>
              <button class="secondary" type="button" id="openReviewStep">Review Preview</button>
            </div>
            <div class="run-status" id="budgetStatus"></div>
          </section>
          <section class="wizard-section" data-wizard-panel="review" hidden>
            <div class="section-head">
              <h3>Review and Preview</h3>
              <span class="status-pill" data-step-status="review">Pending</span>
            </div>
            <div class="summary-grid">
              <div class="summary-item"><span>Pressure point</span><strong id="pressurePointSummary">10.000 bar</strong></div>
              <div class="summary-item"><span>Certificate</span><strong id="certificateSummary">SIMVAL-MANUAL-PRESSURE-0001</strong></div>
              <div class="summary-item"><span>Preview PDF</span><strong id="pdfSummary">Not rendered</strong></div>
              <div class="summary-item"><span>Released certificate</span><strong id="releaseSummary">Not released</strong></div>
            </div>
            <div class="panel-actions">
              <button class="secondary" id="submitTechnicalReview">Submit Review</button>
              <button class="secondary" id="approveTechnicalReview">Approve Technical</button>
              <button class="secondary" id="approveQaRelease">Approve QA</button>
              <button class="secondary" id="buildCertificatePreview">Build Preview</button>
              <button class="secondary" id="renderCertificateRelease">Render Release</button>
              <button id="runManualPressurePreview">Run Complete Preview</button>
              <button id="runFirstCertificate">Produce Certificate</button>
              <a class="button-link" id="manualPressurePdfLink" href="#" target="_blank" rel="noopener" hidden>Open Preview PDF</a>
              <a class="button-link" id="certificatePdfLink" href="#" target="_blank" rel="noopener" hidden>Open Certificate PDF</a>
            </div>
            <div class="run-status" id="manualPressureStatus"></div>
          </section>
          <div class="wizard-nav">
            <button class="secondary" type="button" id="previousWizardStep">Back</button>
            <button type="button" id="nextWizardStep">Next</button>
          </div>
        </div>
      </section>
    </div>
    <section class="panel" hidden>
      <label>Calibration file ID
        <input id="calibrationUploadedFileId" autocomplete="off">
      </label>
      <label>Verification file ID
        <input id="verificationUploadedFileId" autocomplete="off">
      </label>
      <label>Setpoints
        <input id="temperatureSetpoints" autocomplete="off" value="-80">
      </label>
      <textarea id="irtdRows" rows="4">Time,IRTD (deg C),MJT1-A
2026-04-08T15:45:00+00:00,-80.031,-80.036
2026-04-08T15:46:00+00:00,-80.030,-80.034</textarea>
      <input id="windowId" autocomplete="off" value="window-001">
      <input id="windowDutId" autocomplete="off" value="dut-MJT1-A">
      <input id="windowChannelId" autocomplete="off" value="MJT1-A">
      <input id="windowStart" autocomplete="off" value="2026-04-08T15:45:00+00:00">
      <input id="windowEnd" autocomplete="off" value="2026-04-08T15:46:00+00:00">
      <input id="bathExpandedUncertainty" autocomplete="off" value="0.004">
      <button class="secondary" id="prepareTemperatureData">Prepare Data</button>
      <button class="secondary" id="recordIrtdRows">Record IRTD</button>
      <button class="secondary" id="selectTemperatureWindow">Select Window</button>
      <button class="secondary" id="completeTemperatureWindows">Complete Windows</button>
      <button class="secondary" id="calculateTemperature">Calculate Temperature</button>
    </section>
    <details class="advanced-console" id="advancedApiConsole">
      <summary>Advanced API Console</summary>
      <div class="advanced-inner">
        <div class="toolbar">
          <label>Operation
            <select id="operation"></select>
          </label>
          <div>
            <button id="sendRequest">Send</button>
          </div>
        </div>
        <div class="split">
          <section class="panel">
            <h2>Request</h2>
            <textarea id="requestBody" spellcheck="false"></textarea>
          </section>
          <section class="panel">
            <h2>Response</h2>
            <pre id="responseBody"></pre>
          </section>
        </div>
      </div>
    </details>
  </main>
  <script>
    const samples = {
      "/me": "",
      "/calibration-jobs": {
        job_id: "job-001",
        client_name: "SIMVal customer",
        client_address: "Validated Road 1",
        discipline: "temperature",
        measurement_mode: "automatic",
        method: "ValProbe RT linked XLSX/PDF workflow",
        software_version: "app-0.1.0"
      },
      "/constant-sets/approved": {
        version: "constants-2026-001",
        discipline: "temperature",
        effective_from: "2026-01-01T00:00:00+00:00",
        software_version: "app-0.1.0"
      },
      "/uncertainty-budgets/approved": {
        version: "budget-temp-001",
        budget_type: "temperature_logger",
        method: "ValProbe RT automatic temperature",
        discipline: "temperature",
        linked_constant_set_version: "constants-2026-001",
        software_version: "app-0.1.0"
      },
      "/certificate-number-sequences": {
        prefix: "SIMVAL-CAL",
        next_value: 1,
        software_version: "app-0.1.0"
      },
      "/certificate-number-allocations": {
        prefix: "SIMVAL-CAL",
        padding: 4,
        software_version: "app-0.1.0"
      },
      "/certificate-number-sequences/SIMVAL-CAL/retirement": {
        reason: "Prefix retired by controlled numbering policy.",
        software_version: "app-0.1.0"
      },
      "/calibration-jobs/job-001/files": "",
      "/calibration-jobs/job-001/imports": "",
      "/calibration-jobs/job-001/temperature-data-entry": {
        calibration_uploaded_file_id: "file-001",
        setpoints: [-80],
        unit: "deg C",
        software_version: "app-0.1.0"
      },
      "/calibration-jobs/job-001/verification-irtd-rows": {
        calibration_uploaded_file_id: "file-001",
        verification_uploaded_file_id: "file-002",
        rows: [
          ["Time", "IRTD (deg C)", "MJT1-A"],
          ["2026-04-08T15:45:00+00:00", "-80.031", "-80.036"],
          ["2026-04-08T15:46:00+00:00", "-80.030", "-80.034"]
        ],
        unit: "deg C",
        software_version: "app-0.1.0"
      },
      "/calibration-jobs/pressure-job-001/pressure-manual-entry": {
        uploaded_file_id: "pressure-file-001",
        dut_id: "pressure-dut-001",
        dut_make: "PressureCo",
        dut_model: "Gauge",
        dut_serial_number: "PG-001",
        dut_channel_id: "PG-001",
        window_id: "pressure-window-001",
        setpoint: 10.0,
        unit: "bar",
        readings: [
          {
            timestamp: "2026-06-01T14:20:00+00:00",
            value: 10.004,
            source_label: "Pressure",
            row_number: 2,
            column_label: "indication"
          },
          {
            timestamp: "2026-06-01T14:21:00+00:00",
            value: 10.006,
            source_label: "Pressure",
            row_number: 3,
            column_label: "indication"
          }
        ],
        software_version: "app-0.1.0"
      },
      "/calibration-jobs/job-001/temperature-windows": {
        window_id: "window-001",
        dut_id: "dut-MJT1-A",
        dut_channel_id: "MJT1-A",
        setpoint: -80,
        unit: "deg C",
        start_timestamp: "2026-04-08T15:45:00+00:00",
        end_timestamp: "2026-04-08T15:46:00+00:00",
        software_version: "app-0.1.0"
      },
      "/calibration-jobs/job-001/temperature-windows/complete": {
        software_version: "app-0.1.0"
      },
      "/calibration-jobs/job-001/temperature-calculations": {
        uncertainty_inputs: [
          {
            setpoint: -80,
            unit: "deg C",
            cmc_floor: "0.010",
            reference_expanded_uncertainty: 0.010,
            bath_expanded_uncertainty: 0.004,
            dut_resolution: 0.010
          }
        ],
        software_version: "app-0.1.0",
        calculation_engine_version: "calc-engine-0.1.0",
        constant_set_version: "constants-2026-001",
        budget_version: "budget-temp-001"
      },
      "/pressure/manual-calculations": {
        point_id: "pressure-point-001",
        job_id: "pressure-job-001",
        dut_id: "pressure-dut-001",
        measurement_window_id: "pressure-window-001",
        reference_pressure: 10.0,
        indication_values: [10.004, 10.006],
        setpoint: 10.0,
        unit: "bar",
        pressure_kind: "gauge",
        cmc_floor: "0.001",
        reference_expanded_uncertainty: 0.004,
        reference_coverage_factor: 2.0,
        dut_resolution: 0.002,
        barometer_expanded_uncertainty: 0.0,
        barometer_coverage_factor: 2.0,
        coverage_factor: 2.0,
        additional_standard_uncertainties: [],
        software_version: "app-0.1.0",
        calculation_engine_version: "calc-engine-0.1.0",
        constant_set_version: "constants-pressure-001",
        budget_version: "budget-pressure-001"
      },
      "/pressure/automatic-calculations": {
        point_id: "pressure-auto-point-001",
        job_id: "pressure-job-001",
        dut_id: "pressure-dut-001",
        measurement_window_id: "pressure-auto-window-001",
        reference_values: [100.000, 100.002, 100.001],
        indication_values: [100.004, 100.006, 100.005],
        setpoint: 100.0,
        unit: "bar",
        pressure_kind: "gauge",
        cmc_floor: "0.001",
        reference_expanded_uncertainty: 0.004,
        reference_coverage_factor: 2.0,
        dut_resolution: 0.002,
        barometer_expanded_uncertainty: 0.0,
        barometer_coverage_factor: 2.0,
        coverage_factor: 2.0,
        additional_standard_uncertainties: [],
        software_version: "app-0.1.0",
        calculation_engine_version: "calc-engine-0.1.0",
        constant_set_version: "constants-pressure-001",
        budget_version: "budget-pressure-001"
      },
      "/calibration-jobs/pressure-job-001/pressure-calculations": {
        manual_points: [
          {
            point_id: "pressure-point-001",
            dut_id: "pressure-dut-001",
            measurement_window_id: "pressure-window-001",
            reference_pressure: 10.0,
            indication_values: [10.004, 10.006],
            setpoint: 10.0,
            unit: "bar",
            pressure_kind: "gauge",
            cmc_floor: "0.001",
            reference_expanded_uncertainty: 0.004,
            reference_coverage_factor: 2.0,
            dut_resolution: 0.002,
            barometer_expanded_uncertainty: 0.0,
            barometer_coverage_factor: 2.0,
            coverage_factor: 2.0,
            additional_standard_uncertainties: []
          }
        ],
        automatic_points: [],
        software_version: "app-0.1.0",
        calculation_engine_version: "calc-engine-0.1.0",
        constant_set_version: "constants-pressure-001",
        budget_version: "budget-pressure-001"
      },
      "/calibration-jobs/job-001/technical-review-submissions": {
        software_version: "app-0.1.0"
      },
      "/calibration-jobs/job-001/technical-review-approvals": {
        software_version: "app-0.1.0"
      },
      "/calibration-jobs/job-001/qa-release-approvals": {
        software_version: "app-0.1.0"
      },
      "/certificate-metadata": {
        job_id: "job-001",
        certificate_date: "2026-06-03",
        calibration_date: "2026-06-01",
        receipt_date: "2026-05-31",
        task_number: "TASK-2026-001",
        purchase_order: "PO-12345",
        client_name: "SIMVal customer",
        client_address: "Validated Road 1, 2800 Lyngby",
        procedure: "SIMVal SOP-TEMP-001",
        place: "SIMVal Temperature Laboratory, Lyngby",
        approved_by_label: "QA User",
        remarks: "ValProbe RT logger data reviewed.",
        traceability_statement: "Measurements are metrologically traceable.",
        uncertainty_statement: "Expanded uncertainty uses k=2.",
        ambient_conditions: "Room temperature 23 +/- 2 deg C.",
        temperature_scale: "ITS-90",
        software_version: "app-0.1.0"
      },
      "/reference-equipment-selections": {
        job_id: "job-001",
        equipment_id: "ref-001",
        simval_id: "SIM-T-001",
        equipment_type: "IRTD",
        serial_number: "IRT-123",
        discipline: "temperature",
        calibration_certificate_reference: "DANAK-CAL-12345",
        calibration_due_date: "2027-04-30",
        status: "active",
        range_minimum: -90,
        range_maximum: 140,
        range_unit: "deg C",
        traceability_statement: "Accredited calibration with SI traceability.",
        software_version: "app-0.1.0"
      },
      "/certificate-previews": {
        job_id: "job-001",
        template_version: "template-2026-001",
        software_version: "app-0.1.0",
        accreditation_mark_allowed: true
      },
      "/certificate-preview-pdfs": {
        job_id: "job-001",
        certificate_id: "cert-preview-001",
        certificate_number: "SIMVAL-PREVIEW-0001",
        template_version: "template-2026-001",
        software_version: "app-0.1.0",
        accreditation_mark_allowed: false
      },
      "/certificate-rendered-releases": {
        job_id: "job-001",
        certificate_id: "cert-001",
        certificate_number: "SIMVAL-CAL-0001",
        artifact_id: "artifact-001",
        template_version: "template-2026-001",
        software_version: "app-0.1.0",
        accreditation_mark_allowed: true
      },
      "/certificate-rendered-releases/allocated": {
        job_id: "job-001",
        certificate_id: "cert-001",
        certificate_number_prefix: "SIMVAL-CAL",
        certificate_number_padding: 4,
        artifact_id: "artifact-001",
        template_version: "template-2026-001",
        software_version: "app-0.1.0",
        accreditation_mark_allowed: true
      },
      "/certificate-revisions": {
        certificate_id: "cert-001",
        revision_id: "rev-001",
        reason: "Controlled correction after QA approval.",
        software_version: "app-0.1.0"
      },
      "/certificate-history/job-001": "",
      "/certificate-artifacts/artifact-001": ""
    };

    let operations = [];
    const workflowEl = document.getElementById("workflow");
    const operationEl = document.getElementById("operation");
    const requestBodyEl = document.getElementById("requestBody");
    const responseBodyEl = document.getElementById("responseBody");
    const wizardSteps = Array.from(document.querySelectorAll(".wizard-step"));
    const wizardPanels = Array.from(document.querySelectorAll("[data-wizard-panel]"));
    const wizardStepOrder = wizardSteps.map(step => step.dataset.stepTarget);
    const localActorSessions = {
      operator: "lab-flow-operator",
      technical: "lab-flow-technical",
      qa: "lab-flow-qa",
      release: "lab-flow-release"
    };
    let wizardStepIndex = 0;
    let lastUploadedPressureFileId = "";
    let lastCertificateObjectUrl = "";

    function pretty(value) {
      return typeof value === "string" ? value : JSON.stringify(value, null, 2);
    }

    function isLocalhost() {
      return ["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname);
    }

    function setStepStatus(stepId, state) {
      const statusEl = document.querySelector(`[data-step-status="${stepId}"]`);
      if (!statusEl) return;
      statusEl.className = "status-pill";
      if (state === "active" || state === "done") {
        statusEl.classList.add(state);
      }
      statusEl.textContent = state === "done" ? "Done" : state === "active" ? "Active" : "Pending";
    }

    function showWizardStep(stepId) {
      const nextIndex = wizardStepOrder.indexOf(stepId);
      if (nextIndex < 0) return;
      wizardStepIndex = nextIndex;
      wizardSteps.forEach(step => {
        const active = step.dataset.stepTarget === stepId;
        step.classList.toggle("active", active);
        step.setAttribute("aria-selected", active ? "true" : "false");
      });
      wizardPanels.forEach(panel => {
        panel.hidden = panel.dataset.wizardPanel !== stepId;
      });
      for (const statusStep of wizardStepOrder) {
        const statusEl = document.querySelector(`[data-step-status="${statusStep}"]`);
        if (!statusEl || statusEl.textContent === "Done") continue;
        setStepStatus(statusStep, statusStep === stepId ? "active" : "pending");
      }
    }

    function moveWizardStep(delta) {
      const nextIndex = Math.max(0, Math.min(wizardStepOrder.length - 1, wizardStepIndex + delta));
      showWizardStep(wizardStepOrder[nextIndex]);
    }

    function bootstrapLocalSession() {
      const sessionEl = document.getElementById("sessionId");
      let storedSession = "";
      try { storedSession = window.localStorage.getItem("simvalSessionId") || ""; } catch (_error) {}
      if (!sessionEl.value.trim() && storedSession) {
        sessionEl.value = storedSession;
      }
      if (!sessionEl.value.trim() && isLocalhost()) {
        sessionEl.value = "lab-flow-test";
      }
      sessionEl.addEventListener("change", () => {
        try { window.localStorage.setItem("simvalSessionId", sessionEl.value.trim()); } catch (_error) {}
      });
    }

    function setManualPressureDefaults() {
      const jobIdEl = document.getElementById("manualPressureJobId");
      if (!jobIdEl.value.trim()) {
        jobIdEl.value = `manual-pressure-${Date.now()}`;
      }
      document.getElementById("jobId").value = jobIdEl.value.trim();
    }

    function syncJobIds() {
      setManualPressureDefaults();
      const jobId = document.getElementById("manualPressureJobId").value.trim();
      document.getElementById("jobId").value = jobId;
      return jobId;
    }

    function updatePressureSummary() {
      document.getElementById("pressurePointSummary").textContent =
        `${document.getElementById("manualPressureReference").value.trim()} ${document.getElementById("manualPressureUnit").value.trim()}`;
      document.getElementById("certificateSummary").textContent =
        document.getElementById("manualPressureCertificateNumber").value.trim();
    }

    function setSourceFileStatus(message) {
      document.getElementById("sourceFileStatus").textContent = message;
    }

    function appendSourceFileStatus(message) {
      const statusEl = document.getElementById("sourceFileStatus");
      const separator = statusEl.textContent ? String.fromCharCode(10) : "";
      statusEl.textContent = `${statusEl.textContent}${separator}${message}`;
    }

    function setBudgetStatus(message) {
      document.getElementById("budgetStatus").textContent = message;
    }

    function appendBudgetStatus(message) {
      const statusEl = document.getElementById("budgetStatus");
      const separator = statusEl.textContent ? String.fromCharCode(10) : "";
      statusEl.textContent = `${statusEl.textContent}${separator}${message}`;
    }

    function fieldValue(id) {
      return document.getElementById(id).value.trim();
    }

    function numericField(id) {
      const value = Number(fieldValue(id));
      if (!Number.isFinite(value)) {
        throw new Error(`${id} must be numeric.`);
      }
      return value;
    }

    function parseDelimitedLine(line, delimiter) {
      const cells = [];
      let cell = "";
      let quoted = false;
      for (let index = 0; index < line.length; index += 1) {
        const char = line[index];
        if (char === '"') {
          if (quoted && line[index + 1] === '"') {
            cell += '"';
            index += 1;
          } else {
            quoted = !quoted;
          }
        } else if (char === delimiter && !quoted) {
          cells.push(cell.trim());
          cell = "";
        } else {
          cell += char;
        }
      }
      cells.push(cell.trim());
      return cells;
    }

    function parseDelimitedRows(rawText) {
      return rawText.split(/\\r?\\n/)
        .map(line => line.trim())
        .filter(line => line.length > 0)
        .map(line => {
          const delimiter = line.includes("\t") ? "\t" : ",";
          return parseDelimitedLine(line, delimiter);
        });
    }

    function normaliseHeader(value) {
      return value.toLowerCase().replace(/[^a-z0-9]/g, "");
    }

    function headerIndex(headers, names, fallback) {
      const normalised = headers.map(normaliseHeader);
      for (const name of names) {
        const index = normalised.indexOf(name);
        if (index >= 0) return index;
      }
      return fallback;
    }

    function applyManualPressureRowsFromText(rawText) {
      const rows = parseDelimitedRows(rawText);
      if (rows.length < 2) {
        throw new Error("Pressure source file must contain a header row and at least one reading row.");
      }
      const header = rows[0];
      const timestampIndex = headerIndex(header, ["timestamp", "time", "datetime"], 0);
      const referenceIndex = headerIndex(header, ["reference", "referencepressure", "referencevalue"], 1);
      const indicationIndex = headerIndex(header, ["indication", "indicationpressure", "dut", "dutindication"], 2);
      const unitIndex = headerIndex(header, ["unit", "units"], 3);
      const dataRows = rows.slice(1).filter(row => row.length > Math.max(referenceIndex, indicationIndex));
      if (dataRows.length === 0) {
        throw new Error("Pressure source file does not contain parseable reading rows.");
      }
      const first = dataRows[0];
      const second = dataRows[1] || dataRows[0];
      const referencePressure = Number(first[referenceIndex]);
      const indicationA = Number(first[indicationIndex]);
      const indicationB = Number(second[indicationIndex]);
      if (!Number.isFinite(referencePressure) || !Number.isFinite(indicationA) || !Number.isFinite(indicationB)) {
        throw new Error("Pressure source file reference and indication columns must be numeric.");
      }
      document.getElementById("manualPressureReference").value = String(referencePressure);
      document.getElementById("manualPressureIndicationA").value = String(indicationA);
      document.getElementById("manualPressureIndicationB").value = String(indicationB);
      if (first[unitIndex]) {
        document.getElementById("manualPressureUnit").value = first[unitIndex];
      }
      updatePressureSummary();
      return dataRows.map((row, index) => ({
        timestamp: row[timestampIndex] || `2026-06-17T09:${String(21 + index).padStart(2, "0")}:00+00:00`,
        reference: Number(row[referenceIndex]),
        indication: Number(row[indicationIndex]),
        unit: row[unitIndex] || fieldValue("manualPressureUnit"),
        rowNumber: index + 2
      }));
    }

    function manualPressureStatus(message) {
      document.getElementById("manualPressureStatus").textContent = message;
    }

    function appendManualPressureStatus(message) {
      const statusEl = document.getElementById("manualPressureStatus");
      const separator = statusEl.textContent ? String.fromCharCode(10) : "";
      statusEl.textContent = `${statusEl.textContent}${separator}${message}`;
    }

    function requireSessionId() {
      const sessionId = document.getElementById("sessionId").value.trim();
      if (!sessionId) {
        throw new Error("Session ID is required.");
      }
      return sessionId;
    }

    async function parseResponse(response) {
      const text = await response.text();
      let parsed = text;
      try { parsed = JSON.parse(text); } catch (_error) {}
      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText}: ${pretty(parsed)}`);
      }
      return parsed;
    }

    async function postJson(path, payload) {
      const response = await fetch(path, {
        method: "POST",
        headers: { ...sessionHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      return parseResponse(response);
    }

    function loadSample() {
      const op = operations[operationEl.selectedIndex];
      requestBodyEl.value = pretty(samples[op.path] ?? {});
    }

    async function loadContract() {
      const response = await fetch("/app/workflow");
      const contract = await response.json();
      operations = [];
      workflowEl.innerHTML = "";
      operationEl.innerHTML = "";
      for (const step of contract.steps) {
        const card = document.createElement("section");
        card.className = "step";
        card.innerHTML = `<h2>${step.label}</h2><p>${step.status}</p>`;
        const actionWrap = document.createElement("div");
        actionWrap.className = "actions";
        for (const action of step.actions) {
          operations.push(action);
          const option = document.createElement("option");
          option.textContent = `${action.method} ${action.path}`;
          operationEl.appendChild(option);
          const button = document.createElement("button");
          button.className = "secondary";
          button.textContent = action.label;
          button.addEventListener("click", () => {
            operationEl.selectedIndex = operations.indexOf(action);
            loadSample();
          });
          actionWrap.appendChild(button);
        }
        card.appendChild(actionWrap);
        if (step.deferred.length) {
          const deferred = document.createElement("p");
          deferred.className = "danger";
          deferred.textContent = step.deferred.join(" ");
          card.appendChild(deferred);
        }
        workflowEl.appendChild(card);
      }
      loadSample();
    }

    async function sendRequest() {
      const op = operations[operationEl.selectedIndex];
      const headers = {};
      const sessionId = document.getElementById("sessionId").value.trim();
      if (op.requires_session && sessionId) headers["X-Session-Id"] = sessionId;
      const init = { method: op.method, headers };
      const body = requestBodyEl.value.trim();
      if (op.method !== "GET" && body) {
        init.headers["Content-Type"] = "application/json";
        init.body = body;
      }
      responseBodyEl.textContent = "Waiting...";
      try {
        const response = await fetch(op.path, init);
        const text = await response.text();
        let parsed = text;
        try { parsed = JSON.parse(text); } catch (_error) {}
        responseBodyEl.textContent = `${response.status} ${response.statusText}\n\n${pretty(parsed)}`;
      } catch (error) {
        responseBodyEl.textContent = String(error);
      }
    }

    function sessionHeaders() {
      const headers = {};
      const sessionId = document.getElementById("sessionId").value.trim();
      if (sessionId) headers["X-Session-Id"] = sessionId;
      return headers;
    }

    function sessionHeadersForStage(stage) {
      if (isLocalhost() && localActorSessions[stage]) {
        return { "X-Session-Id": localActorSessions[stage] };
      }
      return sessionHeaders();
    }

    async function postJsonForStage(stage, path, payload) {
      const response = await fetch(path, {
        method: "POST",
        headers: { ...sessionHeadersForStage(stage), "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      return parseResponse(response);
    }

    async function createJob() {
      const jobId = syncJobIds();
      const payload = {
        job_id: jobId,
        client_name: document.getElementById("clientName").value.trim(),
        client_address: document.getElementById("clientAddress").value.trim(),
        discipline: document.getElementById("jobDiscipline").value,
        measurement_mode: document.getElementById("measurementMode").value,
        method: document.getElementById("jobMethod").value.trim(),
        software_version: document.getElementById("uploadSoftwareVersion").value.trim()
      };
      responseBodyEl.textContent = "Waiting...";
      try {
        const response = await fetch("/calibration-jobs", {
          method: "POST",
          headers: { ...sessionHeaders(), "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const parsed = await response.json();
        if (response.ok) setStepStatus("job", "done");
        responseBodyEl.textContent = `${response.status} ${response.statusText}\n\n${pretty(parsed)}`;
      } catch (error) {
        responseBodyEl.textContent = String(error);
      }
    }

    async function uploadSourceFile() {
      setSourceFileStatus("");
      const fileInput = document.getElementById("sourceFile");
      const file = fileInput.files[0];
      if (!file) {
        responseBodyEl.textContent = "Select a source file first.";
        setSourceFileStatus("No file selected.");
        return;
      }
      const jobId = syncJobIds();
      let fileText = "";
      try {
        fileText = await file.text();
        applyManualPressureRowsFromText(fileText);
        appendSourceFileStatus("Read pressure rows from selected file");
      } catch (error) {
        appendSourceFileStatus(`File retained; manual fields unchanged: ${error.message || String(error)}`);
      }
      const params = new URLSearchParams({
        original_filename: file.name,
        file_kind: document.getElementById("uploadFileKind").value,
        software_version: document.getElementById("uploadSoftwareVersion").value.trim()
      });
      responseBodyEl.textContent = "Uploading...";
      try {
        const response = await fetch(`/calibration-jobs/${encodeURIComponent(jobId)}/files?${params}`, {
          method: "POST",
          headers: { ...sessionHeadersForStage("operator"), "Content-Type": "application/octet-stream" },
          body: await file.arrayBuffer()
        });
        const parsed = await response.json();
        if (response.ok && parsed.uploaded_file_id && parsed.file_kind === "calibration_xlsx") {
          document.getElementById("calibrationUploadedFileId").value = parsed.uploaded_file_id;
        }
        if (response.ok && parsed.uploaded_file_id && parsed.file_kind === "verification_pdf") {
          document.getElementById("verificationUploadedFileId").value = parsed.uploaded_file_id;
        }
        if (response.ok && parsed.uploaded_file_id) {
          lastUploadedPressureFileId = parsed.uploaded_file_id;
          appendSourceFileStatus(`Uploaded ${file.name}`);
          setStepStatus("measurement", "active");
        }
        responseBodyEl.textContent = `${response.status} ${response.statusText}\n\n${pretty(parsed)}`;
      } catch (error) {
        responseBodyEl.textContent = String(error);
        appendSourceFileStatus(`Upload blocked: ${error.message || String(error)}`);
      }
    }

    async function reviewImports() {
      const jobId = syncJobIds();
      responseBodyEl.textContent = "Waiting...";
      try {
        const response = await fetch(`/calibration-jobs/${encodeURIComponent(jobId)}/imports`, {
          method: "GET",
          headers: sessionHeaders()
        });
        const parsed = await response.json();
        responseBodyEl.textContent = `${response.status} ${response.statusText}\n\n${pretty(parsed)}`;
      } catch (error) {
        responseBodyEl.textContent = String(error);
      }
    }

    async function prepareTemperatureData() {
      const jobId = syncJobIds();
      const rawSetpoints = document.getElementById("temperatureSetpoints").value;
      const setpoints = rawSetpoints.split(",").map(value => Number(value.trim())).filter(value => Number.isFinite(value));
      const payload = {
        calibration_uploaded_file_id: document.getElementById("calibrationUploadedFileId").value.trim(),
        setpoints,
        unit: "deg C",
        software_version: document.getElementById("uploadSoftwareVersion").value.trim()
      };
      responseBodyEl.textContent = "Waiting...";
      try {
        const response = await fetch(`/calibration-jobs/${encodeURIComponent(jobId)}/temperature-data-entry`, {
          method: "POST",
          headers: { ...sessionHeaders(), "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const parsed = await response.json();
        responseBodyEl.textContent = `${response.status} ${response.statusText}\n\n${pretty(parsed)}`;
      } catch (error) {
        responseBodyEl.textContent = String(error);
      }
    }

    function parseTableRows(rawText) {
      return rawText.split(/\\r?\\n/)
        .map(line => line.trim())
        .filter(line => line.length > 0)
        .map(line => {
          const delimiter = line.includes("\t") ? "\t" : ",";
          return line.split(delimiter).map(cell => cell.trim());
        });
    }

    async function recordIrtdRows() {
      const jobId = syncJobIds();
      const payload = {
        calibration_uploaded_file_id: document.getElementById("calibrationUploadedFileId").value.trim(),
        verification_uploaded_file_id: document.getElementById("verificationUploadedFileId").value.trim(),
        rows: parseTableRows(document.getElementById("irtdRows").value),
        unit: "deg C",
        software_version: document.getElementById("uploadSoftwareVersion").value.trim()
      };
      responseBodyEl.textContent = "Waiting...";
      try {
        const response = await fetch(`/calibration-jobs/${encodeURIComponent(jobId)}/verification-irtd-rows`, {
          method: "POST",
          headers: { ...sessionHeaders(), "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const parsed = await response.json();
        responseBodyEl.textContent = `${response.status} ${response.statusText}\n\n${pretty(parsed)}`;
      } catch (error) {
        responseBodyEl.textContent = String(error);
      }
    }

    async function selectTemperatureWindow() {
      const jobId = syncJobIds();
      const setpointValues = document.getElementById("temperatureSetpoints").value
        .split(",")
        .map(value => Number(value.trim()))
        .filter(value => Number.isFinite(value));
      const payload = {
        window_id: document.getElementById("windowId").value.trim(),
        dut_id: document.getElementById("windowDutId").value.trim(),
        dut_channel_id: document.getElementById("windowChannelId").value.trim(),
        setpoint: setpointValues[0],
        unit: "deg C",
        start_timestamp: document.getElementById("windowStart").value.trim(),
        end_timestamp: document.getElementById("windowEnd").value.trim(),
        software_version: document.getElementById("uploadSoftwareVersion").value.trim()
      };
      responseBodyEl.textContent = "Waiting...";
      try {
        const response = await fetch(`/calibration-jobs/${encodeURIComponent(jobId)}/temperature-windows`, {
          method: "POST",
          headers: { ...sessionHeaders(), "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const parsed = await response.json();
        responseBodyEl.textContent = `${response.status} ${response.statusText}\n\n${pretty(parsed)}`;
      } catch (error) {
        responseBodyEl.textContent = String(error);
      }
    }

    async function completeTemperatureWindows() {
      const jobId = syncJobIds();
      const payload = {
        software_version: document.getElementById("uploadSoftwareVersion").value.trim()
      };
      responseBodyEl.textContent = "Waiting...";
      try {
        const response = await fetch(`/calibration-jobs/${encodeURIComponent(jobId)}/temperature-windows/complete`, {
          method: "POST",
          headers: { ...sessionHeaders(), "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const parsed = await response.json();
        responseBodyEl.textContent = `${response.status} ${response.statusText}\n\n${pretty(parsed)}`;
      } catch (error) {
        responseBodyEl.textContent = String(error);
      }
    }

    async function calculateTemperature() {
      const jobId = syncJobIds();
      const setpointValues = document.getElementById("temperatureSetpoints").value
        .split(",")
        .map(value => Number(value.trim()))
        .filter(value => Number.isFinite(value));
      const payload = {
        uncertainty_inputs: [{
          setpoint: setpointValues[0],
          unit: "deg C",
          cmc_floor: document.getElementById("cmcFloor").value.trim(),
          reference_expanded_uncertainty: Number(document.getElementById("referenceExpandedUncertainty").value),
          bath_expanded_uncertainty: Number(document.getElementById("bathExpandedUncertainty").value),
          dut_resolution: Number(document.getElementById("dutResolution").value)
        }],
        software_version: document.getElementById("uploadSoftwareVersion").value.trim(),
        calculation_engine_version: document.getElementById("calculationEngineVersion").value.trim(),
        constant_set_version: document.getElementById("constantSetVersion").value.trim(),
        budget_version: document.getElementById("budgetVersion").value.trim()
      };
      responseBodyEl.textContent = "Waiting...";
      try {
        const response = await fetch(`/calibration-jobs/${encodeURIComponent(jobId)}/temperature-calculations`, {
          method: "POST",
          headers: { ...sessionHeaders(), "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const parsed = await response.json();
        responseBodyEl.textContent = `${response.status} ${response.statusText}\n\n${pretty(parsed)}`;
      } catch (error) {
        responseBodyEl.textContent = String(error);
      }
    }

    async function postJobWorkflowAction(pathSuffix) {
      const jobId = syncJobIds();
      const payload = {
        software_version: document.getElementById("uploadSoftwareVersion").value.trim()
      };
      responseBodyEl.textContent = "Waiting...";
      try {
        const response = await fetch(`/calibration-jobs/${encodeURIComponent(jobId)}/${pathSuffix}`, {
          method: "POST",
          headers: { ...sessionHeaders(), "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const parsed = await response.json();
        responseBodyEl.textContent = `${response.status} ${response.statusText}\n\n${pretty(parsed)}`;
      } catch (error) {
        responseBodyEl.textContent = String(error);
      }
    }

    function samplePayload(path) {
      const payload = JSON.parse(JSON.stringify(samples[path] ?? {}));
      if (payload && typeof payload === "object" && "job_id" in payload) {
        payload.job_id = syncJobIds();
      }
      return payload;
    }

    async function postSample(path) {
      responseBodyEl.textContent = "Waiting...";
      try {
        const response = await fetch(path, {
          method: "POST",
          headers: { ...sessionHeaders(), "Content-Type": "application/json" },
          body: JSON.stringify(samplePayload(path))
        });
        const parsed = await response.json();
        responseBodyEl.textContent = `${response.status} ${response.statusText}\n\n${pretty(parsed)}`;
      } catch (error) {
        responseBodyEl.textContent = String(error);
      }
    }

    function pressureNumber(id) {
      const value = Number(document.getElementById(id).value);
      if (!Number.isFinite(value)) {
        throw new Error(`${id} must be numeric.`);
      }
      return value;
    }

    function manualPressureIds(jobId) {
      return {
        dutId: `${jobId}-dut-001`,
        windowId: `${jobId}-window-001`,
        pointId: `${jobId}-point-001`,
        constantSetVersion: `${jobId}-constants`,
        budgetVersion: `${jobId}-budget`
      };
    }

    async function uploadManualPressureEvidence(jobId, softwareVersion, stage = "operator") {
      const unit = document.getElementById("manualPressureUnit").value.trim();
      const rows = [
        "timestamp,reference,indication,unit",
        `2026-06-17T09:21:00+00:00,${pressureNumber("manualPressureReference")},${pressureNumber("manualPressureIndicationA")},${unit}`,
        `2026-06-17T09:22:00+00:00,${pressureNumber("manualPressureReference")},${pressureNumber("manualPressureIndicationB")},${unit}`
      ];
      const params = new URLSearchParams({
        original_filename: "manual-pressure-readings.csv",
        file_kind: "other",
        software_version: softwareVersion,
        parser_version: "manual-pressure-entry-v1"
      });
      const response = await fetch(`/calibration-jobs/${encodeURIComponent(jobId)}/files?${params}`, {
        method: "POST",
        headers: { ...sessionHeadersForStage(stage), "Content-Type": "application/octet-stream" },
        body: rows.join(String.fromCharCode(10)) + String.fromCharCode(10)
      });
      return parseResponse(response);
    }

    async function uploadSelectedOrGeneratedPressureEvidence(jobId, softwareVersion, stage = "operator") {
      const fileInput = document.getElementById("sourceFile");
      const file = fileInput.files[0];
      if (!file) {
        const generated = await uploadManualPressureEvidence(jobId, softwareVersion, stage);
        lastUploadedPressureFileId = generated.uploaded_file_id;
        appendSourceFileStatus("Uploaded generated pressure evidence");
        return generated;
      }
      const rawText = await file.text();
      try {
        applyManualPressureRowsFromText(rawText);
        appendSourceFileStatus("Read pressure rows from selected file");
      } catch (error) {
        appendSourceFileStatus(`File retained; manual fields unchanged: ${error.message || String(error)}`);
      }
      const params = new URLSearchParams({
        original_filename: file.name,
        file_kind: document.getElementById("uploadFileKind").value,
        software_version: softwareVersion,
        parser_version: "manual-pressure-entry-v1"
      });
      const response = await fetch(`/calibration-jobs/${encodeURIComponent(jobId)}/files?${params}`, {
        method: "POST",
        headers: { ...sessionHeadersForStage(stage), "Content-Type": "application/octet-stream" },
        body: await file.arrayBuffer()
      });
      const upload = await parseResponse(response);
      lastUploadedPressureFileId = upload.uploaded_file_id;
      appendSourceFileStatus(`Uploaded ${file.name}`);
      return upload;
    }

    function pressureRunContext() {
      const jobId = syncJobIds();
      const ids = manualPressureIds(jobId);
      return {
        jobId,
        ids,
        certificateNumber: fieldValue("manualPressureCertificateNumber"),
        softwareVersion: fieldValue("uploadSoftwareVersion") || "app-0.1.0",
        unit: fieldValue("manualPressureUnit"),
        referencePressure: numericField("manualPressureReference"),
        indicationA: numericField("manualPressureIndicationA"),
        indicationB: numericField("manualPressureIndicationB")
      };
    }

    function calibrationJobPayload(context) {
      return {
        job_id: context.jobId,
        client_name: fieldValue("clientName"),
        client_address: fieldValue("clientAddress"),
        discipline: "pressure",
        measurement_mode: "manual",
        method: fieldValue("jobMethod"),
        software_version: context.softwareVersion
      };
    }

    function metadataPayload(context) {
      return {
        job_id: context.jobId,
        certificate_date: fieldValue("certificateDate"),
        calibration_date: fieldValue("calibrationDate"),
        receipt_date: fieldValue("receiptDate"),
        task_number: fieldValue("taskNumber"),
        purchase_order: fieldValue("purchaseOrder"),
        client_name: fieldValue("clientName"),
        client_address: fieldValue("clientAddress"),
        procedure: fieldValue("procedure"),
        place: fieldValue("place"),
        approved_by_label: fieldValue("approvedByLabel"),
        remarks: fieldValue("remarks"),
        traceability_statement: fieldValue("traceabilityStatement"),
        uncertainty_statement: fieldValue("uncertaintyStatement"),
        ambient_conditions: fieldValue("ambientConditions"),
        temperature_scale: context.unit,
        software_version: context.softwareVersion
      };
    }

    function referenceEquipmentPayload(context) {
      return {
        job_id: context.jobId,
        equipment_id: `${context.jobId}-ref-001`,
        simval_id: "SIM-P-001",
        equipment_type: "Pressure calibrator",
        serial_number: "PCAL-123",
        discipline: "pressure",
        calibration_certificate_reference: "DANAK-PRESS-12345",
        calibration_due_date: "2027-06-30",
        status: "active",
        range_minimum: 0.0,
        range_maximum: 20.0,
        range_unit: context.unit,
        traceability_statement: "Accredited pressure calibration with SI traceability.",
        software_version: context.softwareVersion
      };
    }

    function manualPressureEntryPayload(context, upload) {
      return {
        uploaded_file_id: upload.uploaded_file_id,
        dut_id: context.ids.dutId,
        dut_make: fieldValue("dutMake"),
        dut_model: fieldValue("dutModel"),
        dut_serial_number: fieldValue("dutSerialNumber"),
        dut_channel_id: fieldValue("dutChannelId"),
        window_id: context.ids.windowId,
        setpoint: context.referencePressure,
        unit: context.unit,
        readings: [
          {
            timestamp: "2026-06-17T09:21:00+00:00",
            value: context.indicationA,
            source_label: "Pressure",
            row_number: 2,
            column_label: "indication"
          },
          {
            timestamp: "2026-06-17T09:22:00+00:00",
            value: context.indicationB,
            source_label: "Pressure",
            row_number: 3,
            column_label: "indication"
          }
        ],
        software_version: context.softwareVersion
      };
    }

    function constantSetPayload(context) {
      return {
        version: context.ids.constantSetVersion,
        discipline: "pressure",
        effective_from: "2026-01-01T00:00:00+00:00",
        software_version: context.softwareVersion
      };
    }

    function uncertaintyBudgetPayload(context) {
      return {
        version: context.ids.budgetVersion,
        budget_type: "pressure",
        method: fieldValue("budgetMethod"),
        discipline: "pressure",
        linked_constant_set_version: context.ids.constantSetVersion,
        software_version: context.softwareVersion
      };
    }

    function pressureCalculationPayload(context) {
      return {
        manual_points: [
          {
            point_id: context.ids.pointId,
            dut_id: context.ids.dutId,
            measurement_window_id: context.ids.windowId,
            reference_pressure: context.referencePressure,
            indication_values: [context.indicationA, context.indicationB],
            setpoint: context.referencePressure,
            unit: context.unit,
            pressure_kind: fieldValue("pressureKind"),
            cmc_floor: fieldValue("cmcFloor"),
            reference_expanded_uncertainty: numericField("referenceExpandedUncertainty"),
            reference_coverage_factor: numericField("referenceCoverageFactor"),
            dut_resolution: numericField("dutResolution"),
            barometer_expanded_uncertainty: numericField("barometerExpandedUncertainty"),
            barometer_coverage_factor: numericField("barometerCoverageFactor"),
            coverage_factor: numericField("coverageFactor"),
            additional_standard_uncertainties: []
          }
        ],
        automatic_points: [],
        software_version: context.softwareVersion,
        calculation_engine_version: fieldValue("calculationEngineVersion"),
        constant_set_version: context.ids.constantSetVersion,
        budget_version: context.ids.budgetVersion
      };
    }

    async function createUncertaintyBudget() {
      setBudgetStatus("");
      try {
        const context = pressureRunContext();
        document.getElementById("constantSetVersion").value = context.ids.constantSetVersion;
        document.getElementById("budgetVersion").value = context.ids.budgetVersion;
        appendBudgetStatus("Approving pressure constants");
        await postJsonForStage("qa", "/constant-sets/approved", constantSetPayload(context));
        appendBudgetStatus("Approving uncertainty budget");
        await postJsonForStage("qa", "/uncertainty-budgets/approved", uncertaintyBudgetPayload(context));
        appendBudgetStatus(`Budget ready: ${context.ids.budgetVersion}`);
        setStepStatus("equipment", "done");
      } catch (error) {
        appendBudgetStatus(`Budget blocked: ${error.message || String(error)}`);
        responseBodyEl.textContent = String(error);
      }
    }

    async function calculatePressure() {
      setBudgetStatus("");
      try {
        const context = pressureRunContext();
        appendBudgetStatus("Calculating pressure point");
        const calculation = await postJsonForStage(
          "operator",
          `/calibration-jobs/${encodeURIComponent(context.jobId)}/pressure-calculations`,
          pressureCalculationPayload(context)
        );
        appendBudgetStatus(`Calculated ${calculation.summaries.length} pressure point`);
        responseBodyEl.textContent = pretty(calculation);
        setStepStatus("calculation", "done");
        showWizardStep("review");
      } catch (error) {
        appendBudgetStatus(`Calculation blocked: ${error.message || String(error)}`);
        responseBodyEl.textContent = String(error);
      }
    }

    async function runManualPressurePreview() {
      const linkEl = document.getElementById("manualPressurePdfLink");
      if (linkEl.dataset.objectUrl) {
        URL.revokeObjectURL(linkEl.dataset.objectUrl);
        delete linkEl.dataset.objectUrl;
      }
      linkEl.hidden = true;
      manualPressureStatus("");
      responseBodyEl.textContent = "";
      try {
        requireSessionId();
        const jobId = syncJobIds();
        const certificateNumber = document.getElementById("manualPressureCertificateNumber").value.trim();
        const softwareVersion = document.getElementById("uploadSoftwareVersion").value.trim() || "app-0.1.0";
        const unit = document.getElementById("manualPressureUnit").value.trim();
        const referencePressure = pressureNumber("manualPressureReference");
        const indicationA = pressureNumber("manualPressureIndicationA");
        const indicationB = pressureNumber("manualPressureIndicationB");
        const ids = manualPressureIds(jobId);
        updatePressureSummary();
        showWizardStep("review");

        document.getElementById("jobId").value = jobId;
        document.getElementById("jobDiscipline").value = "pressure";
        document.getElementById("measurementMode").value = "manual";
        document.getElementById("jobMethod").value = "SIMVal manual pressure calibration method";
        document.getElementById("constantSetVersion").value = ids.constantSetVersion;
        document.getElementById("budgetVersion").value = ids.budgetVersion;

        appendManualPressureStatus("Creating pressure job");
        await postJson("/calibration-jobs", {
          job_id: jobId,
          client_name: "SIMVal pressure customer",
          client_address: "Pressure Road 1, 2800 Lyngby",
          discipline: "pressure",
          measurement_mode: "manual",
          method: "SIMVal manual pressure calibration method",
          software_version: softwareVersion
        });
        setStepStatus("job", "done");

        appendManualPressureStatus("Capturing certificate metadata");
        await postJson("/certificate-metadata", {
          job_id: jobId,
          certificate_date: "2026-06-17",
          calibration_date: "2026-06-17",
          receipt_date: "2026-06-16",
          task_number: "TASK-PRESSURE-2026-001",
          purchase_order: "PO-PRESSURE-12345",
          client_name: "SIMVal pressure customer",
          client_address: "Pressure Road 1, 2800 Lyngby",
          procedure: "SIMVal SOP-PRESS-001",
          place: "SIMVal Pressure Laboratory, Lyngby",
          approved_by_label: "QA Preview User",
          remarks: "Manual pressure readings entered from controlled source evidence.",
          traceability_statement: "Pressure measurements are traceable through the selected reference pressure standard.",
          uncertainty_statement: "Expanded uncertainty is reported with coverage factor k=2.",
          ambient_conditions: "Room temperature 23 +/- 2 deg C; stable laboratory conditions.",
          temperature_scale: unit,
          software_version: softwareVersion
        });
        setStepStatus("metadata", "done");

        appendManualPressureStatus("Selecting pressure reference equipment");
        await postJson("/reference-equipment-selections", {
          job_id: jobId,
          equipment_id: `${jobId}-ref-001`,
          simval_id: "SIM-P-001",
          equipment_type: "Pressure calibrator",
          serial_number: "PCAL-123",
          discipline: "pressure",
          calibration_certificate_reference: "DANAK-PRESS-12345",
          calibration_due_date: "2027-06-30",
          status: "active",
          range_minimum: 0.0,
          range_maximum: 20.0,
          range_unit: unit,
          traceability_statement: "Accredited pressure calibration with SI traceability.",
          software_version: softwareVersion
        });
        setStepStatus("equipment", "active");

        appendManualPressureStatus("Uploading pressure source evidence");
        const upload = await uploadManualPressureEvidence(jobId, softwareVersion);

        appendManualPressureStatus("Recording manual pressure readings");
        await postJson(`/calibration-jobs/${encodeURIComponent(jobId)}/pressure-manual-entry`, {
          uploaded_file_id: upload.uploaded_file_id,
          dut_id: ids.dutId,
          dut_make: "PressureCo",
          dut_model: "Gauge",
          dut_serial_number: "PG-001",
          dut_channel_id: "PG-001",
          window_id: ids.windowId,
          setpoint: referencePressure,
          unit,
          readings: [
            {
              timestamp: "2026-06-17T09:21:00+00:00",
              value: indicationA,
              source_label: "Pressure",
              row_number: 2,
              column_label: "indication"
            },
            {
              timestamp: "2026-06-17T09:22:00+00:00",
              value: indicationB,
              source_label: "Pressure",
              row_number: 3,
              column_label: "indication"
            }
          ],
          software_version: softwareVersion
        });
        setStepStatus("measurement", "done");

        appendManualPressureStatus("Approving pressure constants and budget");
        await postJson("/constant-sets/approved", {
          version: ids.constantSetVersion,
          discipline: "pressure",
          effective_from: "2026-01-01T00:00:00+00:00",
          software_version: softwareVersion
        });
        await postJson("/uncertainty-budgets/approved", {
          version: ids.budgetVersion,
          budget_type: "pressure",
          method: "SIMVal manual pressure calibration method",
          discipline: "pressure",
          linked_constant_set_version: ids.constantSetVersion,
          software_version: softwareVersion
        });
        setStepStatus("equipment", "done");

        appendManualPressureStatus("Calculating pressure point");
        const calculation = await postJson(`/calibration-jobs/${encodeURIComponent(jobId)}/pressure-calculations`, {
          manual_points: [
            {
              point_id: ids.pointId,
              dut_id: ids.dutId,
              measurement_window_id: ids.windowId,
              reference_pressure: referencePressure,
              indication_values: [indicationA, indicationB],
              setpoint: referencePressure,
              unit,
              pressure_kind: "gauge",
              cmc_floor: "0.001",
              reference_expanded_uncertainty: 0.004,
              reference_coverage_factor: 2.0,
              dut_resolution: 0.002,
              barometer_expanded_uncertainty: 0.0,
              barometer_coverage_factor: 2.0,
              coverage_factor: 2.0,
              additional_standard_uncertainties: []
            }
          ],
          automatic_points: [],
          software_version: softwareVersion,
          calculation_engine_version: "calc-engine-0.1.0",
          constant_set_version: ids.constantSetVersion,
          budget_version: ids.budgetVersion
        });
        setStepStatus("calculation", "done");

        appendManualPressureStatus("Rendering preview PDF");
        const pdfResponse = await fetch("/certificate-preview-pdfs", {
          method: "POST",
          headers: { ...sessionHeaders(), "Content-Type": "application/json" },
          body: JSON.stringify({
            job_id: jobId,
            certificate_id: `${jobId}-preview-cert`,
            certificate_number: certificateNumber,
            template_version: "template-pressure-preview-001",
            software_version: softwareVersion,
            accreditation_mark_allowed: false
          })
        });
        if (!pdfResponse.ok) {
          await parseResponse(pdfResponse);
        }
        const pdfBlob = await pdfResponse.blob();
        const pdfUrl = URL.createObjectURL(pdfBlob);
        linkEl.href = pdfUrl;
        linkEl.dataset.objectUrl = pdfUrl;
        linkEl.hidden = false;
        const checksum = pdfResponse.headers.get("X-SIMVal-Checksum-SHA256");
        document.getElementById("pdfSummary").textContent = `${pdfBlob.size} bytes`;
        setStepStatus("review", "done");
        appendManualPressureStatus("Preview PDF ready");
        responseBodyEl.textContent = pretty({
          job_id: jobId,
          certificate_number: certificateNumber,
          pdf_size_bytes: pdfBlob.size,
          checksum_sha256: checksum,
          summary_ids: calculation.summaries.map(summary => summary.point_id)
        });
        window.open(pdfUrl, "_blank", "noopener");
      } catch (error) {
        appendManualPressureStatus(`Blocked: ${error.message || String(error)}`);
        responseBodyEl.textContent = String(error);
      }
    }

    async function runFirstCertificate() {
      const previewLinkEl = document.getElementById("manualPressurePdfLink");
      const certificateLinkEl = document.getElementById("certificatePdfLink");
      if (previewLinkEl.dataset.objectUrl) {
        URL.revokeObjectURL(previewLinkEl.dataset.objectUrl);
        delete previewLinkEl.dataset.objectUrl;
      }
      if (certificateLinkEl.dataset.objectUrl) {
        URL.revokeObjectURL(certificateLinkEl.dataset.objectUrl);
        delete certificateLinkEl.dataset.objectUrl;
      }
      if (lastCertificateObjectUrl) {
        URL.revokeObjectURL(lastCertificateObjectUrl);
        lastCertificateObjectUrl = "";
      }
      previewLinkEl.hidden = true;
      certificateLinkEl.hidden = true;
      document.getElementById("pdfSummary").textContent = "Not rendered";
      document.getElementById("releaseSummary").textContent = "Not released";
      manualPressureStatus("");
      setSourceFileStatus("");
      setBudgetStatus("");
      responseBodyEl.textContent = "";
      try {
        if (!isLocalhost()) requireSessionId();
        const context = pressureRunContext();
        updatePressureSummary();
        showWizardStep("review");
        document.getElementById("jobDiscipline").value = "pressure";
        document.getElementById("measurementMode").value = "manual";
        document.getElementById("constantSetVersion").value = context.ids.constantSetVersion;
        document.getElementById("budgetVersion").value = context.ids.budgetVersion;

        appendManualPressureStatus("Creating pressure job");
        await postJsonForStage("operator", "/calibration-jobs", calibrationJobPayload(context));
        setStepStatus("job", "done");

        appendManualPressureStatus("Capturing certificate metadata");
        await postJsonForStage("operator", "/certificate-metadata", metadataPayload(context));
        setStepStatus("metadata", "done");

        appendManualPressureStatus("Selecting reference equipment");
        await postJsonForStage("operator", "/reference-equipment-selections", referenceEquipmentPayload(context));
        setStepStatus("equipment", "active");

        appendManualPressureStatus("Uploading source file");
        const upload = await uploadSelectedOrGeneratedPressureEvidence(
          context.jobId,
          context.softwareVersion,
          "operator"
        );

        appendManualPressureStatus("Recording manual readings");
        await postJsonForStage(
          "operator",
          `/calibration-jobs/${encodeURIComponent(context.jobId)}/pressure-manual-entry`,
          manualPressureEntryPayload(context, upload)
        );
        setStepStatus("measurement", "done");

        appendManualPressureStatus("Creating uncertainty budget");
        await postJsonForStage("qa", "/constant-sets/approved", constantSetPayload(context));
        await postJsonForStage("qa", "/uncertainty-budgets/approved", uncertaintyBudgetPayload(context));
        appendBudgetStatus(`Budget ready: ${context.ids.budgetVersion}`);
        setStepStatus("equipment", "done");

        appendManualPressureStatus("Calculating pressure point");
        const calculation = await postJsonForStage(
          "operator",
          `/calibration-jobs/${encodeURIComponent(context.jobId)}/pressure-calculations`,
          pressureCalculationPayload(context)
        );
        setStepStatus("calculation", "done");

        appendManualPressureStatus("Rendering preview PDF");
        const previewResponse = await fetch("/certificate-preview-pdfs", {
          method: "POST",
          headers: { ...sessionHeadersForStage("operator"), "Content-Type": "application/json" },
          body: JSON.stringify({
            job_id: context.jobId,
            certificate_id: `${context.jobId}-preview-cert`,
            certificate_number: context.certificateNumber,
            template_version: "template-pressure-preview-001",
            software_version: context.softwareVersion,
            accreditation_mark_allowed: false
          })
        });
        if (!previewResponse.ok) {
          await parseResponse(previewResponse);
        }
        const previewBlob = await previewResponse.blob();
        const previewUrl = URL.createObjectURL(previewBlob);
        previewLinkEl.href = previewUrl;
        previewLinkEl.dataset.objectUrl = previewUrl;
        previewLinkEl.hidden = false;
        document.getElementById("pdfSummary").textContent = `${previewBlob.size} bytes`;

        appendManualPressureStatus("Submitting technical review");
        await postJsonForStage(
          "operator",
          `/calibration-jobs/${encodeURIComponent(context.jobId)}/technical-review-submissions`,
          { software_version: context.softwareVersion }
        );
        appendManualPressureStatus("Approving technical review");
        await postJsonForStage(
          "technical",
          `/calibration-jobs/${encodeURIComponent(context.jobId)}/technical-review-approvals`,
          { software_version: context.softwareVersion }
        );
        appendManualPressureStatus("Approving QA release");
        await postJsonForStage(
          "qa",
          `/calibration-jobs/${encodeURIComponent(context.jobId)}/qa-release-approvals`,
          { software_version: context.softwareVersion }
        );

        appendManualPressureStatus("Releasing certificate PDF");
        const release = await postJsonForStage("release", "/certificate-rendered-releases", {
          job_id: context.jobId,
          certificate_id: `${context.jobId}-cert`,
          certificate_number: context.certificateNumber,
          artifact_id: `${context.jobId}-artifact`,
          template_version: "template-pressure-preview-001",
          software_version: context.softwareVersion,
          accreditation_mark_allowed: false
        });
        const artifact = release.artifacts[0];
        const artifactResponse = await fetch(`/certificate-artifacts/${encodeURIComponent(artifact.artifact_id)}`, {
          headers: sessionHeadersForStage("release")
        });
        if (!artifactResponse.ok) {
          await parseResponse(artifactResponse);
        }
        const artifactBlob = await artifactResponse.blob();
        const artifactUrl = URL.createObjectURL(artifactBlob);
        lastCertificateObjectUrl = artifactUrl;
        certificateLinkEl.href = artifactUrl;
        certificateLinkEl.dataset.objectUrl = artifactUrl;
        certificateLinkEl.hidden = false;
        document.getElementById("releaseSummary").textContent = release.certificate_number;
        setStepStatus("review", "done");
        appendManualPressureStatus("Certificate PDF ready");
        responseBodyEl.textContent = pretty({
          job_id: context.jobId,
          certificate_number: release.certificate_number,
          artifact_id: artifact.artifact_id,
          artifact_bytes: artifactBlob.size,
          checksum_sha256: artifact.checksum_sha256,
          summary_ids: calculation.summaries.map(summary => summary.point_id)
        });
      } catch (error) {
        appendManualPressureStatus(`Blocked: ${error.message || String(error)}`);
        responseBodyEl.textContent = String(error);
      }
    }

    operationEl.addEventListener("change", loadSample);
    document.getElementById("loadContract").addEventListener("click", loadContract);
    document.getElementById("sendRequest").addEventListener("click", sendRequest);
    document.getElementById("createJob").addEventListener("click", createJob);
    document.getElementById("captureMetadata").addEventListener("click", () => postSample("/certificate-metadata"));
    document.getElementById("selectReferenceEquipment").addEventListener("click", () => postSample("/reference-equipment-selections"));
    document.getElementById("approveConstantSet").addEventListener("click", () => postSample("/constant-sets/approved"));
    document.getElementById("approveUncertaintyBudget").addEventListener("click", () => postSample("/uncertainty-budgets/approved"));
    document.getElementById("uploadSourceFile").addEventListener("click", uploadSourceFile);
    document.getElementById("reviewImports").addEventListener("click", reviewImports);
    document.getElementById("prepareTemperatureData").addEventListener("click", prepareTemperatureData);
    document.getElementById("recordIrtdRows").addEventListener("click", recordIrtdRows);
    document.getElementById("selectTemperatureWindow").addEventListener("click", selectTemperatureWindow);
    document.getElementById("completeTemperatureWindows").addEventListener("click", completeTemperatureWindows);
    document.getElementById("calculateTemperature").addEventListener("click", calculateTemperature);
    document.getElementById("createUncertaintyBudget").addEventListener("click", createUncertaintyBudget);
    document.getElementById("calculatePressure").addEventListener("click", calculatePressure);
    document.getElementById("submitTechnicalReview").addEventListener("click", () => postJobWorkflowAction("technical-review-submissions"));
    document.getElementById("approveTechnicalReview").addEventListener("click", () => postJobWorkflowAction("technical-review-approvals"));
    document.getElementById("approveQaRelease").addEventListener("click", () => postJobWorkflowAction("qa-release-approvals"));
    document.getElementById("buildCertificatePreview").addEventListener("click", () => postSample("/certificate-previews"));
    document.getElementById("renderCertificateRelease").addEventListener("click", () => postSample("/certificate-rendered-releases"));
    document.getElementById("runManualPressurePreview").addEventListener("click", runManualPressurePreview);
    document.getElementById("runFirstCertificate").addEventListener("click", runFirstCertificate);
    document.getElementById("previousWizardStep").addEventListener("click", () => moveWizardStep(-1));
    document.getElementById("nextWizardStep").addEventListener("click", () => moveWizardStep(1));
    document.getElementById("openReviewStep").addEventListener("click", () => showWizardStep("review"));
    wizardSteps.forEach(step => {
      step.addEventListener("click", () => showWizardStep(step.dataset.stepTarget));
    });
    document.getElementById("manualPressureJobId").addEventListener("input", syncJobIds);
    for (const id of [
      "manualPressureCertificateNumber",
      "manualPressureReference",
      "manualPressureUnit"
    ]) {
      document.getElementById(id).addEventListener("input", updatePressureSummary);
    }
    bootstrapLocalSession();
    setManualPressureDefaults();
    syncJobIds();
    updatePressureSummary();
    showWizardStep("job");
    loadContract();
  </script>
</body>
</html>
"""


def _workflow_steps() -> tuple[WorkflowStep, ...]:
    return (
        WorkflowStep(
            step_id="session",
            label="Session",
            status="Authenticated user and role context",
            actions=(
                WorkflowAction(
                    label="Current user",
                    method="GET",
                    path="/me",
                    required_roles=("operator", "technical_reviewer", "qa_approver", "admin", "read_only"),
                ),
            ),
            evidence=("authenticated_user", "active_session", "role_set"),
        ),
        WorkflowStep(
            step_id="user_admin",
            label="User Administration",
            status="Admin-only user access review and account maintenance",
            actions=(
                WorkflowAction(
                    label="List active users",
                    method="GET",
                    path="/users",
                    required_roles=("admin",),
                ),
                WorkflowAction(
                    label="Create user",
                    method="POST",
                    path="/users",
                    required_roles=("admin",),
                ),
                WorkflowAction(
                    label="Change user roles",
                    method="POST",
                    path="/users/user-001/roles",
                    required_roles=("admin",),
                ),
                WorkflowAction(
                    label="Deactivate user",
                    method="POST",
                    path="/users/user-001/deactivation",
                    required_roles=("admin",),
                ),
                WorkflowAction(
                    label="Revoke user session",
                    method="POST",
                    path="/user-sessions/session-001/revocation",
                    required_roles=("admin",),
                ),
                WorkflowAction(
                    label="Create certificate number sequence",
                    method="POST",
                    path="/certificate-number-sequences",
                    required_roles=("admin",),
                ),
                WorkflowAction(
                    label="Allocate certificate number",
                    method="POST",
                    path="/certificate-number-allocations",
                    required_roles=("admin",),
                ),
                WorkflowAction(
                    label="Retire certificate number sequence",
                    method="POST",
                    path="/certificate-number-sequences/SIMVAL-CAL/retirement",
                    required_roles=("admin",),
                ),
            ),
            evidence=(
                "reviewed_by",
                "reviewed_at",
                "user_account_audit_event_id",
                "user_session_audit_event_id",
                "certificate_number_sequence_audit_event_id",
                "certificate_number_audit_event_id",
                "reason",
            ),
        ),
        WorkflowStep(
            step_id="job",
            label="Job",
            status="Create draft calibration job",
            actions=(
                WorkflowAction(
                    label="Create job",
                    method="POST",
                    path="/calibration-jobs",
                    required_roles=("operator", "technical_reviewer", "admin"),
                ),
                WorkflowAction(
                    label="Approve constant set",
                    method="POST",
                    path="/constant-sets/approved",
                    required_roles=("qa_approver", "admin"),
                ),
                WorkflowAction(
                    label="Approve uncertainty budget",
                    method="POST",
                    path="/uncertainty-budgets/approved",
                    required_roles=("qa_approver", "admin"),
                ),
            ),
            evidence=(
                "job_audit_event_id",
                "constant_set_audit_event_id",
                "budget_audit_event_id",
                "created_by",
                "created_at",
            ),
        ),
        WorkflowStep(
            step_id="import_data",
            label="Import Data",
            status="Upload controlled calibration and verification source files",
            actions=(
                WorkflowAction(
                    label="Upload source file",
                    method="POST",
                    path="/calibration-jobs/job-001/files",
                    required_roles=("operator", "technical_reviewer", "admin"),
                ),
                WorkflowAction(
                    label="Review imports",
                    method="GET",
                    path="/calibration-jobs/job-001/imports",
                    required_roles=("operator", "technical_reviewer", "admin"),
                ),
                WorkflowAction(
                    label="Prepare temperature data",
                    method="POST",
                    path="/calibration-jobs/job-001/temperature-data-entry",
                    required_roles=("operator", "technical_reviewer", "admin"),
                ),
                WorkflowAction(
                    label="Record manual IRTD rows",
                    method="POST",
                    path="/calibration-jobs/job-001/verification-irtd-rows",
                    required_roles=("operator", "technical_reviewer", "admin"),
                ),
                WorkflowAction(
                    label="Record manual pressure entry",
                    method="POST",
                    path="/calibration-jobs/pressure-job-001/pressure-manual-entry",
                    required_roles=("operator", "technical_reviewer", "admin"),
                ),
                WorkflowAction(
                    label="Record automatic pressure entry",
                    method="POST",
                    path="/calibration-jobs/pressure-job-001/pressure-automatic-entry",
                    required_roles=("operator", "technical_reviewer", "admin"),
                ),
                WorkflowAction(
                    label="Select temperature window",
                    method="POST",
                    path="/calibration-jobs/job-001/temperature-windows",
                    required_roles=("operator", "technical_reviewer", "admin"),
                ),
                WorkflowAction(
                    label="Complete temperature windows",
                    method="POST",
                    path="/calibration-jobs/job-001/temperature-windows/complete",
                    required_roles=("operator", "technical_reviewer", "admin"),
                ),
                WorkflowAction(
                    label="Run temperature calculation",
                    method="POST",
                    path="/calibration-jobs/job-001/temperature-calculations",
                    required_roles=("operator", "technical_reviewer", "admin"),
                ),
                WorkflowAction(
                    label="Run manual pressure calculation",
                    method="POST",
                    path="/pressure/manual-calculations",
                    required_roles=("operator", "technical_reviewer", "admin"),
                ),
                WorkflowAction(
                    label="Run automatic pressure calculation",
                    method="POST",
                    path="/pressure/automatic-calculations",
                    required_roles=("operator", "technical_reviewer", "admin"),
                ),
                WorkflowAction(
                    label="Run pressure job calculation",
                    method="POST",
                    path="/calibration-jobs/pressure-job-001/pressure-calculations",
                    required_roles=("operator", "technical_reviewer", "admin"),
                ),
                WorkflowAction(
                    label="Submit technical review",
                    method="POST",
                    path="/calibration-jobs/job-001/technical-review-submissions",
                    required_roles=("operator", "technical_reviewer", "admin"),
                ),
                WorkflowAction(
                    label="Approve technical review",
                    method="POST",
                    path="/calibration-jobs/job-001/technical-review-approvals",
                    required_roles=("technical_reviewer", "admin"),
                ),
                WorkflowAction(
                    label="Approve QA release",
                    method="POST",
                    path="/calibration-jobs/job-001/qa-release-approvals",
                    required_roles=("qa_approver", "admin"),
                ),
            ),
            evidence=(
                "upload_audit_event_id",
                "checksum_sha256",
                "parser_status",
                "reading_count",
                "data_entry_audit_event_id",
                "manual_irtd_audit_event_id",
                "alignment_audit_event_id",
                "selection_audit_event_id",
                "workflow_audit_event_id",
                "calculation_audit_event_id",
                "summary_ids",
            ),
            deferred=(
                "Verification PDF text extraction remains deferred; raw PDF evidence is stored.",
            ),
        ),
        WorkflowStep(
            step_id="metadata",
            label="Metadata",
            status="Capture certificate metadata before equipment selection",
            actions=(
                WorkflowAction(
                    label="Capture metadata",
                    method="POST",
                    path="/certificate-metadata",
                    required_roles=("operator", "admin"),
                ),
            ),
            evidence=("metadata_audit_event_id", "workflow_audit_event_id"),
        ),
        WorkflowStep(
            step_id="reference_equipment",
            label="Reference Equipment",
            status="Select immutable reference equipment evidence",
            actions=(
                WorkflowAction(
                    label="Select equipment",
                    method="POST",
                    path="/reference-equipment-selections",
                    required_roles=("operator", "admin"),
                ),
            ),
            evidence=("selection_audit_event_id", "workflow_audit_event_id"),
            deferred=("Full equipment-library CRUD is manual until production setup.",),
        ),
        WorkflowStep(
            step_id="preview",
            label="Preview",
            status="Generate locked preview from calculated summaries",
            actions=(
                WorkflowAction(
                    label="Build preview",
                    method="POST",
                    path="/certificate-previews",
                    required_roles=("operator", "technical_reviewer", "qa_approver", "admin"),
                ),
                WorkflowAction(
                    label="Render preview PDF",
                    method="POST",
                    path="/certificate-preview-pdfs",
                    required_roles=("operator", "technical_reviewer", "qa_approver", "admin"),
                ),
            ),
            evidence=("preview_audit_event_id", "summary_ids", "version_refs", "preview_pdf_checksum"),
        ),
        WorkflowStep(
            step_id="release",
            label="Release",
            status="Render, store, and release PDF after approval",
            actions=(
                WorkflowAction(
                    label="Render and release",
                    method="POST",
                    path="/certificate-rendered-releases",
                    required_roles=("qa_approver", "admin"),
                ),
                WorkflowAction(
                    label="Allocate number and release",
                    method="POST",
                    path="/certificate-rendered-releases/allocated",
                    required_roles=("qa_approver", "admin"),
                ),
            ),
            evidence=(
                "artifact_checksum",
                "certificate_number_audit_event_id",
                "release_audit_event_id",
                "workflow_audit_event_id",
            ),
        ),
        WorkflowStep(
            step_id="history_revision",
            label="History And Revision",
            status="Retrieve released evidence or register correction reason",
            actions=(
                WorkflowAction(
                    label="Certificate history",
                    method="GET",
                    path="/certificate-history/job-001",
                    required_roles=("operator", "technical_reviewer", "qa_approver", "admin", "read_only"),
                ),
                WorkflowAction(
                    label="Download released artifact",
                    method="GET",
                    path="/certificate-artifacts/artifact-001",
                    required_roles=("operator", "technical_reviewer", "qa_approver", "admin", "read_only"),
                ),
                WorkflowAction(
                    label="Register revision",
                    method="POST",
                    path="/certificate-revisions",
                    required_roles=("qa_approver", "admin"),
                ),
            ),
            evidence=("artifact_history", "revision_audit_event_id"),
        ),
    )
