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
    main { padding: 22px 28px 32px; }
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
      .toolbar, .split, .task-grid, .field-grid { grid-template-columns: 1fr; }
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
  <main>
    <div class="toolbar">
      <label>Session ID
        <input id="sessionId" autocomplete="off" placeholder="X-Session-Id">
      </label>
      <label>Operation
        <select id="operation"></select>
      </label>
      <div>
        <button id="sendRequest">Send</button>
      </div>
    </div>
    <div class="workflow" id="workflow"></div>
    <div class="task-grid">
      <section class="panel">
        <h2>Create Job</h2>
        <div class="field-grid">
          <label>Job ID
            <input id="jobId" autocomplete="off" value="job-001">
          </label>
          <label>Client
            <input id="clientName" autocomplete="off" value="SIMVal customer">
          </label>
          <label class="wide">Client address
            <input id="clientAddress" autocomplete="off" value="Validated Road 1">
          </label>
          <label>Discipline
            <select id="jobDiscipline">
              <option value="temperature">Temperature</option>
              <option value="pressure">Pressure</option>
            </select>
          </label>
          <label>Mode
            <select id="measurementMode">
              <option value="automatic">Automatic</option>
              <option value="manual">Manual</option>
            </select>
          </label>
          <label class="wide">Method
            <input id="jobMethod" autocomplete="off" value="ValProbe RT linked XLSX/PDF workflow">
          </label>
        </div>
        <div class="panel-actions">
          <button id="createJob">Create Job</button>
          <button class="secondary" id="captureMetadata">Capture Metadata</button>
          <button class="secondary" id="selectReferenceEquipment">Select Equipment</button>
          <button class="secondary" id="approveConstantSet">Approve Constants</button>
          <button class="secondary" id="approveUncertaintyBudget">Approve Budget</button>
        </div>
      </section>
      <section class="panel">
        <h2>Upload Source File</h2>
        <div class="field-grid">
          <label>File kind
            <select id="uploadFileKind">
              <option value="calibration_xlsx">Calibration XLSX</option>
              <option value="verification_pdf">Verification PDF</option>
              <option value="certificate_reference_pdf">Certificate reference PDF</option>
              <option value="other">Other</option>
            </select>
          </label>
          <label>Software version
            <input id="uploadSoftwareVersion" autocomplete="off" value="app-0.1.0">
          </label>
          <label class="wide">Source file
            <input id="sourceFile" type="file">
          </label>
          <label>Calibration file ID
            <input id="calibrationUploadedFileId" autocomplete="off">
          </label>
          <label>Verification file ID
            <input id="verificationUploadedFileId" autocomplete="off">
          </label>
          <label>Setpoints
            <input id="temperatureSetpoints" autocomplete="off" value="-80">
          </label>
          <label class="wide">IRTD rows
            <textarea id="irtdRows" rows="4">Time,IRTD (deg C),MJT1-A
