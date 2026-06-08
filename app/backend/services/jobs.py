"""Calibration job creation service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import sqlite3

from app.backend.audit.events import AuditAction, AuditEvent
from app.backend.auth.permissions import Action
from app.backend.domain.entities import (
    CalibrationJob,
    Client,
    Discipline,
    MeasurementMode,
)
from app.backend.persistence.sqlite import (
    SQLiteAuditEventRepository,
    SQLiteCalibrationJobRepository,
)
from app.backend.services.authentication import resolve_actor_for_action


class CalibrationJobServiceError(ValueError):
    """Raised when calibration job creation inputs are incomplete."""


@dataclass(frozen=True, slots=True)
class CalibrationJobCreation:
    job: CalibrationJob
    audit_event_id: int
    audit_event: AuditEvent


def create_calibration_job_for_session(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    job_id: str,
    client_name: str,
    client_address: str,
    discipline: Discipline,
    measurement_mode: MeasurementMode,
    method: str,
    software_version: str,
    timestamp: datetime,
) -> CalibrationJobCreation:
    """Create a draft calibration job with authenticated user evidence."""
    actor = resolve_actor_for_action(
        connection=connection,
        session_id=session_id,
        action=Action.CREATE_CALIBRATION_JOB,
        timestamp=timestamp,
    )
    _require_text(software_version, "Software version")

    job = CalibrationJob(
        id=job_id,
        client=Client(name=client_name, address=client_address),
        discipline=discipline,
        measurement_mode=measurement_mode,
        method=method,
        created_by=actor.user_id,
        created_at=timestamp,
    )
    audit_event = AuditEvent(
        entity_type="calibration_job",
        entity_id=job.id,
        action=AuditAction.JOB_CREATED,
        user_id=actor.user_id,
        timestamp=timestamp,
        new_value={
            "client_name": job.client.name,
            "discipline": job.discipline.value,
            "measurement_mode": job.measurement_mode.value,
            "method": job.method,
            "state": job.state.value,
        },
        software_version=software_version,
    )
    with connection:
        job_repository = SQLiteCalibrationJobRepository(connection, autocommit=False)
        audit_repository = SQLiteAuditEventRepository(connection, autocommit=False)
        job_repository.add(job)
        audit_event_id = audit_repository.append(audit_event)
    return CalibrationJobCreation(
        job=job,
        audit_event_id=audit_event_id,
        audit_event=audit_event,
    )


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise CalibrationJobServiceError(f"{field_name} is required.")

