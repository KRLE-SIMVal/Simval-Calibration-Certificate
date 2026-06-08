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
    section.panel {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      padding: 14px;
    }
    section.panel h2 { margin: 0 0 12px; font-size: 1rem; }
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
      .toolbar, .split { grid-template-columns: 1fr; }
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

    operationEl.addEventListener("change", loadSample);
    document.getElementById("loadContract").addEventListener("click", loadContract);
    document.getElementById("sendRequest").addEventListener("click", sendRequest);
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
