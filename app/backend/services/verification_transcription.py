"""Manual verification IRTD transcription and logger alignment services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import sqlite3
from typing import Sequence

from app.backend.audit.events import AuditAction, AuditEvent
from app.backend.auth.permissions import Action
from app.backend.domain.entities import UploadedFileKind
from app.backend.domain.workflow import WorkflowState
from app.backend.imports.temperature_alignment import (
    TemperatureAlignmentError,
    TemperatureAlignmentResult,
    link_logger_readings_to_irtd,
)
from app.backend.imports.verification_pdf_contract import (
    VerificationIrtdParseResult,
    VerificationPdfParseError,
    parse_irtd_reference_table,
)
from app.backend.persistence.sqlite import (
    RecordNotFoundError,
    SQLiteAuditEventRepository,
    SQLiteCalibrationJobRepository,
    SQLiteLinkedTemperatureReadingRepository,
    SQLiteParsedReadingRepository,
    SQLiteUploadedFileRepository,
)
from app.backend.services.authentication import resolve_actor_for_action


class VerificationTranscriptionServiceError(ValueError):
    """Raised when manual verification data cannot be controlled."""


@dataclass(frozen=True, slots=True)
class ManualIrtdAlignment:
    job_id: str
    calibration_uploaded_file_id: str
    verification_uploaded_file_id: str
    parsed_verification: VerificationIrtdParseResult
    alignment: TemperatureAlignmentResult
    manual_irtd_audit_event_id: int
    manual_irtd_audit_event: AuditEvent
    alignment_audit_event_id: int
    alignment_audit_event: AuditEvent

    @property
    def irtd_reading_count(self) -> int:
        return len(self.parsed_verification.readings)

    @property
    def linked_reading_count(self) -> int:
        return len(self.alignment.linked_readings)

    @property
    def warnings(self) -> tuple[str, ...]:
        return self.parsed_verification.warnings + self.alignment.warnings


def record_manual_irtd_rows_for_session(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    job_id: str,
    calibration_uploaded_file_id: str,
    verification_uploaded_file_id: str,
    rows: Sequence[Sequence[str]],
    unit: str,
    software_version: str,
    timestamp: datetime,
) -> ManualIrtdAlignment:
    """Parse manually transcribed IRTD rows and align them to logger readings."""
    actor = resolve_actor_for_action(
        connection=connection,
        session_id=session_id,
        action=Action.ENTER_MANUAL_READINGS,
        timestamp=timestamp,
    )
    _require_text(job_id, "Job id")
    _require_text(calibration_uploaded_file_id, "Calibration uploaded file id")
    _require_text(verification_uploaded_file_id, "Verification uploaded file id")
    _require_text(unit, "Temperature unit")
    _require_text(software_version, "Software version")
    _require_timezone_aware(timestamp, "Manual IRTD transcription timestamp")

    with connection:
        job_repository = SQLiteCalibrationJobRepository(connection, autocommit=False)
        uploaded_file_repository = SQLiteUploadedFileRepository(
            connection,
            autocommit=False,
        )
        parsed_reading_repository = SQLiteParsedReadingRepository(
            connection,
            autocommit=False,
        )
        linked_reading_repository = SQLiteLinkedTemperatureReadingRepository(
            connection,
            autocommit=False,
        )
        audit_repository = SQLiteAuditEventRepository(connection, autocommit=False)

        job = job_repository.get(job_id)
        if job.state is not WorkflowState.DATA_ENTERED:
            raise VerificationTranscriptionServiceError(
                "Manual IRTD transcription requires data_entered state."
            )
        try:
            calibration_file = uploaded_file_repository.get(calibration_uploaded_file_id)
            verification_file = uploaded_file_repository.get(verification_uploaded_file_id)
        except RecordNotFoundError as exc:
            raise VerificationTranscriptionServiceError(
                "Calibration and verification uploaded files are required."
            ) from exc
        if calibration_file.job_id != job_id or verification_file.job_id != job_id:
            raise VerificationTranscriptionServiceError(
                "Calibration and verification files must belong to the selected job."
            )
        if calibration_file.file_kind is not UploadedFileKind.CALIBRATION_XLSX:
            raise VerificationTranscriptionServiceError(
                "Manual IRTD alignment requires a calibration XLSX file."
            )
        if verification_file.file_kind is not UploadedFileKind.VERIFICATION_PDF:
            raise VerificationTranscriptionServiceError(
                "Manual IRTD transcription requires a verification PDF file."
            )

        logger_readings = parsed_reading_repository.list_for_uploaded_file(
            calibration_file.id,
        )
        if len(logger_readings) == 0:
            raise VerificationTranscriptionServiceError(
                "Manual IRTD alignment requires parsed calibration readings."
            )
        if parsed_reading_repository.list_for_uploaded_file(verification_file.id):
            raise VerificationTranscriptionServiceError(
                "Verification IRTD readings already exist for this file."
            )
        if linked_reading_repository.list_for_job(job_id):
            raise VerificationTranscriptionServiceError(
                "Linked temperature readings already exist for this job."
            )

        try:
            parsed_verification = parse_irtd_reference_table(
                rows=rows,
                uploaded_file_id=verification_file.id,
                unit=unit,
            )
        except VerificationPdfParseError as exc:
            raise VerificationTranscriptionServiceError(str(exc)) from exc
        if len(parsed_verification.readings) == 0:
            raise VerificationTranscriptionServiceError(
                "Manual IRTD transcription produced no valid reference readings."
            )
        try:
            alignment = link_logger_readings_to_irtd(
                logger_readings=logger_readings,
                irtd_readings=parsed_verification.readings,
            )
        except TemperatureAlignmentError as exc:
            raise VerificationTranscriptionServiceError(str(exc)) from exc
        if len(alignment.linked_readings) == 0:
            raise VerificationTranscriptionServiceError(
                "Manual IRTD transcription produced no linked logger readings."
            )

        parsed_reading_repository.add_many(parsed_verification.readings)
        linked_reading_repository.add_many(
            job_id=job_id,
            linked_readings=alignment.linked_readings,
        )

        manual_irtd_audit_event = AuditEvent(
            entity_type="uploaded_file",
            entity_id=verification_file.id,
            action=AuditAction.MANUAL_IRTD_TABLE_RECORDED,
            user_id=actor.user_id,
            timestamp=timestamp,
            new_value={
                "source": "manual_transcription_from_verification_pdf",
                "row_count": len(rows),
                "irtd_column_name": parsed_verification.irtd_column_name,
                "irtd_reading_count": len(parsed_verification.readings),
                "warning_count": len(parsed_verification.warnings),
                "unit": unit,
            },
            software_version=software_version,
        )
        manual_irtd_audit_event_id = audit_repository.append(manual_irtd_audit_event)

        alignment_audit_event = AuditEvent(
            entity_type="calibration_job",
            entity_id=job_id,
            action=AuditAction.IMPORT_ALIGNMENT_RECORDED,
            user_id=actor.user_id,
            timestamp=timestamp,
            new_value={
                "source": "manual_irtd_table",
                "calibration_uploaded_file_id": calibration_file.id,
                "verification_uploaded_file_id": verification_file.id,
                "irtd_reading_count": len(parsed_verification.readings),
                "linked_reading_count": len(alignment.linked_readings),
                "alignment_warning_count": len(alignment.warnings),
            },
            software_version=software_version,
        )
        alignment_audit_event_id = audit_repository.append(alignment_audit_event)

    return ManualIrtdAlignment(
        job_id=job_id,
        calibration_uploaded_file_id=calibration_file.id,
        verification_uploaded_file_id=verification_file.id,
        parsed_verification=parsed_verification,
        alignment=alignment,
        manual_irtd_audit_event_id=manual_irtd_audit_event_id,
        manual_irtd_audit_event=manual_irtd_audit_event,
        alignment_audit_event_id=alignment_audit_event_id,
        alignment_audit_event=alignment_audit_event,
    )


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise VerificationTranscriptionServiceError(f"{field_name} is required.")


def _require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise VerificationTranscriptionServiceError(
            f"{field_name} must be timezone-aware."
        )
