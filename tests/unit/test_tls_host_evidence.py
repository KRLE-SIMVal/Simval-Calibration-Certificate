import json
from datetime import datetime, timezone

import pytest

from app.backend.validation.tls_host import (
    TlsHostEvidenceError,
    build_tls_host_evidence,
)
from scripts.validation.generate_tls_host_evidence import main


def test_tls_host_evidence_passes_for_reviewed_host_boundary_record(tmp_path):
    host_evidence = _host_evidence(tmp_path)

    evidence = build_tls_host_evidence(
        host_evidence_path=host_evidence,
        reviewer_approved=True,
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    payload = json.loads(evidence.to_json())

    assert payload["status"] == "passed"
    assert payload["blockers"] == []
    assert payload["https_endpoint_verified"] is True
    assert payload["approved_hostname_verified"] is True
    assert payload["tls_certificate_valid"] is True
    assert payload["direct_api_exposure_reviewed"] is True
    assert payload["direct_unauthenticated_api_exposure_blocked"] is True
    assert payload["reviewer_approved"] is True
    assert payload["evidence_files"][0]["path"] == "tls-host-source.json"
    assert "simval.example.test" not in evidence.to_json()


def test_tls_host_evidence_blocks_unverified_endpoint_and_hostname(tmp_path):
    host_evidence = _host_evidence(
        tmp_path,
        https_endpoint_verified=False,
        approved_hostname_verified=False,
    )

    evidence = build_tls_host_evidence(
        host_evidence_path=host_evidence,
        reviewer_approved=True,
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    payload = json.loads(evidence.to_json())

    assert payload["status"] == "blocked"
    assert "tls_host_https_endpoint_not_verified" in payload["blockers"]
    assert "tls_host_approved_hostname_not_verified" in payload["blockers"]


def test_tls_host_evidence_blocks_invalid_certificate_and_api_exposure(tmp_path):
    host_evidence = _host_evidence(
        tmp_path,
        tls_certificate_valid=False,
        direct_api_exposure_reviewed=False,
        direct_unauthenticated_api_exposure_blocked=False,
    )

    evidence = build_tls_host_evidence(
        host_evidence_path=host_evidence,
        reviewer_approved=True,
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    payload = json.loads(evidence.to_json())

    assert payload["status"] == "blocked"
    assert "tls_host_certificate_not_valid" in payload["blockers"]
    assert "tls_host_direct_api_exposure_not_reviewed" in payload["blockers"]
    assert "tls_host_direct_unauthenticated_api_not_blocked" in payload["blockers"]


def test_tls_host_evidence_blocks_missing_reviewer_approval(tmp_path):
    host_evidence = _host_evidence(tmp_path)

    evidence = build_tls_host_evidence(
        host_evidence_path=host_evidence,
        reviewer_approved=False,
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    payload = json.loads(evidence.to_json())

    assert payload["status"] == "blocked"
    assert payload["blockers"] == ["tls_host_reviewer_approval_missing"]


def test_tls_host_evidence_rejects_invalid_json(tmp_path):
    host_evidence = tmp_path / "tls-host-source.json"
    host_evidence.write_text("not-json", encoding="utf-8")

    with pytest.raises(TlsHostEvidenceError, match="not valid JSON"):
        build_tls_host_evidence(
            host_evidence_path=host_evidence,
            reviewer_approved=True,
            generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
        )


def test_tls_host_evidence_rejects_naive_timestamp(tmp_path):
    host_evidence = _host_evidence(tmp_path)

    with pytest.raises(TlsHostEvidenceError, match="timezone-aware"):
        build_tls_host_evidence(
            host_evidence_path=host_evidence,
            reviewer_approved=True,
            generated_at=datetime(2026, 6, 15, 12, 0),
        )


def test_generate_tls_host_evidence_cli_writes_passed_output(tmp_path):
    host_evidence = _host_evidence(tmp_path)
    output = tmp_path / "tls-host-evidence.json"

    result = main(
        [
            "--host-evidence",
            str(host_evidence),
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


def test_generate_tls_host_evidence_cli_returns_two_when_blocked(tmp_path):
    host_evidence = _host_evidence(tmp_path, tls_certificate_valid=False)
    output = tmp_path / "tls-host-evidence.json"

    result = main(
        [
            "--host-evidence",
            str(host_evidence),
            "--generated-at",
            "2026-06-15T12:00:00Z",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))

    assert result == 2
    assert payload["status"] == "blocked"
    assert "tls_host_certificate_not_valid" in payload["blockers"]
    assert "tls_host_reviewer_approval_missing" in payload["blockers"]


def _host_evidence(
    tmp_path,
    *,
    https_endpoint_verified: bool = True,
    approved_hostname_verified: bool = True,
    tls_certificate_valid: bool = True,
    direct_api_exposure_reviewed: bool = True,
    direct_unauthenticated_api_exposure_blocked: bool = True,
):
    payload = {
        "approved_hostname": "simval.example.test",
        "https_endpoint_verified": https_endpoint_verified,
        "approved_hostname_verified": approved_hostname_verified,
        "tls_certificate_valid": tls_certificate_valid,
        "direct_api_exposure_reviewed": direct_api_exposure_reviewed,
        "direct_unauthenticated_api_exposure_blocked": (
            direct_unauthenticated_api_exposure_blocked
        ),
    }
    path = tmp_path / "tls-host-source.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path
