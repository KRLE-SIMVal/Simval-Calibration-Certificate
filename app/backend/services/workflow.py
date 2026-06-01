"""Audit-aware workflow transition service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.backend.audit.events import AuditAction, AuditEvent
from app.backend.domain.workflow import WorkflowState, require_transition


class WorkflowServiceError(ValueError):
    """Raised when workflow orchestration inputs are incomplete."""


@dataclass(frozen=True, slots=True)
class WorkflowTransitionResult:
    state: WorkflowState
    audit_event: AuditEvent


def transition_calibration_job(
    *,
    job_id: str,
    current: WorkflowState,
    target: WorkflowState,
    user_id: str,
    software_version: str,
    timestamp: datetime,
    reason: str | None = None,
) -> WorkflowTransitionResult:
    """Transition a calibration job and return the required audit evidence."""
    _require_text(job_id, "Job id")
    _require_text(user_id, "User id")
    _require_text(software_version, "Software version")
    _require_instance(current, WorkflowState, "Current workflow state")
    _require_instance(target, WorkflowState, "Target workflow state")
    _require_timezone_aware(timestamp, "Workflow transition timestamp")
    if target in {WorkflowState.VOIDED, WorkflowState.REVISED}:
        if reason is None or reason.strip() == "":
            raise WorkflowServiceError("Void and revision transitions require a reason.")

    new_state = require_transition(current, target)
    audit_event = AuditEvent(
        entity_type="calibration_job",
        entity_id=job_id,
        action=AuditAction.WORKFLOW_TRANSITIONED,
        user_id=user_id,
        timestamp=timestamp,
        previous_value={"state": current.value},
        new_value={"state": new_state.value},
        reason=reason,
        software_version=software_version,
    )
    return WorkflowTransitionResult(state=new_state, audit_event=audit_event)


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise WorkflowServiceError(f"{field_name} is required.")


def _require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise WorkflowServiceError(f"{field_name} must be timezone-aware.")


def _require_instance(value: object, expected_type: type, field_name: str) -> None:
    if not isinstance(value, expected_type):
        raise WorkflowServiceError(f"{field_name} is invalid.")
