from datetime import datetime, timezone

import pytest

from app.backend.audit.events import AuditAction
from app.backend.domain.workflow import WorkflowState, WorkflowTransitionError
from app.backend.services.workflow import (
    WorkflowServiceError,
    transition_calibration_job,
)


def test_workflow_service_transitions_and_returns_audit_event():
    result = transition_calibration_job(
        job_id="job-001",
        current=WorkflowState.DRAFT,
        target=WorkflowState.METADATA_COMPLETE,
        user_id="operator-001",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 16, 0, tzinfo=timezone.utc),
    )

    assert result.state is WorkflowState.METADATA_COMPLETE
    assert result.audit_event.action is AuditAction.WORKFLOW_TRANSITIONED
    assert result.audit_event.entity_type == "calibration_job"
    assert result.audit_event.entity_id == "job-001"
    assert result.audit_event.previous_value == {"state": "draft"}
    assert result.audit_event.new_value == {"state": "metadata_complete"}
    assert result.audit_event.software_version == "app-0.1.0"


def test_workflow_service_rejects_invalid_transition_without_audit_event():
    with pytest.raises(WorkflowTransitionError):
        transition_calibration_job(
            job_id="job-001",
            current=WorkflowState.DRAFT,
            target=WorkflowState.RELEASED,
            user_id="operator-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 16, 0, tzinfo=timezone.utc),
        )


@pytest.mark.parametrize(
    "target",
    [WorkflowState.VOIDED, WorkflowState.REVISED],
)
def test_workflow_service_requires_reason_for_void_or_revision(target):
    current = (
        WorkflowState.DRAFT if target is WorkflowState.VOIDED else WorkflowState.RELEASED
    )

    with pytest.raises(WorkflowServiceError):
        transition_calibration_job(
            job_id="job-001",
            current=current,
            target=target,
            user_id="qa-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 16, 0, tzinfo=timezone.utc),
        )


def test_workflow_service_records_reason_for_void():
    result = transition_calibration_job(
        job_id="job-001",
        current=WorkflowState.DRAFT,
        target=WorkflowState.VOIDED,
        user_id="qa-001",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 16, 0, tzinfo=timezone.utc),
        reason="Created under wrong customer record.",
    )

    assert result.state is WorkflowState.VOIDED
    assert result.audit_event.reason == "Created under wrong customer record."


def test_workflow_service_rejects_blank_identity_fields():
    with pytest.raises(WorkflowServiceError):
        transition_calibration_job(
            job_id=" ",
            current=WorkflowState.DRAFT,
            target=WorkflowState.METADATA_COMPLETE,
            user_id="operator-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 16, 0, tzinfo=timezone.utc),
        )


def test_workflow_service_rejects_invalid_state_type():
    with pytest.raises(WorkflowServiceError):
        transition_calibration_job(
            job_id="job-001",
            current="draft",
            target=WorkflowState.METADATA_COMPLETE,
            user_id="operator-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 16, 0, tzinfo=timezone.utc),
        )


def test_workflow_service_rejects_naive_timestamp():
    with pytest.raises(WorkflowServiceError):
        transition_calibration_job(
            job_id="job-001",
            current=WorkflowState.DRAFT,
            target=WorkflowState.METADATA_COMPLETE,
            user_id="operator-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 16, 0),
        )
