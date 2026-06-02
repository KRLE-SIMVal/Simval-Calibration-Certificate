"""Import orchestration services for calibration source files."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sqlite3
from typing import Sequence

from app.backend.audit.events import AuditAction, AuditEvent
from app.backend.domain.entities import UploadedFile, UploadedFileKind
from app.backend.imports.temperature_alignment import (
    TemperatureAlignmentError,
    TemperatureAlignmentResult,
    link_logger_readings_to_irtd,
)
from app.backend.imports.valprobe_workbook import (
    ParsedValProbeWorkbook,
    parse_valprobe_temperature_workbook,
)
from app.backend.imports.verification_pdf_contract import (
    VerificationIrtdParseResult,
    parse_irtd_reference_table,
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


@dataclass(frozen=True, slots=True)
class LinkedValProbeImportResult:
    calibration_file: UploadedFile
    verification_file: UploadedFile
    parsed_workbook: ParsedValProbeWorkbook
    parsed_verification: VerificationIrtdParseResult
    alignment: TemperatureAlignmentResult
    audit_event_ids: tuple[int, ...]
    audit_events: tuple[AuditEvent, ...]

    @property
    def logger_reading_count(self) -> int:
        return len(self.parsed_workbook.readings)

    @property
    def irtd_reading_count(self) -> int:
        return len(self.parsed_verification.readings)

    @property
    def linked_reading_count(self) -> int:
        return len(self.alignment.linked_readings)

    @property
    def warnings(self) -> tuple[str, ...]:
        return (
            self.parsed_workbook.warnings
            + self.parsed_verification.warnings
            + self.alignment.warnings
        )


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


def record_valprobe_temperature_import_with_irtd_references(
    *,
    connection: sqlite3.Connection,
    workbook_path: Path,
    calibration_file: UploadedFile,
    verification_file: UploadedFile,
    verification_rows: Sequence[Sequence[str]],
    user_id: str,
    software_version: str,
    timestamp: datetime,
) -> LinkedValProbeImportResult:
    """Parse, persist, and align a ValProbe XLSX with extracted IRTD rows."""
    _validate_import_inputs(
        uploaded_file=calibration_file,
        user_id=user_id,
        software_version=software_version,
    )
    _validate_verification_import_inputs(
        verification_file=verification_file,
        calibration_file=calibration_file,
    )
    assert calibration_file.parser_version is not None
    assert verification_file.parser_version is not None
    parsed_workbook = parse_valprobe_temperature_workbook(
        workbook_path,
        uploaded_file_id=calibration_file.id,
        parser_version=calibration_file.parser_version,
    )
    parsed_verification = parse_irtd_reference_table(
        rows=verification_rows,
        uploaded_file_id=verification_file.id,
    )
    try:
        alignment = link_logger_readings_to_irtd(
            logger_readings=parsed_workbook.readings,
            irtd_readings=parsed_verification.readings,
        )
    except TemperatureAlignmentError as error:
        raise ImportServiceError(
            "Linked ValProbe import could not align IRTD references."
        ) from error

    audit_events = (
        _parser_result_audit_event(
            uploaded_file_id=calibration_file.id,
            parser_version=parsed_workbook.parser_version,
            reading_count=len(parsed_workbook.readings),
            warning_count=len(parsed_workbook.warnings),
            user_id=user_id,
            software_version=software_version,
            timestamp=timestamp,
        ),
        _parser_result_audit_event(
            uploaded_file_id=verification_file.id,
            parser_version=verification_file.parser_version,
            reading_count=len(parsed_verification.readings),
            warning_count=len(parsed_verification.warnings),
            user_id=user_id,
            software_version=software_version,
            timestamp=timestamp,
            extra_new_value={
                "irtd_column_name": parsed_verification.irtd_column_name,
            },
        ),
        AuditEvent(
            entity_type="calibration_job",
            entity_id=calibration_file.job_id,
            action=AuditAction.IMPORT_ALIGNMENT_RECORDED,
            user_id=user_id,
            timestamp=timestamp,
            new_value={
                "calibration_uploaded_file_id": calibration_file.id,
                "verification_uploaded_file_id": verification_file.id,
                "linked_reading_count": len(alignment.linked_readings),
                "alignment_warning_count": len(alignment.warnings),
            },
            software_version=software_version,
        ),
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
        uploaded_file_repository.add(calibration_file)
        uploaded_file_repository.add(verification_file)
        reading_repository.add_many(
            parsed_workbook.readings + parsed_verification.readings
        )
        audit_event_ids = tuple(
            audit_repository.append(audit_event) for audit_event in audit_events
        )

    return LinkedValProbeImportResult(
        calibration_file=calibration_file,
        verification_file=verification_file,
        parsed_workbook=parsed_workbook,
        parsed_verification=parsed_verification,
        alignment=alignment,
        audit_event_ids=audit_event_ids,
        audit_events=audit_events,
    )


def _validate_import_inputs(
    *,
    uploaded_file: UploadedFile,
    user_id: str,
    software_version: str,
) -> None:
    if uploaded_file.file_kind is not UploadedFileKind.CALIBRATION_XLSX:
        raise ImportServiceError("ValProbe import requires a calibration XLSX file.")
    if (
        uploaded_file.parser_version is None
        or uploaded_file.parser_version.strip() == ""
    ):
        raise ImportServiceError("ValProbe import requires a parser version.")
    if user_id.strip() == "":
        raise ImportServiceError("Import user_id is required.")
    if software_version.strip() == "":
        raise ImportServiceError("Import software_version is required.")


def _validate_verification_import_inputs(
    *,
    verification_file: UploadedFile,
    calibration_file: UploadedFile,
) -> None:
    if verification_file.file_kind is not UploadedFileKind.VERIFICATION_PDF:
        raise ImportServiceError(
            "Linked ValProbe import requires a verification PDF file."
        )
    if (
        verification_file.parser_version is None
        or verification_file.parser_version.strip() == ""
    ):
        raise ImportServiceError(
            "Linked ValProbe import requires a verification parser version."
        )
    if verification_file.job_id != calibration_file.job_id:
        raise ImportServiceError(
            "Linked ValProbe import requires files from the same calibration job."
        )


def _parser_result_audit_event(
    *,
    uploaded_file_id: str,
    parser_version: str,
    reading_count: int,
    warning_count: int,
    user_id: str,
    software_version: str,
    timestamp: datetime,
    extra_new_value: dict[str, str] | None = None,
) -> AuditEvent:
    new_value: dict[str, str | int] = {
        "parser_version": parser_version,
        "reading_count": reading_count,
        "warning_count": warning_count,
    }
    if extra_new_value is not None:
        new_value.update(extra_new_value)
    return AuditEvent(
        entity_type="uploaded_file",
        entity_id=uploaded_file_id,
        action=AuditAction.PARSER_RESULT_RECORDED,
        user_id=user_id,
        timestamp=timestamp,
        new_value=new_value,
        software_version=software_version,
    )
