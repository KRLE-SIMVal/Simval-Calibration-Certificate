import json
import sqlite3
from datetime import datetime, timezone

import pytest

from app.backend.operations.backup import (
    BackupOperationError,
    create_sqlite_backup,
    restore_sqlite_backup,
    verify_sqlite_backup,
)
from scripts.maintenance.create_sqlite_backup import main as backup_cli_main
from scripts.maintenance.restore_sqlite_backup import main as restore_cli_main


def test_sqlite_backup_writes_verifiable_database_copy(tmp_path):
    source_path = tmp_path / "simval.sqlite3"
    _create_database(source_path)

    evidence = create_sqlite_backup(
        source_database_path=source_path,
        backup_directory=tmp_path / "backups",
        created_at=datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc),
    )

    assert evidence.backup_path.name == "simval-sqlite-backup-20260608T120000Z.sqlite3"
    assert evidence.created_at == datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    assert evidence.verification.integrity_check == "ok"
    assert len(evidence.verification.sha256) == 64
    assert evidence.verification.size_bytes > 0
    assert _database_note(evidence.backup_path) == "validated backup content"


def test_sqlite_backup_rejects_missing_source(tmp_path):
    with pytest.raises(BackupOperationError, match="Source database does not exist"):
        create_sqlite_backup(
            source_database_path=tmp_path / "missing.sqlite3",
            backup_directory=tmp_path / "backups",
            created_at=datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc),
        )


def test_sqlite_backup_requires_timezone_aware_timestamp(tmp_path):
    source_path = tmp_path / "simval.sqlite3"
    _create_database(source_path)

    with pytest.raises(BackupOperationError, match="Backup timestamp"):
        create_sqlite_backup(
            source_database_path=source_path,
            backup_directory=tmp_path / "backups",
            created_at=datetime(2026, 6, 8, 12, 0),
        )


def test_sqlite_backup_rejects_duplicate_backup_filename(tmp_path):
    source_path = tmp_path / "simval.sqlite3"
    _create_database(source_path)
    timestamp = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    create_sqlite_backup(
        source_database_path=source_path,
        backup_directory=tmp_path / "backups",
        created_at=timestamp,
    )

    with pytest.raises(BackupOperationError, match="Backup file already exists"):
        create_sqlite_backup(
            source_database_path=source_path,
            backup_directory=tmp_path / "backups",
            created_at=timestamp,
        )


def test_sqlite_restore_writes_new_database_and_verification_evidence(tmp_path):
    source_path = tmp_path / "simval.sqlite3"
    _create_database(source_path)
    backup = create_sqlite_backup(
        source_database_path=source_path,
        backup_directory=tmp_path / "backups",
        created_at=datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc),
    )

    evidence = restore_sqlite_backup(
        backup_path=backup.backup_path,
        restored_database_path=tmp_path / "restored" / "simval.sqlite3",
        restored_at=datetime(2026, 6, 8, 13, 0, tzinfo=timezone.utc),
    )

    assert evidence.backup_verification.integrity_check == "ok"
    assert evidence.restored_verification.integrity_check == "ok"
    assert evidence.backup_verification.sha256 == evidence.restored_verification.sha256
    assert _database_note(evidence.restored_database_path) == "validated backup content"


def test_sqlite_restore_rejects_existing_target(tmp_path):
    source_path = tmp_path / "simval.sqlite3"
    restored_path = tmp_path / "restored.sqlite3"
    _create_database(source_path)
    _create_database(restored_path)
    backup = create_sqlite_backup(
        source_database_path=source_path,
        backup_directory=tmp_path / "backups",
        created_at=datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc),
    )

    with pytest.raises(BackupOperationError, match="Restore target already exists"):
        restore_sqlite_backup(
            backup_path=backup.backup_path,
            restored_database_path=restored_path,
            restored_at=datetime(2026, 6, 8, 13, 0, tzinfo=timezone.utc),
        )


def test_sqlite_backup_cli_writes_json_evidence(tmp_path):
    source_path = tmp_path / "simval.sqlite3"
    evidence_path = tmp_path / "backup-evidence.json"
    _create_database(source_path)

    result = backup_cli_main(
        [
            "--database-path",
            str(source_path),
            "--backup-dir",
            str(tmp_path / "backups"),
            "--evidence-output",
            str(evidence_path),
        ]
    )

    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert result == 0
    assert payload["backup_path"].endswith(".sqlite3")
    assert payload["verification"]["integrity_check"] == "ok"
    assert len(payload["verification"]["sha256"]) == 64


def test_sqlite_restore_cli_writes_json_evidence(tmp_path):
    source_path = tmp_path / "simval.sqlite3"
    _create_database(source_path)
    backup = create_sqlite_backup(
        source_database_path=source_path,
        backup_directory=tmp_path / "backups",
        created_at=datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc),
    )
    evidence_path = tmp_path / "restore-evidence.json"
    restored_path = tmp_path / "restored.sqlite3"

    result = restore_cli_main(
        [
            "--backup-path",
            str(backup.backup_path),
            "--restore-path",
            str(restored_path),
            "--evidence-output",
            str(evidence_path),
        ]
    )

    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert result == 0
    assert payload["restored_database_path"] == restored_path.resolve().as_posix()
    assert payload["backup_verification"]["integrity_check"] == "ok"
    assert payload["restored_verification"]["integrity_check"] == "ok"


def test_verify_sqlite_backup_rejects_non_sqlite_file(tmp_path):
    not_database = tmp_path / "not-a-database.sqlite3"
    not_database.write_text("not sqlite", encoding="utf-8")

    with pytest.raises(BackupOperationError, match="SQLite integrity check"):
        verify_sqlite_backup(not_database)


def _create_database(path):
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE notes (id TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute(
            "INSERT INTO notes (id, value) VALUES ('note-001', 'validated backup content')"
        )


def _database_note(path):
    with sqlite3.connect(path) as connection:
        return connection.execute(
            "SELECT value FROM notes WHERE id = 'note-001'"
        ).fetchone()[0]

