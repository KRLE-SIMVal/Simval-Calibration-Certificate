"""Import orchestration services for calibration source files."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sqlite3

from app.backend.audit.events import AuditAction, AuditEvent
from app.backend.domain.entities import UploadedFile, UploadedFileKind
from app.backend.imports.valprobe_workbook import (
    ParsedValProbeWorkbook,
    parse_valprobe_temperature_workbook,
)
from app.backend.persistence.sqlite import (
    SQLiteAuditEventRepository,
    SQLiteParsedReadingRepository,
    SQLiteUploadedFileRepository,
)


class ImportServiceError(ValueError):
    """Raised when import orchestration inputs are incomplete or inconsistent."""


@dataclass(frozen=True, slots=True)
class ValProbeImportResult:
    uploaded_file: UploadedFile
    parsed_workbook: ParsedValProbeWorkbook
    audit_event_id: int
    audit_event: AuditEvent

    @property
    def reading_count(self) -> int:
        return len(self.parsed_workbook.readings)


def record_valprobe_temperature_import(
    *,
    connection: sqlite3.Connection,
    workbook_path: Path,
    uploaded_file: UploadedFile,
    user_id: str,
    software_version: str,
    timestamp: datetime,
) -> ValProbeImportResult:
    """Parse and persist a ValProbe temperature workbook with audit evidence."""
    _validate_import_inputs(
        uploaded_file=uploaded_file,
        user_id=user_id,
        software_version=software_version,
    )
    assert uploaded_file.parser_version is not None
    parsed = parse_valprobe_temperature_workbook(
        workbook_path,
        uploaded_file_id=uploaded_file.id,
        parser_version=uploaded_file.parser_version,
    )
    audit_event = AuditEvent(
        entity_type="uploaded_file",
        entity_id=uploaded_file.id,
        action=AuditAction.PARSER_RESULT_RECORDED,
        user_id=user_id,
        timestamp=timestamp,
        new_value={
            "parser_version": parsed.parser_version,
            "reading_count": len(parsed.readings),
            "warning_count": len(parsed.warnings),
        },
        software_version=software_version,
    )
    with connection:
        uploaded_file_repository = SQLiteUploadedFileRepository(
            connection,
            autocommit=False,
        )
        reading_repository = SQLiteParsedReadingRepository(
            connection,
            autocommit=False,
        )
        audit_repository = SQLiteAuditEventRepository(connection, autocommit=False)
        uploaded_file_repository.add(uploaded_file)
        reading_repository.add_many(parsed.readings)
        audit_event_id = audit_repository.append(audit_event)
    return ValProbeImportResult(
        uploaded_file=uploaded_file,
        parsed_workbook=parsed,
        audit_event_id=audit_event_id,
        audit_event=audit_event,
    )


def _validate_import_inputs(
    *,
    uploaded_file: UploadedFile,
    user_id: str,
    software_version: str,
) -> None:
    if uploaded_file.file_kind is not UploadedFileKind.CALIBRATION_XLSX:
        raise ImportServiceError("ValProbe import requires a calibration XLSX file.")
    if uploaded_file.parser_version is None or uploaded_file.parser_version.strip() == "":
        raise ImportServiceError("ValProbe import requires a parser version.")
    if user_id.strip() == "":
        raise ImportServiceError("Import user_id is required.")
    if software_version.strip() == "":
        raise ImportServiceError("Import software_version is required.")
