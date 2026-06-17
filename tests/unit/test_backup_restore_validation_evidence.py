import json
from datetime import datetime, timezone

import pytest

from app.backend.validation.backup_restore import (
    BackupRestoreValidationEvidenceError,
    build_backup_restore_validation_evidence,
)
from scripts.validation.generate_backup_restore_validation_evidence import main


def test_backup_restore_validation_evidence_passes_when_integrity_and_review_pass(
    tmp_path,
):
    backup, restore = _write_backup_restore_evidence(tmp_path)

    evidence = build_backup_restore_validation_evidence(
        backup_evidence_path=backup,
        restore_evidence_path=restore,
        reviewer_approved=True,
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    payload = json.loads(evidence.to_json())

    assert payload["status"] == "passed"
    assert payload["blockers"] == []
    assert payload["backup_integrity_check"] == "ok"
    assert payload["restored_integrity_check"] == "ok"
    assert payload["backup_and_restored_checksums_match"] is True
    assert payload["reviewer_approved"] is True
    assert {item["key"] for item in payload["evidence_files"]} == {
        "backup_evidence",
        "restore_evidence",
    }
    assert all(len(item["sha256"]) == 64 for item in payload["evidence_files"])
    assert "C:" not in evidence.to_json()


def test_backup_restore_validation_evidence_blocks_missing_review(tmp_path):
    backup, restore = _write_backup_restore_evidence(tmp_path)

    evidence = build_backup_restore_validation_evidence(
        backup_evidence_path=backup,
        restore_evidence_path=restore,
        reviewer_approved=False,
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    payload = json.loads(evidence.to_json())

    assert payload["status"] == "blocked"
    assert payload["blockers"] == ["backup_restore_reviewer_approval_missing"]


def test_backup_restore_validation_evidence_blocks_checksum_mismatch(tmp_path):
    backup, restore = _write_backup_restore_evidence(tmp_path, restored_sha="other")

    evidence = build_backup_restore_validation_evidence(
        backup_evidence_path=backup,
        restore_evidence_path=restore,
        reviewer_approved=True,
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    payload = json.loads(evidence.to_json())

    assert payload["status"] == "blocked"
    assert "backup_restore_checksum_mismatch" in payload["blockers"]


def test_backup_restore_validation_evidence_rejects_invalid_json(tmp_path):
    backup = tmp_path / "backup-evidence.json"
    restore = tmp_path / "restore-evidence.json"
    backup.write_text("not json", encoding="utf-8")
    restore.write_text("{}", encoding="utf-8")

    with pytest.raises(BackupRestoreValidationEvidenceError, match="valid JSON"):
        build_backup_restore_validation_evidence(
            backup_evidence_path=backup,
            restore_evidence_path=restore,
            reviewer_approved=True,
            generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
        )


def test_backup_restore_validation_evidence_rejects_naive_timestamp(tmp_path):
    backup, restore = _write_backup_restore_evidence(tmp_path)

    with pytest.raises(BackupRestoreValidationEvidenceError, match="timezone-aware"):
        build_backup_restore_validation_evidence(
            backup_evidence_path=backup,
            restore_evidence_path=restore,
            reviewer_approved=True,
            generated_at=datetime(2026, 6, 15, 12, 0),
        )


def test_generate_backup_restore_validation_evidence_cli_writes_passed_output(
    tmp_path,
):
    backup, restore = _write_backup_restore_evidence(tmp_path)
    output = tmp_path / "backup-restore-validation.json"

    result = main(
        [
            "--backup-evidence",
            str(backup),
            "--restore-evidence",
            str(restore),
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


def test_generate_backup_restore_validation_evidence_cli_returns_two_when_blocked(
    tmp_path,
):
    backup, restore = _write_backup_restore_evidence(tmp_path)
    output = tmp_path / "backup-restore-validation.json"

    result = main(
        [
            "--backup-evidence",
            str(backup),
            "--restore-evidence",
            str(restore),
            "--generated-at",
            "2026-06-15T12:00:00Z",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))

    assert result == 2
    assert payload["blockers"] == ["backup_restore_reviewer_approval_missing"]


def _write_backup_restore_evidence(tmp_path, *, restored_sha="abc123"):
    backup = tmp_path / "backup-evidence.json"
    restore = tmp_path / "restore-evidence.json"
    backup_payload = {
        "source_database_path": "C:/SIMVal/data/simval.sqlite3",
        "backup_path": "C:/SIMVal/backups/simval.sqlite3",
        "created_at": "2026-06-15T12:00:00+00:00",
        "verification": {
            "database_path": "C:/SIMVal/backups/simval.sqlite3",
            "integrity_check": "ok",
            "sha256": "abc123",
            "size_bytes": 4096,
        },
    }
    restore_payload = {
        "backup_path": "C:/SIMVal/backups/simval.sqlite3",
        "restored_database_path": "C:/SIMVal/restore/simval.sqlite3",
        "restored_at": "2026-06-15T13:00:00+00:00",
        "backup_verification": {
            "database_path": "C:/SIMVal/backups/simval.sqlite3",
            "integrity_check": "ok",
            "sha256": "abc123",
            "size_bytes": 4096,
        },
        "restored_verification": {
            "database_path": "C:/SIMVal/restore/simval.sqlite3",
            "integrity_check": "ok",
            "sha256": restored_sha,
            "size_bytes": 4096,
        },
    }
    backup.write_text(json.dumps(backup_payload), encoding="utf-8")
    restore.write_text(json.dumps(restore_payload), encoding="utf-8")
    return backup, restore
