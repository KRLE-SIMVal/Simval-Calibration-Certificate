import json
import sqlite3
from datetime import datetime, timezone

from app.backend.api.settings import ApiSettings
from app.backend.operations.production_readiness import (
    ProductionReadinessEvidence,
    build_production_readiness_report,
)
from app.backend.operations.readiness import ReadinessComponent, RuntimeReadiness
from scripts.validation.generate_production_readiness_report import main


def test_production_readiness_report_blocks_missing_go_live_evidence(tmp_path):
    settings = _settings(tmp_path)

    report = build_production_readiness_report(
        settings=settings,
        runtime_readiness=RuntimeReadiness(
            status="ready",
            components=(
                ReadinessComponent("database", "ok", "SQLite ok."),
                ReadinessComponent("artifact_storage", "ok", "Artifacts ok."),
            ),
        ),
        evidence=ProductionReadinessEvidence(),
        generated_at=datetime(2026, 6, 9, 8, 0, tzinfo=timezone.utc),
        software_version="0.1.0",
    )

    assert report.status == "blocked"
    assert "live_entra_verification_missing" in report.blockers
    assert "tls_host_verification_missing" in report.blockers
    assert "valprobe_parser_validation_missing" in report.blockers
    assert "final_human_approval_missing" in report.blockers
    assert report.scope == {
        "enabled_disciplines": ["temperature"],
        "runtime_profile": "production",
        "auth_provider": "entra_id_free",
        "entra_configured": True,
        "entra_local_session_hours": 8,
    }


def test_production_readiness_report_allows_go_live_review_when_evidence_is_complete(
    tmp_path,
):
    report = build_production_readiness_report(
        settings=_settings(tmp_path),
        runtime_readiness=RuntimeReadiness(
            status="ready",
            components=(
                ReadinessComponent("database", "ok", "SQLite ok."),
                ReadinessComponent("artifact_storage", "ok", "Artifacts ok."),
            ),
        ),
        evidence=ProductionReadinessEvidence(
            live_entra_verified=True,
            tls_host_verified=True,
            backup_restore_verified=True,
            reviewer_independence_verified=True,
            valprobe_parser_validated=True,
            retention_policy_approved=True,
            final_human_approval_recorded=True,
            references={
                "validation_package": "Docs/Validation/evidence/latest",
                "live_entra": "evidence/live-entra-evidence.json",
                "tls_host": "evidence/tls-host-evidence.json",
                "backup_restore": "evidence/backup-restore.json",
                "reviewer_independence": "evidence/reviewer-independence.json",
                "valprobe_parser_validation": (
                    "evidence/valprobe-parser-validation.json"
                ),
                "retention_policy": "evidence/retention-policy.json",
                "human_approval": "evidence/human-approval-evidence.json",
            },
        ),
        generated_at=datetime(2026, 6, 9, 8, 0, tzinfo=timezone.utc),
        software_version="0.1.0",
    )

    payload = report.to_payload()

    assert report.ready_for_go_live_review
    assert payload["status"] == "ready_for_go_live_review"
    assert payload["blockers"] == []
    assert payload["evidence"]["references"]["validation_package"] == (
        "Docs/Validation/evidence/latest"
    )
    assert payload["evidence"]["references"]["human_approval"] == (
        "evidence/human-approval-evidence.json"
    )


def test_production_readiness_report_blocks_verified_flags_without_references(
    tmp_path,
):
    report = build_production_readiness_report(
        settings=_settings(tmp_path),
        runtime_readiness=RuntimeReadiness(
            status="ready",
            components=(
                ReadinessComponent("database", "ok", "SQLite ok."),
                ReadinessComponent("artifact_storage", "ok", "Artifacts ok."),
            ),
        ),
        evidence=ProductionReadinessEvidence(
            live_entra_verified=True,
            tls_host_verified=True,
            backup_restore_verified=True,
            reviewer_independence_verified=True,
            valprobe_parser_validated=True,
            retention_policy_approved=True,
            final_human_approval_recorded=True,
            references={"validation_package": "Docs/Validation/evidence/latest"},
        ),
        generated_at=datetime(2026, 6, 9, 8, 0, tzinfo=timezone.utc),
        software_version="0.1.0",
    )

    assert report.status == "blocked"
    assert report.blockers == (
        "live_entra_evidence_reference_missing",
        "tls_host_evidence_reference_missing",
        "backup_restore_evidence_reference_missing",
        "reviewer_independence_evidence_reference_missing",
        "valprobe_parser_validation_evidence_reference_missing",
        "retention_policy_evidence_reference_missing",
        "human_approval_evidence_reference_missing",
    )


