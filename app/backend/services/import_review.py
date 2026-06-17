"""Import review service for uploaded calibration source files."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import sqlite3

from app.backend.audit.events import AuditAction
from app.backend.auth.permissions import Action
from app.backend.domain.entities import UploadedFile, UploadedFileKind
from app.backend.persistence.sqlite import (
    RecordNotFoundError,
    SQLiteAuditEventRepository,
    SQLiteCalibrationJobRepository,
    SQLiteParsedReadingRepository,
    SQLiteUploadedFileRepository,
)
from app.backend.services.authentication import resolve_actor_for_action


class ImportReviewServiceError(ValueError):
    """Raised when import review cannot be produced safely."""


@dataclass(frozen=True, slots=True)
class UploadedFileReview:
    uploaded_file: UploadedFile
    parser_status: str
    reading_count: int
    warning_count: int
    uploaded_by: str
    size_bytes: int | None


@dataclass(frozen=True, slots=True)
class ImportReview:
    job_id: str
    reviewed_by: str
    reviewed_at: datetime
    files: tuple[UploadedFileReview, ...]


def build_import_review_for_session(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    job_id: str,
    timestamp: datetime,
) -> ImportReview:
    """Return uploaded-file and parser evidence for an authorized session."""
    actor = resolve_actor_for_action(
        connection=connection,
        session_id=session_id,
        action=Action.UPLOAD_IMPORT_FILE,
        timestamp=timestamp,
    )
    try:
        SQLiteCalibrationJobRepository(connection).get(job_id)
    except RecordNotFoundError as exc:
        raise ImportReviewServiceError("Calibration job was not found.") from exc

    uploaded_file_repository = SQLiteUploadedFileRepository(connection)
    parsed_reading_repository = SQLiteParsedReadingRepository(connection)
    audit_repository = SQLiteAuditEventRepository(connection)

    reviews: list[UploadedFileReview] = []
    for uploaded_file in uploaded_file_repository.list_for_job(job_id):
        readings = parsed_reading_repository.list_for_uploaded_file(uploaded_file.id)
        events = audit_repository.list_for_entity("uploaded_file", uploaded_file.id)
        upload_event = next(
            (event for event in events if event.action is AuditAction.FILE_UPLOADED),
            None,
        )
        parser_event = next(
            (
                event
                for event in reversed(events)
                if event.action is AuditAction.PARSER_RESULT_RECORDED
            ),
            None,
        )
        parser_status = _parser_status(
            uploaded_file=uploaded_file,
            parser_event=parser_event,
        )
        reading_count = len(readings)
        if reading_count == 0:
            reading_count = _parser_reading_count(parser_event=parser_event)
        warning_count = _parser_warning_count(parser_event=parser_event)
        reviews.append(
            UploadedFileReview(
                uploaded_file=uploaded_file,
                parser_status=parser_status,
                reading_count=reading_count,
                warning_count=warning_count,
                uploaded_by=upload_event.user_id if upload_event is not None else "",
                size_bytes=_upload_size(upload_event=upload_event),
            )
        )

    return ImportReview(
        job_id=job_id,
        reviewed_by=actor.user_id,
        reviewed_at=timestamp,
        files=tuple(reviews),
    )


def _parser_status(
    *,
    uploaded_file: UploadedFile,
    parser_event,
) -> str:
    if parser_event is not None and parser_event.new_value is not None:
        raw_status = parser_event.new_value.get("parser_status")
        if isinstance(raw_status, str) and raw_status.strip() != "":
            return raw_status
        return "parsed"
    if uploaded_file.file_kind is UploadedFileKind.VERIFICATION_PDF:
        return "stored_only"
    return "not_run"


def _parser_warning_count(*, parser_event) -> int:
    if parser_event is None or parser_event.new_value is None:
        return 0
    raw_count = parser_event.new_value.get("warning_count", 0)
    return int(raw_count)


def _parser_reading_count(*, parser_event) -> int:
    if parser_event is None or parser_event.new_value is None:
        return 0
    raw_count = parser_event.new_value.get("reading_count", 0)
    return int(raw_count)


def _upload_size(*, upload_event) -> int | None:
    if upload_event is None or upload_event.new_value is None:
        return None
    raw_size = upload_event.new_value.get("size_bytes")
    if raw_size is None:
        return None
    return int(raw_size)
