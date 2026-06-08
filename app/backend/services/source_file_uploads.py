"""Controlled source-file upload service for calibration jobs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import hashlib
import re
import sqlite3

from app.backend.audit.events import AuditAction, AuditEvent
from app.backend.auth.permissions import Action
from app.backend.domain.entities import UploadedFile, UploadedFileKind
from app.backend.imports.valprobe_workbook import (
    ValProbeWorkbookParseError,
    parse_valprobe_temperature_workbook,
)
from app.backend.persistence.sqlite import (
    RecordNotFoundError,
    SQLiteAuditEventRepository,
    SQLiteCalibrationJobRepository,
    SQLiteParsedReadingRepository,
    SQLiteUploadedFileRepository,
)
from app.backend.services.authentication import resolve_actor_for_action


class SourceFileUploadServiceError(ValueError):
    """Raised when source-file upload inputs or storage are unsafe."""


@dataclass(frozen=True, slots=True)
class SourceFileUploadResult:
    uploaded_file: UploadedFile
    uploaded_by: str
    size_bytes: int
    upload_audit_event_id: int
    upload_audit_event: AuditEvent
    parser_status: str
    reading_count: int
    warning_count: int
    warnings: tuple[str, ...]
    parser_audit_event_id: int | None = None
    parser_audit_event: AuditEvent | None = None


def upload_source_file_for_session(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    job_id: str,
    file_id: str,
    original_filename: str,
    file_kind: UploadedFileKind,
    content_bytes: bytes,
    artifact_directory: Path,
    software_version: str,
    timestamp: datetime,
    parser_version: str | None = None,
) -> SourceFileUploadResult:
    """Store raw uploaded bytes and parse known calibration workbook files."""
    actor = resolve_actor_for_action(
        connection=connection,
        session_id=session_id,
        action=Action.UPLOAD_IMPORT_FILE,
        timestamp=timestamp,
    )
    _require_text(job_id, "Calibration job id")
    _require_text(file_id, "Uploaded file id")
    _require_text(original_filename, "Original filename")
    _require_text(software_version, "Software version")
    _require_timezone_aware(timestamp, "Upload timestamp")
    if not isinstance(file_kind, UploadedFileKind):
        raise SourceFileUploadServiceError("File kind is invalid.")
    if len(content_bytes) == 0:
        raise SourceFileUploadServiceError("Uploaded file content is required.")

    try:
        SQLiteCalibrationJobRepository(connection).get(job_id)
    except RecordNotFoundError as exc:
        raise SourceFileUploadServiceError("Calibration job was not found.") from exc

    storage = _write_uploaded_bytes(
        artifact_directory=artifact_directory,
        job_id=job_id,
        file_id=file_id,
        original_filename=original_filename,
        content_bytes=content_bytes,
    )
    checksum = hashlib.sha256(content_bytes).hexdigest()
    effective_parser_version = _parser_version_for_kind(
        file_kind=file_kind,
        parser_version=parser_version,
    )
    uploaded_file = UploadedFile(
        id=file_id,
        job_id=job_id,
        original_filename=original_filename,
        checksum_sha256=checksum,
        file_kind=file_kind,
        storage_uri=storage.storage_uri,
        parser_version=effective_parser_version,
        uploaded_at=timestamp,
    )

    try:
        with connection:
            uploaded_file_repository = SQLiteUploadedFileRepository(
                connection,
                autocommit=False,
            )
            reading_repository = SQLiteParsedReadingRepository(
                connection,
                autocommit=False,
            )
            audit_repository = SQLiteAuditEventRepository(
                connection,
                autocommit=False,
            )

            uploaded_file_repository.add(uploaded_file)
            upload_event = AuditEvent(
                entity_type="uploaded_file",
                entity_id=uploaded_file.id,
                action=AuditAction.FILE_UPLOADED,
                user_id=actor.user_id,
                timestamp=timestamp,
                new_value={
                    "checksum_sha256": uploaded_file.checksum_sha256,
                    "file_kind": uploaded_file.file_kind.value,
                    "original_filename": uploaded_file.original_filename,
                    "size_bytes": len(content_bytes),
                    "storage_uri": uploaded_file.storage_uri,
                },
                software_version=software_version,
            )
            upload_event_id = audit_repository.append(upload_event)

            parser_status = "not_run"
            reading_count = 0
            warnings: tuple[str, ...] = ()
            parser_event_id: int | None = None
            parser_event: AuditEvent | None = None
            if file_kind is UploadedFileKind.CALIBRATION_XLSX:
                assert effective_parser_version is not None
                try:
                    parsed = parse_valprobe_temperature_workbook(
                        storage.path,
                        uploaded_file_id=uploaded_file.id,
                        parser_version=effective_parser_version,
                    )
                    reading_repository.add_many(parsed.readings)
                    parser_status = "parsed"
                    reading_count = len(parsed.readings)
                    warnings = parsed.warnings
                except ValProbeWorkbookParseError as exc:
                    parser_status = "failed"
                    warnings = (str(exc),)
                parser_event = _parser_audit_event(
                    uploaded_file=uploaded_file,
                    parser_status=parser_status,
                    parser_version=effective_parser_version,
                    reading_count=reading_count,
                    warning_count=len(warnings),
                    user_id=actor.user_id,
                    software_version=software_version,
                    timestamp=timestamp,
                )
                parser_event_id = audit_repository.append(parser_event)
            elif file_kind is UploadedFileKind.VERIFICATION_PDF:
                parser_status = "stored_only"
                warnings = (
                    "Verification PDF extraction is deferred; raw file evidence was stored.",
                )

    except Exception:
        _remove_uploaded_bytes(storage.path)
        raise

    return SourceFileUploadResult(
        uploaded_file=uploaded_file,
        uploaded_by=actor.user_id,
        size_bytes=len(content_bytes),
        upload_audit_event_id=upload_event_id,
        upload_audit_event=upload_event,
        parser_status=parser_status,
        reading_count=reading_count,
        warning_count=len(warnings),
        warnings=warnings,
        parser_audit_event_id=parser_event_id,
        parser_audit_event=parser_event,
    )


@dataclass(frozen=True, slots=True)
class _StoredUpload:
    path: Path
    storage_uri: str


def _write_uploaded_bytes(
    *,
    artifact_directory: Path,
    job_id: str,
    file_id: str,
    original_filename: str,
    content_bytes: bytes,
) -> _StoredUpload:
    if original_filename != Path(original_filename).name:
        raise SourceFileUploadServiceError(
            "Original filename must not contain path components."
        )
    resolved_base = artifact_directory.resolve()
    safe_job_id = _safe_storage_segment(job_id)
    safe_filename = _safe_filename(original_filename)
    upload_dir = resolved_base / "uploads" / safe_job_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    target_path = (upload_dir / f"{_safe_storage_segment(file_id)}-{safe_filename}").resolve()
    if resolved_base not in target_path.parents:
        raise SourceFileUploadServiceError(
            "Uploaded file path must stay within artifact storage."
        )
    try:
        with target_path.open("xb") as handle:
            handle.write(content_bytes)
    except FileExistsError as exc:
        raise SourceFileUploadServiceError("Uploaded file already exists.") from exc
    except OSError as exc:
        raise SourceFileUploadServiceError("Uploaded file could not be stored.") from exc
    relative = target_path.relative_to(resolved_base).as_posix()
    return _StoredUpload(
        path=target_path,
        storage_uri=f"controlled-local://{relative}",
    )


def _parser_version_for_kind(
    *,
    file_kind: UploadedFileKind,
    parser_version: str | None,
) -> str | None:
    if parser_version is not None and parser_version.strip() == "":
        raise SourceFileUploadServiceError("Parser version cannot be blank.")
    if file_kind is UploadedFileKind.CALIBRATION_XLSX:
        return parser_version or "valprobe-xlsx-parser-v1"
    return parser_version


def _parser_audit_event(
    *,
    uploaded_file: UploadedFile,
    parser_status: str,
    parser_version: str,
    reading_count: int,
    warning_count: int,
    user_id: str,
    software_version: str,
    timestamp: datetime,
) -> AuditEvent:
    return AuditEvent(
        entity_type="uploaded_file",
        entity_id=uploaded_file.id,
        action=AuditAction.PARSER_RESULT_RECORDED,
        user_id=user_id,
        timestamp=timestamp,
        new_value={
            "parser_status": parser_status,
            "parser_version": parser_version,
            "reading_count": reading_count,
            "warning_count": warning_count,
        },
        software_version=software_version,
    )


def _safe_filename(value: str) -> str:
    candidate = re.sub(r"[^A-Za-z0-9._ -]", "_", value).strip()
    if candidate in {"", ".", ".."}:
        raise SourceFileUploadServiceError("Original filename is unsafe.")
    return candidate


def _safe_storage_segment(value: str) -> str:
    candidate = re.sub(r"[^A-Za-z0-9._-]", "_", value).strip("._")
    if candidate == "":
        raise SourceFileUploadServiceError("Storage segment is unsafe.")
    return candidate


def _remove_uploaded_bytes(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise SourceFileUploadServiceError(f"{field_name} is required.")


def _require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise SourceFileUploadServiceError(f"{field_name} must be timezone-aware.")

