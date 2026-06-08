"""Controlled review and approval workflow transition services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import sqlite3

from app.backend.audit.events import AuditEvent
from app.backend.auth.permissions import Action
from app.backend.domain.entities import CalibrationJob
from app.backend.domain.workflow import WorkflowState
from app.backend.persistence.sqlite import (
    SQLiteAuditEventRepository,
    SQLiteCalibrationJobRepository,
)
from app.backend.services.authentication import resolve_actor_for_action
from app.backend.services.workflow import (
    WorkflowServiceError,
    transition_calibration_job,
)


class ReviewWorkflowServiceError(ValueError):
    """Raised when a review workflow transition cannot be recorded."""


@dataclass(frozen=True, slots=True)
class ReviewWorkflowTransition:
    job: CalibrationJob
    audit_event_id: int
    audit_event: AuditEvent


def submit_technical_review_for_session(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    job_id: str,
    software_version: str,
    timestamp: datetime,
) -> ReviewWorkflowTransition:
    """Move a calculated job into technical review."""
    return _review_transition_for_session(
        connection=connection,
        session_id=session_id,
        job_id=job_id,
        action=Action.SUBMIT_TECHNICAL_REVIEW,
        expected_state=WorkflowState.CALCULATED,
        target_state=WorkflowState.TECHNICAL_REVIEW,
        software_version=software_version,
        timestamp=timestamp,
    )


def approve_technical_review_for_session(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    job_id: str,
    software_version: str,
    timestamp: datetime,
) -> ReviewWorkflowTransition:
    """Move a technically reviewed job into QA review."""
    return _review_transition_for_session(
        connection=connection,
        session_id=session_id,
        job_id=job_id,
        action=Action.APPROVE_TECHNICAL_REVIEW,
        expected_state=WorkflowState.TECHNICAL_REVIEW,
        target_state=WorkflowState.QA_REVIEW,
        software_version=software_version,
        timestamp=timestamp,
    )


def approve_qa_release_for_session(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    job_id: str,
    software_version: str,
    timestamp: datetime,
) -> ReviewWorkflowTransition:
    """Move a QA-reviewed job into approved state."""
    return _review_transition_for_session(
        connection=connection,
        session_id=session_id,
        job_id=job_id,
        action=Action.APPROVE_QA_RELEASE,
        expected_state=WorkflowState.QA_REVIEW,
        target_state=WorkflowState.APPROVED,
        software_version=software_version,
        timestamp=timestamp,
    )


def _review_transition_for_session(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    job_id: str,
    action: Action,
    expected_state: WorkflowState,
    target_state: WorkflowState,
    software_version: str,
    timestamp: datetime,
) -> ReviewWorkflowTransition:
    actor = resolve_actor_for_action(
        connection=connection,
        session_id=session_id,
        action=action,
        timestamp=timestamp,
    )
    _require_text(job_id, "Job id")
    _require_text(software_version, "Software version")
    _require_timezone_aware(timestamp, "Review transition timestamp")

    with connection:
        job_repository = SQLiteCalibrationJobRepository(connection, autocommit=False)
        audit_repository = SQLiteAuditEventRepository(connection, autocommit=False)
        job = job_repository.get(job_id)
        if job.state is not expected_state:
            raise ReviewWorkflowServiceError(
                f"Review transition requires {expected_state.value} state."
            )
        try:
            transition = transition_calibration_job(
                job_id=job.id,
                current=job.state,
                target=target_state,
                user_id=actor.user_id,
                software_version=software_version,
                timestamp=timestamp,
            )
        except WorkflowServiceError as exc:
            raise ReviewWorkflowServiceError(str(exc)) from exc
        updated_job = job_repository.update_state(
            job_id=job.id,
            expected_state=job.state,
            new_state=transition.state,
        )
        audit_event_id = audit_repository.append(transition.audit_event)

    return ReviewWorkflowTransition(
        job=updated_job,
        audit_event_id=audit_event_id,
        audit_event=transition.audit_event,
    )


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise ReviewWorkflowServiceError(f"{field_name} is required.")


def _require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ReviewWorkflowServiceError(f"{field_name} must be timezone-aware.")
