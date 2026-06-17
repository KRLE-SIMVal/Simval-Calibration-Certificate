import json
from datetime import datetime, timezone

import pytest

from app.backend.validation.human_approval import (
    REQUIRED_APPROVAL_ROLES,
    HumanApprovalEvidenceError,
    build_human_approval_evidence,
)
from scripts.validation.generate_human_approval_evidence import main


def test_human_approval_evidence_passes_for_complete_go_no_go_record(tmp_path):
    approval = _approval_file(tmp_path)

    evidence = build_human_approval_evidence(
        approval_path=approval,
        software_version="0.1.0",
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    payload = json.loads(evidence.to_json())

    assert payload["status"] == "passed"
    assert payload["blockers"] == []
    assert payload["software_version"] == "0.1.0"
    assert payload["evidence_pack_reviewed"] is True
    assert payload["readiness_report_sha256_present"] is True
    assert payload["remaining_deviation_count"] == 0
    assert [record["role"] for record in payload["reviewer_roles"]] == list(
        REQUIRED_APPROVAL_ROLES
    )
    assert payload["reviewer_roles"][0]["actor_digest"]
    assert "owner@example.com" not in evidence.to_json()
    assert payload["evidence_files"][0]["path"] == "go-no-go-approval.json"


def test_human_approval_evidence_blocks_version_mismatch(tmp_path):
    approval = _approval_file(tmp_path, software_version="different")

    evidence = build_human_approval_evidence(
        approval_path=approval,
        software_version="0.1.0",
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    payload = json.loads(evidence.to_json())

    assert payload["status"] == "blocked"
    assert "human_approval_software_version_mismatch" in payload["blockers"]


def test_human_approval_evidence_blocks_missing_required_role(tmp_path):
    approval = _approval_file(tmp_path, remove_role="qa_laboratory_reviewer")

    evidence = build_human_approval_evidence(
        approval_path=approval,
        software_version="0.1.0",
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    payload = json.loads(evidence.to_json())

    assert payload["status"] == "blocked"
    assert "human_approval_required_role_missing" in payload["blockers"]
    assert "human_approval_required_role_not_approved" in payload["blockers"]


def test_human_approval_evidence_blocks_unreviewed_pack_and_missing_report_hash(
    tmp_path,
):
    approval = _approval_file(
        tmp_path,
        evidence_pack_reviewed=False,
        readiness_report_sha256="not-a-hash",
    )

    evidence = build_human_approval_evidence(
        approval_path=approval,
        software_version="0.1.0",
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    payload = json.loads(evidence.to_json())

    assert payload["status"] == "blocked"
    assert "human_approval_evidence_pack_not_reviewed" in payload["blockers"]
    assert "human_approval_readiness_report_reference_missing" in payload["blockers"]


def test_human_approval_evidence_blocks_unaccepted_remaining_deviation(tmp_path):
    approval = _approval_file(
        tmp_path,
        remaining_deviations=[{"id": "DEV-1", "disposition": "open"}],
    )

    evidence = build_human_approval_evidence(
        approval_path=approval,
        software_version="0.1.0",
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    payload = json.loads(evidence.to_json())

    assert payload["status"] == "blocked"
    assert "human_approval_open_deviations_unaccepted" in payload["blockers"]


def test_human_approval_evidence_blocks_malformed_remaining_deviation(tmp_path):
    approval = _approval_file(
        tmp_path,
        remaining_deviations=[{"id": "DEV-1", "disposition": "accepted_for_go_live"}],
    )
    payload = json.loads(approval.read_text(encoding="utf-8"))
    payload["remaining_deviations"].append("not-a-deviation-record")
    approval.write_text(json.dumps(payload), encoding="utf-8")

    evidence = build_human_approval_evidence(
        approval_path=approval,
        software_version="0.1.0",
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    output = json.loads(evidence.to_json())

    assert output["status"] == "blocked"
    assert "human_approval_open_deviations_unaccepted" in output["blockers"]


def test_human_approval_evidence_accepts_controlled_deviation_disposition(tmp_path):
    approval = _approval_file(
        tmp_path,
        remaining_deviations=[
            {"id": "DEV-1", "disposition": "accepted_for_go_live"}
        ],
    )

    evidence = build_human_approval_evidence(
        approval_path=approval,
        software_version="0.1.0",
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    assert json.loads(evidence.to_json())["status"] == "passed"


def test_human_approval_evidence_rejects_invalid_json(tmp_path):
    approval = tmp_path / "go-no-go-approval.json"
    approval.write_text("not-json", encoding="utf-8")

    with pytest.raises(HumanApprovalEvidenceError, match="not valid JSON"):
        build_human_approval_evidence(
            approval_path=approval,
            software_version="0.1.0",
            generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
        )


def test_human_approval_evidence_rejects_naive_timestamp(tmp_path):
    approval = _approval_file(tmp_path)

    with pytest.raises(HumanApprovalEvidenceError, match="timezone-aware"):
        build_human_approval_evidence(
            approval_path=approval,
            software_version="0.1.0",
            generated_at=datetime(2026, 6, 15, 12, 0),
        )


def test_generate_human_approval_evidence_cli_writes_passed_output(tmp_path):
    approval = _approval_file(tmp_path)
    output = tmp_path / "human-approval-evidence.json"

    result = main(
        [
            "--approval-file",
            str(approval),
            "--software-version",
            "0.1.0",
            "--generated-at",
            "2026-06-15T12:00:00Z",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))

    assert result == 0
    assert payload["status"] == "passed"


def test_generate_human_approval_evidence_cli_returns_two_when_blocked(tmp_path):
    approval = _approval_file(tmp_path, remove_role="system_owner")
    output = tmp_path / "human-approval-evidence.json"

    result = main(
        [
            "--approval-file",
            str(approval),
            "--software-version",
            "0.1.0",
            "--generated-at",
            "2026-06-15T12:00:00Z",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))

    assert result == 2
    assert payload["status"] == "blocked"


def _approval_file(
    tmp_path,
    *,
    software_version: str = "0.1.0",
    evidence_pack_reviewed: bool = True,
    readiness_report_sha256: str | None = None,
    remove_role: str | None = None,
    remaining_deviations: list[dict] | None = None,
):
    approvals = {
        "system_owner": {
            "decision": "approve",
            "actor_identifier": "owner@example.com",
            "approved_at": "2026-06-15T12:00:00Z",
        },
        "qa_laboratory_reviewer": {
            "decision": "approve",
            "actor_identifier": "qa@example.com",
            "approved_at": "2026-06-15T12:05:00Z",
        },
    }
    if remove_role is not None:
        approvals.pop(remove_role)
    payload = {
        "software_version": software_version,
        "readiness_report_sha256": readiness_report_sha256 or ("a" * 64),
        "evidence_pack_reviewed": evidence_pack_reviewed,
        "approvals": approvals,
        "remaining_deviations": remaining_deviations or [],
    }
    path = tmp_path / "go-no-go-approval.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path