2026-04-08T15:45:00+00:00,-80.031,-80.036
2026-04-08T15:46:00+00:00,-80.030,-80.034</textarea>
          </label>
          <label>Window ID
            <input id="windowId" autocomplete="off" value="window-001">
          </label>
          <label>DUT ID
            <input id="windowDutId" autocomplete="off" value="dut-MJT1-A">
          </label>
          <label>Channel
            <input id="windowChannelId" autocomplete="off" value="MJT1-A">
          </label>
          <label>Window start
            <input id="windowStart" autocomplete="off" value="2026-04-08T15:45:00+00:00">
          </label>
          <label>Window end
            <input id="windowEnd" autocomplete="off" value="2026-04-08T15:46:00+00:00">
          </label>
          <label>CMC floor
            <input id="cmcFloor" autocomplete="off" value="0.010">
          </label>
          <label>Reference U
            <input id="referenceExpandedUncertainty" autocomplete="off" value="0.010">
          </label>
          <label>Bath U
            <input id="bathExpandedUncertainty" autocomplete="off" value="0.004">
          </label>
          <label>DUT resolution
            <input id="dutResolution" autocomplete="off" value="0.010">
          </label>
          <label>Calculation engine
            <input id="calculationEngineVersion" autocomplete="off" value="calc-engine-0.1.0">
          </label>
          <label>Constants version
            <input id="constantSetVersion" autocomplete="off" value="constants-2026-001">
          </label>
          <label>Budget version
            <input id="budgetVersion" autocomplete="off" value="budget-temp-001">
          </label>
        </div>
        <div class="panel-actions">
          <button id="uploadSourceFile">Upload File</button>
          <button class="secondary" id="reviewImports">Review Imports</button>
          <button class="secondary" id="prepareTemperatureData">Prepare Data</button>
          <button class="secondary" id="recordIrtdRows">Record IRTD</button>
          <button class="secondary" id="selectTemperatureWindow">Select Window</button>
          <button class="secondary" id="completeTemperatureWindows">Complete Windows</button>
          <button class="secondary" id="calculateTemperature">Calculate</button>
          <button class="secondary" id="submitTechnicalReview">Submit Review</button>
          <button class="secondary" id="approveTechnicalReview">Approve Technical</button>
          <button class="secondary" id="approveQaRelease">Approve QA</button>
          <button class="secondary" id="buildCertificatePreview">Build Preview</button>
          <button class="secondary" id="renderCertificateRelease">Render Release</button>
        </div>
      </section>
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
      "/certificate-rendered-releases": {
        job_id: "job-001",
        certificate_id: "cert-001",
        certificate_number: "SIMVAL-CAL-0001",
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
      "/certificate-history/job-001": ""
    };

    let operations = [];
    const workflowEl = document.getElementById("workflow");
    const operationEl = document.getElementById("operation");
    const requestBodyEl = document.getElementById("requestBody");
    const responseBodyEl = document.getElementById("responseBody");

    function pretty(value) {
      return typeof value === "string" ? value : JSON.stringify(value, null, 2);
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

    async function createJob() {
      const payload = {
        job_id: document.getElementById("jobId").value.trim(),
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
        responseBodyEl.textContent = `${response.status} ${response.statusText}\n\n${pretty(parsed)}`;
      } catch (error) {
        responseBodyEl.textContent = String(error);
      }
    }

    async function uploadSourceFile() {
      const fileInput = document.getElementById("sourceFile");
      const file = fileInput.files[0];
      if (!file) {
        responseBodyEl.textContent = "Select a source file first.";
        return;
      }
      const jobId = document.getElementById("jobId").value.trim();
      const params = new URLSearchParams({
        original_filename: file.name,
        file_kind: document.getElementById("uploadFileKind").value,
        software_version: document.getElementById("uploadSoftwareVersion").value.trim()
      });
      responseBodyEl.textContent = "Uploading...";
      try {
        const response = await fetch(`/calibration-jobs/${encodeURIComponent(jobId)}/files?${params}`, {
          method: "POST",
          headers: { ...sessionHeaders(), "Content-Type": "application/octet-stream" },
          body: await file.arrayBuffer()
        });
        const parsed = await response.json();
        if (response.ok && parsed.uploaded_file_id && parsed.file_kind === "calibration_xlsx") {
          document.getElementById("calibrationUploadedFileId").value = parsed.uploaded_file_id;
        }
        if (response.ok && parsed.uploaded_file_id && parsed.file_kind === "verification_pdf") {
          document.getElementById("verificationUploadedFileId").value = parsed.uploaded_file_id;
        }
        responseBodyEl.textContent = `${response.status} ${response.statusText}\n\n${pretty(parsed)}`;
      } catch (error) {
        responseBodyEl.textContent = String(error);
      }
    }

    async function reviewImports() {
      const jobId = document.getElementById("jobId").value.trim();
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
      const jobId = document.getElementById("jobId").value.trim();
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
      return rawText.split(/\r?\n/)
        .map(line => line.trim())
        .filter(line => line.length > 0)
        .map(line => {
          const delimiter = line.includes("\t") ? "\t" : ",";
          return line.split(delimiter).map(cell => cell.trim());
        });
    }

    async function recordIrtdRows() {
      const jobId = document.getElementById("jobId").value.trim();
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
      const jobId = document.getElementById("jobId").value.trim();
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
      const jobId = document.getElementById("jobId").value.trim();
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
      const jobId = document.getElementById("jobId").value.trim();
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
      const jobId = document.getElementById("jobId").value.trim();
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
        payload.job_id = document.getElementById("jobId").value.trim();
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
    document.getElementById("submitTechnicalReview").addEventListener("click", () => postJobWorkflowAction("technical-review-submissions"));
    document.getElementById("approveTechnicalReview").addEventListener("click", () => postJobWorkflowAction("technical-review-approvals"));
    document.getElementById("approveQaRelease").addEventListener("click", () => postJobWorkflowAction("qa-release-approvals"));
    document.getElementById("buildCertificatePreview").addEventListener("click", () => postSample("/certificate-previews"));
    document.getElementById("renderCertificateRelease").addEventListener("click", () => postSample("/certificate-rendered-releases"));
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
            ),
            evidence=("preview_audit_event_id", "summary_ids", "version_refs"),
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
            ),
            evidence=("artifact_checksum", "release_audit_event_id", "workflow_audit_event_id"),
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
                    label="Register revision",
                    method="POST",
                    path="/certificate-revisions",
                    required_roles=("qa_approver", "admin"),
                ),
            ),
            evidence=("artifact_history", "revision_audit_event_id"),
        ),
    )
