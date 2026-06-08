"""Controlled SQLite backup and restore helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import sqlite3


class BackupOperationError(ValueError):
    """Raised when backup or restore evidence cannot be produced safely."""


@dataclass(frozen=True, slots=True)
class SQLiteBackupVerification:
    database_path: Path
    integrity_check: str
    sha256: str
    size_bytes: int

    def to_payload(self) -> dict:
        return {
            "database_path": self.database_path.as_posix(),
            "integrity_check": self.integrity_check,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True, slots=True)
class SQLiteBackupEvidence:
    source_database_path: Path
    backup_path: Path
    created_at: datetime
    verification: SQLiteBackupVerification

    def to_payload(self) -> dict:
        return {
            "source_database_path": self.source_database_path.as_posix(),
            "backup_path": self.backup_path.as_posix(),
            "created_at": self.created_at.isoformat(),
            "verification": self.verification.to_payload(),
        }


@dataclass(frozen=True, slots=True)
class SQLiteRestoreEvidence:
    backup_path: Path
    restored_database_path: Path
    restored_at: datetime
    backup_verification: SQLiteBackupVerification
    restored_verification: SQLiteBackupVerification

    def to_payload(self) -> dict:
        return {
            "backup_path": self.backup_path.as_posix(),
            "restored_database_path": self.restored_database_path.as_posix(),
            "restored_at": self.restored_at.isoformat(),
            "backup_verification": self.backup_verification.to_payload(),
            "restored_verification": self.restored_verification.to_payload(),
        }


def create_sqlite_backup(
    *,
    source_database_path: Path,
    backup_directory: Path,
    created_at: datetime,
) -> SQLiteBackupEvidence:
    """Create a consistent SQLite backup and return verification evidence."""
    _require_timezone_aware(created_at, "Backup timestamp")
    source_path = _existing_file(source_database_path, "Source database")
    backup_dir = backup_directory.resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = _backup_path(backup_dir, created_at)
    if backup_path.exists():
        raise BackupOperationError("Backup file already exists.")
    try:
        with sqlite3.connect(source_path) as source_connection:
            with sqlite3.connect(backup_path) as backup_connection:
                source_connection.backup(backup_connection)
    except sqlite3.DatabaseError as exc:
        _remove_partial_file(backup_path)
        raise BackupOperationError("SQLite backup failed.") from exc
    verification = verify_sqlite_backup(backup_path)
    if verification.integrity_check != "ok":
        raise BackupOperationError("SQLite backup integrity check failed.")
    return SQLiteBackupEvidence(
        source_database_path=source_path,
        backup_path=backup_path,
        created_at=created_at.astimezone(timezone.utc),
        verification=verification,
    )


def restore_sqlite_backup(
    *,
    backup_path: Path,
    restored_database_path: Path,
    restored_at: datetime,
) -> SQLiteRestoreEvidence:
    """Restore a verified SQLite backup into a new database path."""
    _require_timezone_aware(restored_at, "Restore timestamp")
    source_backup_path = _existing_file(backup_path, "Backup database")
    target_path = restored_database_path.resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        raise BackupOperationError("Restore target already exists.")
    backup_verification = verify_sqlite_backup(source_backup_path)
    if backup_verification.integrity_check != "ok":
        raise BackupOperationError("Backup integrity check failed before restore.")
    try:
        with sqlite3.connect(source_backup_path) as backup_connection:
            with sqlite3.connect(target_path) as restored_connection:
                backup_connection.backup(restored_connection)
    except sqlite3.DatabaseError as exc:
        _remove_partial_file(target_path)
        raise BackupOperationError("SQLite restore failed.") from exc
    restored_verification = verify_sqlite_backup(target_path)
    if restored_verification.integrity_check != "ok":
        raise BackupOperationError("Restored database integrity check failed.")
    return SQLiteRestoreEvidence(
        backup_path=source_backup_path,
        restored_database_path=target_path,
        restored_at=restored_at.astimezone(timezone.utc),
        backup_verification=backup_verification,
        restored_verification=restored_verification,
    )


def verify_sqlite_backup(database_path: Path) -> SQLiteBackupVerification:
    """Run SQLite integrity verification and checksum the database file."""
    resolved_path = _existing_file(database_path, "SQLite database")
    try:
        with sqlite3.connect(resolved_path) as connection:
            rows = connection.execute("PRAGMA integrity_check").fetchall()
    except sqlite3.DatabaseError as exc:
        raise BackupOperationError("SQLite integrity check failed to run.") from exc
    integrity_check = "; ".join(str(row[0]) for row in rows)
    return SQLiteBackupVerification(
        database_path=resolved_path,
        integrity_check=integrity_check,
        sha256=_sha256(resolved_path),
        size_bytes=resolved_path.stat().st_size,
    )


def _backup_path(backup_directory: Path, created_at: datetime) -> Path:
    timestamp = created_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = (backup_directory / f"simval-sqlite-backup-{timestamp}.sqlite3")
    resolved_backup_path = backup_path.resolve()
    if backup_directory not in resolved_backup_path.parents:
        raise BackupOperationError("Backup path must stay within backup directory.")
    return resolved_backup_path


def _existing_file(path: Path, label: str) -> Path:
    resolved_path = path.resolve()
    if not resolved_path.is_file():
        raise BackupOperationError(f"{label} does not exist.")
    return resolved_path


def _require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise BackupOperationError(f"{field_name} must be timezone-aware.")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _remove_partial_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass

