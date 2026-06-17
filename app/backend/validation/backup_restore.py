"""Backup/restore validation evidence for controlled pilot use."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
from typing import Any


class BackupRestoreValidationEvidenceError(ValueError):
    """Raised when backup/restore validation evidence is incomplete."""


@dataclass(frozen=True, slots=True)
class BackupRestoreEvidenceFile:
    key: str
    path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class BackupRestoreValidationEvidence:
    generated_at: str
    status: str
    blockers: tuple[str, ...]
    backup_integrity_check: str | None
    restored_integrity_check: str | None
    backup_and_restored_checksums_match: bool
    backup_size_bytes: int | None
    restored_size_bytes: int | None
    reviewer_approved: bool
    evidence_files: tuple[BackupRestoreEvidenceFile, ...]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def build_backup_restore_validation_evidence(
    *,
    backup_evidence_path: Path,
    restore_evidence_path: Path,
    reviewer_approved: bool = False,
    generated_at: datetime | None = None,
) -> BackupRestoreValidationEvidence:
    generated = generated_at or datetime.now(timezone.utc)
    if generated.tzinfo is None or generated.utcoffset() is None:
        raise BackupRestoreValidationEvidenceError(
            "Backup/restore validation evidence timestamp must be timezone-aware."
        )
    backup_payload = _json_file(backup_evidence_path, "backup evidence")
    restore_payload = _json_file(restore_evidence_path, "restore evidence")
    backup_integrity = _nested_value(
        backup_payload,
        ("verification", "integrity_check"),
    )
    restored_integrity = _nested_value(
        restore_payload,
        ("restored_verification", "integrity_check"),
    )
    backup_sha = _nested_value(backup_payload, ("verification", "sha256"))
    restore_backup_sha = _nested_value(
        restore_payload,
        ("backup_verification", "sha256"),
    )
    restored_sha = _nested_value(
        restore_payload,
        ("restored_verification", "sha256"),
    )
    backup_size = _nested_int(backup_payload, ("verification", "size_bytes"))
    restored_size = _nested_int(
        restore_payload,
        ("restored_verification", "size_bytes"),
    )
    checksums_match = (
        isinstance(backup_sha, str)
        and isinstance(restore_backup_sha, str)
        and isinstance(restored_sha, str)
        and backup_sha == restore_backup_sha == restored_sha
    )
    blockers = _blockers(
        backup_integrity=backup_integrity,
        restored_integrity=restored_integrity,
        checksums_match=checksums_match,
        reviewer_approved=reviewer_approved,
    )
    return BackupRestoreValidationEvidence(
        generated_at=generated.astimezone(timezone.utc).isoformat(),
        status="passed" if len(blockers) == 0 else "blocked",
        blockers=blockers,
        backup_integrity_check=(
            backup_integrity if isinstance(backup_integrity, str) else None
        ),
        restored_integrity_check=(
            restored_integrity if isinstance(restored_integrity, str) else None
        ),
        backup_and_restored_checksums_match=checksums_match,
        backup_size_bytes=backup_size,
        restored_size_bytes=restored_size,
        reviewer_approved=reviewer_approved,
        evidence_files=(
            _evidence_file("backup_evidence", backup_evidence_path),
            _evidence_file("restore_evidence", restore_evidence_path),
        ),
    )


def write_backup_restore_validation_evidence(
    evidence: BackupRestoreValidationEvidence,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(evidence.to_json() + "\n", encoding="utf-8")


def _blockers(
    *,
    backup_integrity: Any,
    restored_integrity: Any,
    checksums_match: bool,
    reviewer_approved: bool,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if backup_integrity != "ok":
        blockers.append("backup_integrity_check_not_ok")
    if restored_integrity != "ok":
        blockers.append("restored_integrity_check_not_ok")
    if not checksums_match:
        blockers.append("backup_restore_checksum_mismatch")
    if not reviewer_approved:
        blockers.append("backup_restore_reviewer_approval_missing")
    return tuple(blockers)


def _json_file(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise BackupRestoreValidationEvidenceError(f"{label} file does not exist.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackupRestoreValidationEvidenceError(
            f"{label} file is not valid JSON."
        ) from exc
    if not isinstance(payload, dict):
        raise BackupRestoreValidationEvidenceError(
            f"{label} file must contain a JSON object."
        )
    return payload


def _nested_value(payload: dict[str, Any], keys: tuple[str, ...]) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _nested_int(payload: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    value = _nested_value(payload, keys)
    return value if isinstance(value, int) else None


def _evidence_file(key: str, path: Path) -> BackupRestoreEvidenceFile:
    resolved_path = path.resolve()
    return BackupRestoreEvidenceFile(
        key=key,
        path=path.name,
        sha256=_sha256(resolved_path),
        size_bytes=resolved_path.stat().st_size,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
