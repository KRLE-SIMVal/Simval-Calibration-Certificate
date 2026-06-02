"""Transactional persistence orchestration for workflow changes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import sqlite3

from app.backend.audit.events import AuditEvent
from app.backend.domain.entities import CalibrationJob
from app.backend.domain.workflow import WorkflowState
from app.backend.persistence.sqlite import (
    SQLiteAuditEventRepository,
    SQLiteCalibrationJobRepository,
)
from app.backend.services.workflow import transition_calibration_job


@dataclass(frozen=True, slots=True)
class PersistedWorkflowTransition:
    job: CalibrationJob
    audit_event_id: int
    audit_event: AuditEvent


def persist_workflow_transition(
    *,
    connection: sqlite3.Connection,
    job_id: str,
    target: WorkflowState,
    user_id: str,
    software_version: str,
    timestamp: datetime,
    reason: str | None = None,
) -> PersistedWorkflowTransition:
    """Persist a workflow state change and its audit event atomically."""
    with connection:
        job_repository = SQLiteCalibrationJobRepository(connection, autocommit=False)
        audit_repository = SQLiteAuditEventRepository(connection, autocommit=False)
        current_job = job_repository.get(job_id)
        transition = transition_calibration_job(
            job_id=current_job.id,
            current=current_job.state,
            target=target,
            user_id=user_id,
            software_version=software_version,
            timestamp=timestamp,
            reason=reason,
        )
        updated_job = job_repository.update_state(
            job_id=current_job.id,
            expected_state=current_job.state,
            new_state=transition.state,
        )
        audit_event_id = audit_repository.append(transition.audit_event)
        return PersistedWorkflowTransition(
            job=updated_job,
            audit_event_id=audit_event_id,
            audit_event=transition.audit_event,
        )
