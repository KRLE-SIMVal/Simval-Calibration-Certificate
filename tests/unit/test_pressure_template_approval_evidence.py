import json
from datetime import datetime, timezone

import pytest

from app.backend.validation.pressure_template_approval import (
    PressureTemplateApprovalEvidenceError,
    build_pressure_template_approval_evidence,
)
from scripts.validation.generate_pressure_template_approval_evidence import main


def test_pressure_template_approval_evidence_passes_for_complete_approval(tmp_path):
    approval_path = tmp_path / "pressure-template-approval.json"
    approval_path.write_text(
        json.dumps(_approval_payload()),
        encoding="utf-8",
    )

    evidence = build_pressure_template_approval_evidence(
        approval_path=approval_path,
        template_version="template-pressure-2026-001",
        generated_at=datetime(2026, 6, 16, 10, 0, tzinfo=timezone.utc),
    )
    payload = json.loads(evidence.to_json())

    assert payload["status"] == "passed"
    assert payload["blockers"] == []
    assert payload["template_version"] == "template-pressure-2026-001"
    assert payload["approval_template_version"] == "template-pressure-2026-001"
    assert payload["discipline"] == "pressure"
    assert payload["certificate_artifact_sha256_present"] is True
    assert payload["certificate_artifact_reviewed"] is True
    assert payload["method_specific_statements_reviewed"] is True
    assert payload["danak_mark_scope_reviewed"] is True
    assert payload["ab11_reporting_reviewed"] is True
    assert [record["role"] for record in payload["reviewer_roles"]] == [
        "qa_laboratory_reviewer",
        "laboratory_chief",
    ]
    assert all(record["actor_digest"] for record in payload["reviewer_roles"])
    assert payload["evidence_files"][0]["key"] == "pressure_template_approval"
    assert payload["evidence_files"][0]["size_bytes"] > 0


def test_pressure_template_approval_evidence_blocks_incomplete_review(tmp_path):
    approval_path = tmp_path / "pressure-template-approval.json"
    approval_path.write_text(
        json.dumps(
            _approval_payload(
                certificate_artifact_reviewed=False,
                method_specific_statements_reviewed=False,
                danak_mark_scope_reviewed=False,
                ab11_reporting_reviewed=False,
                approvals={},
            )
        ),
        encoding="utf-8",
    )

    evidence = build_pressure_template_approval_evidence(
        approval_path=approval_path,
        template_version="template-pressure-2026-001",
        generated_at=datetime(2026, 6, 16, 10, 0, tzinfo=timezone.utc),
    )
    payload = json.loads(evidence.to_json())

    assert payload["status"] == "blocked"
    assert payload["blockers"] == [
        "pressure_template_artifact_not_reviewed",
        "pressure_template_method_statements_not_reviewed",
        "pressure_template_danak_scope_not_reviewed",
        "pressure_template_ab11_reporting_not_reviewed",
        "pressure_template_required_role_missing",
        "pressure_template_required_role_not_approved",
    ]


def test_pressure_template_approval_evidence_blocks_version_and_scope_mismatch(tmp_path):
    approval_path = tmp_path / "pressure-template-approval.json"
    approval_path.write_text(
        json.dumps(
            _approval_payload(
                template_version="template-temperature-2026-001",
                discipline="temperature",
                certificate_artifact_sha256="not-a-sha",
            )
        ),
        encoding="utf-8",
    )

    evidence = build_pressure_template_approval_evidence(
        approval_path=approval_path,
        template_version="template-pressure-2026-001",
        generated_at=datetime(2026, 6, 16, 10, 0, tzinfo=timezone.utc),
    )
    payload = json.loads(evidence.to_json())

    assert payload["status"] == "blocked"
    assert "pressure_template_version_mismatch" in payload["blockers"]
    assert "pressure_template_discipline_not_pressure" in payload["blockers"]
    assert "pressure_template_artifact_reference_missing" in payload["blockers"]


def test_pressure_template_approval_evidence_rejects_invalid_json(tmp_path):
    approval_path = tmp_path / "pressure-template-approval.json"
    approval_path.write_text("not json", encoding="utf-8")

    with pytest.raises(PressureTemplateApprovalEvidenceError):
        build_pressure_template_approval_evidence(
            approval_path=approval_path,
            template_version="template-pressure-2026-001",
        )


def test_pressure_template_approval_evidence_rejects_naive_timestamp(tmp_path):
    approval_path = tmp_path / "pressure-template-approval.json"
    approval_path.write_text(json.dumps(_approval_payload()), encoding="utf-8")

    with pytest.raises(PressureTemplateApprovalEvidenceError):
        build_pressure_template_approval_evidence(
            approval_path=approval_path,
            template_version="template-pressure-2026-001",
            generated_at=datetime(2026, 6, 16, 10, 0),
        )


def test_generate_pressure_template_approval_evidence_cli_writes_passed_output(tmp_path):
    approval_path = tmp_path / "pressure-template-approval.json"
    output_path = tmp_path / "pressure-template-approval-evidence.json"
    approval_path.write_text(json.dumps(_approval_payload()), encoding="utf-8")

    exit_code = main(
        [
            "--approval-file",
            str(approval_path),
            "--template-version",
            "template-pressure-2026-001",
            "--generated-at",
            "2026-06-16T10:00:00+00:00",
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert payload["blockers"] == []


def test_generate_pressure_template_approval_evidence_cli_returns_two_when_blocked(
    tmp_path,
):
    approval_path = tmp_path / "pressure-template-approval.json"
    output_path = tmp_path / "pressure-template-approval-evidence.json"
    approval_path.write_text(
        json.dumps(_approval_payload(approvals={})),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--approval-file",
            str(approval_path),
            "--template-version",
            "template-pressure-2026-001",
            "--generated-at",
            "2026-06-16T10:00:00+00:00",
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 2
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["status"] == "blocked"
    assert "pressure_template_required_role_missing" in payload["blockers"]


def _approval_payload(
    *,
    template_version: str = "template-pressure-2026-001",
    discipline: str = "pressure",
    certificate_artifact_sha256: str = "a" * 64,
    certificate_artifact_reviewed: bool = True,
    method_specific_statements_reviewed: bool = True,
    danak_mark_scope_reviewed: bool = True,
    ab11_reporting_reviewed: bool = True,
    approvals: dict | None = None,
) -> dict:
    if approvals is None:
        approvals = {
            "qa_laboratory_reviewer": {
                "decision": "approve",
                "approved_at": "2026-06-16T09:00:00+00:00",
                "actor_identifier": "qa@example.com",
            },
            "laboratory_chief": {
                "decision": "approve",
                "approved_at": "2026-06-16T09:15:00+00:00",
                "actor_identifier": "chief@example.com",
            },
        }
    return {
        "template_version": template_version,
        "discipline": discipline,
        "certificate_artifact_sha256": certificate_artifact_sha256,
        "certificate_artifact_reviewed": certificate_artifact_reviewed,
        "method_specific_statements_reviewed": method_specific_statements_reviewed,
        "danak_mark_scope_reviewed": danak_mark_scope_reviewed,
        "ab11_reporting_reviewed": ab11_reporting_reviewed,
        "approvals": approvals,
    }