def test_generate_production_readiness_report_cli_writes_blocked_report(
    tmp_path,
    monkeypatch,
):
    database_path = tmp_path / "simval.sqlite3"
    artifact_path = tmp_path / "artifacts"
    artifact_path.mkdir()
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE notes (id TEXT PRIMARY KEY)")
    output_path = tmp_path / "production-readiness.json"
    monkeypatch.setenv("SIMVAL_DATABASE_PATH", str(database_path))
    monkeypatch.setenv("SIMVAL_ARTIFACT_STORAGE_PATH", str(artifact_path))
    monkeypatch.setenv("SIMVAL_ENABLED_DISCIPLINES", "temperature")
    monkeypatch.setenv("SIMVAL_AUTH_PROVIDER", "entra_id_free")
    monkeypatch.setenv("SIMVAL_ENTRA_TENANT_ID", "tenant-001")
    monkeypatch.setenv("SIMVAL_ENTRA_CLIENT_ID", "client-001")

    result = main(
        [
            "--software-version",
            "0.1.0",
            "--generated-at",
            "2026-06-09T08:00:00Z",
            "--evidence",
            "pytest=Docs/Validation/evidence/latest/pytest.xml",
            "--output",
            str(output_path),
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result == 2
    assert payload["status"] == "blocked"
    assert payload["runtime_readiness"]["status"] == "ready"
    assert payload["evidence"]["references"] == {
        "pytest": "Docs/Validation/evidence/latest/pytest.xml"
    }
    assert "runtime_profile_not_production" in payload["blockers"]
    assert "final_human_approval_missing" in payload["blockers"]
    assert "production_smoke_evidence_missing" in payload["blockers"]
    assert payload["evidence"]["reference_manifest"][0]["key"] == "pytest"


def test_generate_production_readiness_report_cli_blocks_missing_evidence_file(
    tmp_path,
    monkeypatch,
):
    _configure_ready_runtime(tmp_path, monkeypatch)
    output_path = tmp_path / "production-readiness.json"

    result = main(
        [
            "--software-version",
            "0.1.0",
            "--generated-at",
            "2026-06-09T08:00:00Z",
            "--live-entra-verified",
            "--tls-host-verified",
            "--backup-restore-verified",
            "--reviewer-independence-verified",
            "--valprobe-parser-validated",
            "--retention-policy-approved",
            "--final-human-approval-recorded",
            "--evidence",
            f"live_entra={tmp_path / 'missing-live-entra.json'}",
            "--evidence",
            f"tls_host={tmp_path / 'missing-tls-host.json'}",
            "--evidence",
            f"backup_restore={tmp_path / 'missing-backup-restore.json'}",
            "--evidence",
            f"reviewer_independence={tmp_path / 'missing-reviewer.json'}",
            "--evidence",
            f"valprobe_parser_validation={tmp_path / 'missing-parser.json'}",
            "--evidence",
            f"retention_policy={tmp_path / 'missing-retention.json'}",
            "--evidence",
            f"human_approval={tmp_path / 'missing-approval.json'}",
            "--output",
            str(output_path),
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result == 2
    assert payload["status"] == "blocked"
    assert payload["evidence"]["unavailable_references"] == [
        "backup_restore",
        "human_approval",
        "live_entra",
        "retention_policy",
        "reviewer_independence",
        "tls_host",
        "valprobe_parser_validation",
    ]
    assert "live_entra_evidence_reference_unavailable" in payload["blockers"]


def test_generate_production_readiness_report_cli_records_evidence_manifest(
    tmp_path,
    monkeypatch,
):
    _configure_ready_runtime(tmp_path, monkeypatch)
    output_path = tmp_path / "production-readiness.json"
    evidence_files = {
        "live_entra": tmp_path / "live-entra.json",
        "tls_host": tmp_path / "tls-host.json",
        "backup_restore": tmp_path / "backup-restore.json",
        "reviewer_independence": tmp_path / "reviewer-independence.json",
        "valprobe_parser_validation": tmp_path / "valprobe-parser-validation.json",
        "retention_policy": tmp_path / "retention-policy.json",
        "human_approval": tmp_path / "human-approval.json",
        "smoke_evidence": tmp_path / "smoke-evidence.json",
    }
    for key, path in evidence_files.items():
        path.write_text(f"{key} evidence", encoding="utf-8")
    for key in (
        "backup_restore",
        "reviewer_independence",
        "valprobe_parser_validation",
        "retention_policy",
        "human_approval",
        "live_entra",
        "tls_host",
    ):
        evidence_files[key].write_text('{"status":"passed"}', encoding="utf-8")
    _write_smoke_evidence(evidence_files["smoke_evidence"], software_version="0.1.0")

    result = main(
        [
            "--software-version",
            "0.1.0",
            "--generated-at",
            "2026-06-09T08:00:00Z",
            "--live-entra-verified",
            "--tls-host-verified",
            "--backup-restore-verified",
            "--reviewer-independence-verified",
            "--valprobe-parser-validated",
            "--retention-policy-approved",
            "--final-human-approval-recorded",
            *[
                value
                for key, path in evidence_files.items()
                for value in ("--evidence", f"{key}={path}")
            ],
            "--output",
            str(output_path),
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result == 0
    assert payload["status"] == "ready_for_go_live_review"
    assert payload["blockers"] == []
    assert payload["evidence"]["unavailable_references"] == []
    manifest_by_key = {
        record["key"]: record for record in payload["evidence"]["reference_manifest"]
    }
    assert set(manifest_by_key) == set(evidence_files)
    assert manifest_by_key["human_approval"]["kind"] == "file"
    assert len(manifest_by_key["human_approval"]["sha256"]) == 64
    assert manifest_by_key["human_approval"]["size_bytes"] > 0


def test_generate_production_readiness_report_cli_blocks_failed_pilot_evidence(
    tmp_path,
    monkeypatch,
):
    _configure_ready_runtime(tmp_path, monkeypatch)
    output_path = tmp_path / "production-readiness.json"
    evidence_files = {
        "live_entra": tmp_path / "live-entra.json",
        "tls_host": tmp_path / "tls-host.json",
        "backup_restore": tmp_path / "backup-restore.json",
        "reviewer_independence": tmp_path / "reviewer-independence.json",
        "valprobe_parser_validation": tmp_path / "valprobe-parser-validation.json",
        "retention_policy": tmp_path / "retention-policy.json",
        "human_approval": tmp_path / "human-approval.json",
        "smoke_evidence": tmp_path / "smoke-evidence.json",
    }
    for key, path in evidence_files.items():
        path.write_text(f"{key} evidence", encoding="utf-8")
    evidence_files["backup_restore"].write_text('{"status":"blocked"}', encoding="utf-8")
    evidence_files["reviewer_independence"].write_text(
        '{"status":"passed"}',
        encoding="utf-8",
    )
    evidence_files["valprobe_parser_validation"].write_text(
        '{"status":"passed"}',
        encoding="utf-8",
    )
    evidence_files["retention_policy"].write_text(
        '{"status":"passed"}',
        encoding="utf-8",
    )
    evidence_files["human_approval"].write_text(
        '{"status":"passed"}',
        encoding="utf-8",
    )
    evidence_files["live_entra"].write_text(
        '{"status":"passed"}',
        encoding="utf-8",
    )
    evidence_files["tls_host"].write_text(
        '{"status":"passed"}',
        encoding="utf-8",
    )
    _write_smoke_evidence(evidence_files["smoke_evidence"], software_version="0.1.0")

    result = main(
        [
            "--software-version",
            "0.1.0",
            "--generated-at",
            "2026-06-09T08:00:00Z",
            "--live-entra-verified",
            "--tls-host-verified",
            "--backup-restore-verified",
            "--reviewer-independence-verified",
            "--valprobe-parser-validated",
            "--retention-policy-approved",
            "--final-human-approval-recorded",
            *[
                value
                for key, path in evidence_files.items()
                for value in ("--evidence", f"{key}={path}")
            ],
            "--output",
            str(output_path),
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result == 2
    assert payload["status"] == "blocked"
    assert "backup_restore_evidence_not_passed" in payload["blockers"]


def test_generate_production_readiness_report_cli_blocks_failed_retention_evidence(
    tmp_path,
    monkeypatch,
):
    _configure_ready_runtime(tmp_path, monkeypatch)
    output_path = tmp_path / "production-readiness.json"
    retention_evidence = tmp_path / "retention-policy.json"
    retention_evidence.write_text('{"status":"blocked"}', encoding="utf-8")
    smoke_evidence = tmp_path / "smoke-evidence.json"
    _write_smoke_evidence(smoke_evidence, software_version="0.1.0")

    result = main(
        [
            "--software-version",
            "0.1.0",
            "--generated-at",
            "2026-06-09T08:00:00Z",
            "--retention-policy-approved",
            "--evidence",
            f"retention_policy={retention_evidence}",
            "--evidence",
            f"smoke_evidence={smoke_evidence}",
            "--output",
            str(output_path),
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result == 2
    assert "retention_policy_evidence_not_passed" in payload["blockers"]


def test_generate_production_readiness_report_cli_blocks_failed_human_approval(
    tmp_path,
    monkeypatch,
):
    _configure_ready_runtime(tmp_path, monkeypatch)
    output_path = tmp_path / "production-readiness.json"
    approval_evidence = tmp_path / "human-approval.json"
    approval_evidence.write_text('{"status":"blocked"}', encoding="utf-8")
    smoke_evidence = tmp_path / "smoke-evidence.json"
    _write_smoke_evidence(smoke_evidence, software_version="0.1.0")

    result = main(
        [
            "--software-version",
            "0.1.0",
            "--generated-at",
            "2026-06-09T08:00:00Z",
            "--final-human-approval-recorded",
            "--evidence",
            f"human_approval={approval_evidence}",
            "--evidence",
            f"smoke_evidence={smoke_evidence}",
            "--output",
            str(output_path),
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result == 2
    assert "human_approval_evidence_not_passed" in payload["blockers"]


def test_generate_production_readiness_report_cli_blocks_failed_live_entra(
    tmp_path,
    monkeypatch,
):
    _configure_ready_runtime(tmp_path, monkeypatch)
    output_path = tmp_path / "production-readiness.json"
    live_entra = tmp_path / "live-entra.json"
    live_entra.write_text('{"status":"blocked"}', encoding="utf-8")
    smoke_evidence = tmp_path / "smoke-evidence.json"
    _write_smoke_evidence(smoke_evidence, software_version="0.1.0")

    result = main(
        [
            "--software-version",
            "0.1.0",
            "--generated-at",
            "2026-06-09T08:00:00Z",
            "--live-entra-verified",
            "--evidence",
            f"live_entra={live_entra}",
            "--evidence",
            f"smoke_evidence={smoke_evidence}",
            "--output",
            str(output_path),
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result == 2
    assert "live_entra_evidence_not_passed" in payload["blockers"]


def test_generate_production_readiness_report_cli_blocks_failed_tls_host(
    tmp_path,
    monkeypatch,
):
    _configure_ready_runtime(tmp_path, monkeypatch)
    output_path = tmp_path / "production-readiness.json"
    tls_host = tmp_path / "tls-host.json"
    tls_host.write_text('{"status":"blocked"}', encoding="utf-8")
    smoke_evidence = tmp_path / "smoke-evidence.json"
    _write_smoke_evidence(smoke_evidence, software_version="0.1.0")

    result = main(
        [
            "--software-version",
            "0.1.0",
            "--generated-at",
            "2026-06-09T08:00:00Z",
            "--tls-host-verified",
            "--evidence",
            f"tls_host={tls_host}",
            "--evidence",
            f"smoke_evidence={smoke_evidence}",
            "--output",
            str(output_path),
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result == 2
    assert "tls_host_evidence_not_passed" in payload["blockers"]


def test_generate_production_readiness_report_cli_blocks_invalid_pilot_evidence(
    tmp_path,
    monkeypatch,
):
    _configure_ready_runtime(tmp_path, monkeypatch)
    output_path = tmp_path / "production-readiness.json"
    reviewer_evidence = tmp_path / "reviewer-independence.json"
    reviewer_evidence.write_text("not-json", encoding="utf-8")
    smoke_evidence = tmp_path / "smoke-evidence.json"
    _write_smoke_evidence(smoke_evidence, software_version="0.1.0")

    result = main(
        [
            "--software-version",
            "0.1.0",
            "--generated-at",
            "2026-06-09T08:00:00Z",
            "--reviewer-independence-verified",
            "--evidence",
            f"reviewer_independence={reviewer_evidence}",
            "--evidence",
            f"smoke_evidence={smoke_evidence}",
            "--output",
            str(output_path),
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result == 2
    assert "reviewer_independence_evidence_invalid" in payload["blockers"]


def test_generate_production_readiness_report_cli_blocks_failed_smoke_evidence(
    tmp_path,
    monkeypatch,
):
    _configure_ready_runtime(tmp_path, monkeypatch)
    smoke_path = tmp_path / "smoke-evidence.json"
    _write_smoke_evidence(smoke_path, software_version="0.1.0", status="failed")
    output_path = tmp_path / "production-readiness.json"

    result = main(
        [
            "--software-version",
            "0.1.0",
            "--generated-at",
            "2026-06-09T08:00:00Z",
            "--evidence",
            f"smoke_evidence={smoke_path}",
            "--output",
            str(output_path),
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result == 2
    assert "production_smoke_failed" in payload["blockers"]


def test_generate_production_readiness_report_cli_blocks_smoke_version_mismatch(
    tmp_path,
    monkeypatch,
):
    _configure_ready_runtime(tmp_path, monkeypatch)
    smoke_path = tmp_path / "smoke-evidence.json"
    _write_smoke_evidence(smoke_path, software_version="different")
    output_path = tmp_path / "production-readiness.json"

    result = main(
        [
            "--software-version",
            "0.1.0",
            "--generated-at",
            "2026-06-09T08:00:00Z",
            "--evidence",
            f"smoke_evidence={smoke_path}",
            "--output",
            str(output_path),
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result == 2
    assert "production_smoke_software_version_mismatch" in payload["blockers"]


def _settings(tmp_path) -> ApiSettings:
    return ApiSettings.from_environment(
        {
            "SIMVAL_DATABASE_PATH": str(tmp_path / "simval.sqlite3"),
            "SIMVAL_ARTIFACT_STORAGE_PATH": str(tmp_path / "artifacts"),
            "SIMVAL_RUNTIME_PROFILE": "production",
            "SIMVAL_ENABLED_DISCIPLINES": "temperature",
            "SIMVAL_AUTH_PROVIDER": "entra_id_free",
            "SIMVAL_ENTRA_TENANT_ID": "tenant-001",
            "SIMVAL_ENTRA_CLIENT_ID": "client-001",
        }
    )


def _configure_ready_runtime(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "simval.sqlite3"
    artifact_path = tmp_path / "artifacts"
    artifact_path.mkdir()
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE notes (id TEXT PRIMARY KEY)")
    monkeypatch.setenv("SIMVAL_DATABASE_PATH", str(database_path))
    monkeypatch.setenv("SIMVAL_ARTIFACT_STORAGE_PATH", str(artifact_path))
    monkeypatch.setenv("SIMVAL_RUNTIME_PROFILE", "production")
    monkeypatch.setenv("SIMVAL_ENABLED_DISCIPLINES", "temperature")
    monkeypatch.setenv("SIMVAL_AUTH_PROVIDER", "entra_id_free")
    monkeypatch.setenv("SIMVAL_ENTRA_TENANT_ID", "tenant-001")
    monkeypatch.setenv("SIMVAL_ENTRA_CLIENT_ID", "client-001")


def _write_smoke_evidence(
    path,
    *,
    software_version: str,
    status: str = "passed",
) -> None:
    path.write_text(
        json.dumps(
            {
                "status": status,
                "generated_at": "2026-06-09T08:00:00+00:00",
                "software_version": software_version,
                "base_url": "http://127.0.0.1:8010",
                "scope": {"enabled_disciplines": ["temperature"]},
                "endpoints": [
                    {"path": "/health", "status_code": 200, "ok": True},
                    {"path": "/readiness", "status_code": 200, "ok": True},
                    {"path": "/app", "status_code": 200, "ok": True},
                    {"path": "/app/workflow", "status_code": 200, "ok": True},
                ],
            }
        ),
        encoding="utf-8",
    )
