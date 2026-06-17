import json
from datetime import datetime, timezone

import pytest

from app.backend.validation.live_entra import (
    LiveEntraEvidenceError,
    build_live_entra_evidence,
)
from scripts.validation.generate_live_entra_evidence import main


def test_live_entra_evidence_passes_for_reviewed_auth_boundary_record(tmp_path):
    auth_evidence = _auth_evidence(tmp_path)

    evidence = build_live_entra_evidence(
        auth_evidence_path=auth_evidence,
        reviewer_approved=True,
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    payload = json.loads(evidence.to_json())

    assert payload["status"] == "passed"
    assert payload["blockers"] == []
    assert payload["provider"] == "entra_id_free"
    assert payload["tenant_id_verified"] is True
    assert payload["client_id_verified"] is True
    assert payload["audience_verified"] is True
    assert payload["session_exchange_status"] == "passed"
    assert payload["get_me_status"] == "passed"
    assert payload["user_session_created_audit_event_retained"] is True
    assert payload["local_role_mapping_reviewed"] is True
    assert payload["reviewer_approved"] is True
    assert payload["evidence_files"][0]["path"] == "live-entra-source.json"
    assert "tenant-001" not in evidence.to_json()
    assert "client-001" not in evidence.to_json()


def test_live_entra_evidence_blocks_wrong_provider_and_unverified_tenant(tmp_path):
    auth_evidence = _auth_evidence(
        tmp_path,
        provider="local_session",
        tenant_id_verified=False,
    )

    evidence = build_live_entra_evidence(
        auth_evidence_path=auth_evidence,
        reviewer_approved=True,
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    payload = json.loads(evidence.to_json())

    assert payload["status"] == "blocked"
    assert "live_entra_provider_not_approved" in payload["blockers"]
    assert "live_entra_tenant_not_verified" in payload["blockers"]


def test_live_entra_evidence_blocks_failed_session_checks(tmp_path):
    auth_evidence = _auth_evidence(
        tmp_path,
        session_exchange_status="failed",
        get_me_status="failed",
    )

    evidence = build_live_entra_evidence(
        auth_evidence_path=auth_evidence,
        reviewer_approved=True,
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    payload = json.loads(evidence.to_json())

    assert payload["status"] == "blocked"
    assert "live_entra_session_exchange_not_passed" in payload["blockers"]
    assert "live_entra_get_me_not_passed" in payload["blockers"]


def test_live_entra_evidence_blocks_missing_audit_and_role_review(tmp_path):
    auth_evidence = _auth_evidence(
        tmp_path,
        user_session_created_audit_event_retained=False,
        local_role_mapping_reviewed=False,
    )

    evidence = build_live_entra_evidence(
        auth_evidence_path=auth_evidence,
        reviewer_approved=True,
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    payload = json.loads(evidence.to_json())

    assert payload["status"] == "blocked"
    assert "live_entra_session_audit_event_missing" in payload["blockers"]
    assert "live_entra_role_mapping_review_missing" in payload["blockers"]


def test_live_entra_evidence_blocks_missing_reviewer_approval(tmp_path):
    auth_evidence = _auth_evidence(tmp_path)

    evidence = build_live_entra_evidence(
        auth_evidence_path=auth_evidence,
        reviewer_approved=False,
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    payload = json.loads(evidence.to_json())

    assert payload["status"] == "blocked"
    assert payload["blockers"] == ["live_entra_reviewer_approval_missing"]


def test_live_entra_evidence_rejects_invalid_json(tmp_path):
    auth_evidence = tmp_path / "live-entra-source.json"
    auth_evidence.write_text("not-json", encoding="utf-8")

    with pytest.raises(LiveEntraEvidenceError, match="not valid JSON"):
        build_live_entra_evidence(
            auth_evidence_path=auth_evidence,
            reviewer_approved=True,
            generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
        )


def test_live_entra_evidence_rejects_naive_timestamp(tmp_path):
    auth_evidence = _auth_evidence(tmp_path)

    with pytest.raises(LiveEntraEvidenceError, match="timezone-aware"):
        build_live_entra_evidence(
            auth_evidence_path=auth_evidence,
            reviewer_approved=True,
            generated_at=datetime(2026, 6, 15, 12, 0),
        )


def test_generate_live_entra_evidence_cli_writes_passed_output(tmp_path):
    auth_evidence = _auth_evidence(tmp_path)
    output = tmp_path / "live-entra-evidence.json"

    result = main(
        [
            "--auth-evidence",
            str(auth_evidence),
            "--reviewer-approved",
            "--generated-at",
            "2026-06-15T12:00:00Z",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))

    assert result == 0
    assert payload["status"] == "passed"


def test_generate_live_entra_evidence_cli_returns_two_when_blocked(tmp_path):
    auth_evidence = _auth_evidence(tmp_path, audience_verified=False)
    output = tmp_path / "live-entra-evidence.json"

    result = main(
        [
            "--auth-evidence",
            str(auth_evidence),
            "--generated-at",
            "2026-06-15T12:00:00Z",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))

    assert result == 2
    assert payload["status"] == "blocked"
    assert "live_entra_audience_not_verified" in payload["blockers"]
    assert "live_entra_reviewer_approval_missing" in payload["blockers"]


def _auth_evidence(
    tmp_path,
    *,
    provider: str = "entra_id_free",
    tenant_id_verified: bool = True,
    client_id_verified: bool = True,
    audience_verified: bool = True,
    session_exchange_status: str = "passed",
    get_me_status: str = "passed",
    user_session_created_audit_event_retained: bool = True,
    local_role_mapping_reviewed: bool = True,
):
    payload = {
        "provider": provider,
        "tenant_id": "tenant-001",
        "client_id": "client-001",
        "tenant_id_verified": tenant_id_verified,
        "client_id_verified": client_id_verified,
        "audience_verified": audience_verified,
        "session_exchange_status": session_exchange_status,
        "get_me_status": get_me_status,
        "user_session_created_audit_event_retained": (
            user_session_created_audit_event_retained
        ),
        "local_role_mapping_reviewed": local_role_mapping_reviewed,
    }
    path = tmp_path / "live-entra-source.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path
