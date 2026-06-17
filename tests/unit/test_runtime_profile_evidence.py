import json
from datetime import datetime, timezone

import pytest

from app.backend.api.settings import ApiSettings
from app.backend.validation.runtime_profile import (
    RuntimeProfileEvidenceError,
    build_runtime_profile_evidence,
)
from scripts.validation.generate_runtime_profile_evidence import main


def test_runtime_profile_evidence_passes_for_production_entra_temperature(tmp_path):
    evidence = build_runtime_profile_evidence(
        settings=_production_settings(tmp_path),
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    payload = json.loads(evidence.to_json())

    assert payload["status"] == "passed"
    assert payload["blockers"] == []
    assert payload["runtime_profile"] == "production"
    assert payload["auth_provider"] == "entra_id_free"
    assert payload["enabled_disciplines"] == ["temperature"]
    assert payload["database_path_configured"] is True
    assert payload["artifact_storage_path_configured"] is True
    assert payload["entra_configured"] is True
    assert payload["entra_session_hours"] == 8
    assert "simval.sqlite3" not in evidence.to_json()
    assert "tenant-001" not in evidence.to_json()


def test_runtime_profile_evidence_blocks_development_local_session(tmp_path):
    settings = ApiSettings.from_environment(
        {
            "SIMVAL_DATABASE_PATH": str(tmp_path / "simval.sqlite3"),
            "SIMVAL_ARTIFACT_STORAGE_PATH": str(tmp_path / "artifacts"),
        }
    )

    evidence = build_runtime_profile_evidence(
        settings=settings,
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    payload = json.loads(evidence.to_json())

    assert payload["status"] == "blocked"
    assert payload["blockers"] == [
        "runtime_profile_not_production",
        "auth_provider_not_entra_id_free",
        "entra_configuration_missing",
    ]


def test_runtime_profile_evidence_rejects_naive_timestamp(tmp_path):
    with pytest.raises(RuntimeProfileEvidenceError, match="timezone-aware"):
        build_runtime_profile_evidence(
            settings=_production_settings(tmp_path),
            generated_at=datetime(2026, 6, 15, 12, 0),
        )


def test_generate_runtime_profile_evidence_cli_writes_passed_output(
    tmp_path,
    monkeypatch,
):
    _configure_production_environment(tmp_path, monkeypatch)
    output_path = tmp_path / "runtime-profile.json"

    result = main(
        [
            "--generated-at",
            "2026-06-15T12:00:00Z",
            "--output",
            str(output_path),
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result == 0
    assert payload["status"] == "passed"
    assert payload["runtime_profile"] == "production"


def test_generate_runtime_profile_evidence_cli_returns_two_when_blocked(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("SIMVAL_DATABASE_PATH", str(tmp_path / "simval.sqlite3"))
    monkeypatch.setenv("SIMVAL_ARTIFACT_STORAGE_PATH", str(tmp_path / "artifacts"))
    output_path = tmp_path / "runtime-profile.json"

    result = main(
        [
            "--generated-at",
            "2026-06-15T12:00:00Z",
            "--output",
            str(output_path),
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result == 2
    assert "runtime_profile_not_production" in payload["blockers"]


def _production_settings(tmp_path) -> ApiSettings:
    return ApiSettings.from_environment(
        {
            "SIMVAL_DATABASE_PATH": str(tmp_path / "simval.sqlite3"),
            "SIMVAL_ARTIFACT_STORAGE_PATH": str(tmp_path / "artifacts"),
            "SIMVAL_RUNTIME_PROFILE": "production",
            "SIMVAL_AUTH_PROVIDER": "entra_id_free",
            "SIMVAL_ENTRA_TENANT_ID": "tenant-001",
            "SIMVAL_ENTRA_CLIENT_ID": "client-001",
        }
    )


def _configure_production_environment(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SIMVAL_DATABASE_PATH", str(tmp_path / "simval.sqlite3"))
    monkeypatch.setenv("SIMVAL_ARTIFACT_STORAGE_PATH", str(tmp_path / "artifacts"))
    monkeypatch.setenv("SIMVAL_RUNTIME_PROFILE", "production")
    monkeypatch.setenv("SIMVAL_AUTH_PROVIDER", "entra_id_free")
    monkeypatch.setenv("SIMVAL_ENTRA_TENANT_ID", "tenant-001")
    monkeypatch.setenv("SIMVAL_ENTRA_CLIENT_ID", "client-001")
