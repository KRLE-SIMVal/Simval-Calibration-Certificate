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
    assert "final_human_approval_missing" in report.blockers
    assert report.scope == {
        "enabled_disciplines": ["temperature"],
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
            retention_policy_approved=True,
            final_human_approval_recorded=True,
            references={"validation_package": "Docs/Validation/evidence/latest"},
        ),
        generated_at=datetime(2026, 6, 9, 8, 0, tzinfo=timezone.utc),
        software_version="0.1.0",
    )

    payload = report.to_payload()

    assert report.ready_for_go_live_review
    assert payload["status"] == "ready_for_go_live_review"
    assert payload["blockers"] == []
    assert payload["evidence"]["references"] == {
        "validation_package": "Docs/Validation/evidence/latest"
    }


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
    assert "final_human_approval_missing" in payload["blockers"]


def _settings(tmp_path) -> ApiSettings:
    return ApiSettings.from_environment(
        {
            "SIMVAL_DATABASE_PATH": str(tmp_path / "simval.sqlite3"),
            "SIMVAL_ARTIFACT_STORAGE_PATH": str(tmp_path / "artifacts"),
            "SIMVAL_ENABLED_DISCIPLINES": "temperature",
            "SIMVAL_AUTH_PROVIDER": "entra_id_free",
            "SIMVAL_ENTRA_TENANT_ID": "tenant-001",
            "SIMVAL_ENTRA_CLIENT_ID": "client-001",
        }
    )
