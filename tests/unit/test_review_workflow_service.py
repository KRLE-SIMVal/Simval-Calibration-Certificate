import sqlite3
from datetime import datetime, timezone

import pytest

from app.backend.audit.events import AuditAction, AuditEvent
from app.backend.auth.permissions import Role
from app.backend.auth.users import UserAccount, UserSession
from app.backend.domain.entities import CalibrationJob, Client, Discipline, MeasurementMode
from app.backend.domain.workflow import WorkflowState
from app.backend.persistence.sqlite import (
    SQLiteAuditEventRepository,
    SQLiteCalibrationJobRepository,
    SQLiteUserAccountRepository,
    SQLiteUserSessionRepository,
    initialize_schema,
)
from app.backend.services.review_workflow import (
    ReviewWorkflowServiceError,
    approve_qa_release_for_session,
    approve_technical_review_for_session,
)


def test_technical_review_approval_rejects_same_user_calculation_actor():
    connection = _connection_with_job_and_user(
        job_state=WorkflowState.TECHNICAL_REVIEW,
        user=_user("reviewer-001", (Role.TECHNICAL_REVIEWER,)),
        session=_session("reviewer-session", "reviewer-001"),
    )
    SQLiteAuditEventRepository(connection).append(
        AuditEvent(
            entity_type="calibration_job",
            entity_id="job-001",
            action=AuditAction.CALCULATION_RUN,
            user_id="reviewer-001",
            timestamp=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
        )
    )

    with pytest.raises(ReviewWorkflowServiceError) as exc_info:
        approve_technical_review_for_session(
            connection=connection,
            session_id="reviewer-session",
            job_id="job-001",
            software_version="0.1.0",
            timestamp=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
        )

    assert "reviewer_independence_violation" in str(exc_info.value)
    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.TECHNICAL_REVIEW
    )
    events = SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    )
    assert [event.action for event in events] == [AuditAction.CALCULATION_RUN]


def test_technical_review_approval_allows_independent_reviewer():
    connection = _connection_with_job_and_user(
        job_state=WorkflowState.TECHNICAL_REVIEW,
        user=_user("reviewer-001", (Role.TECHNICAL_REVIEWER,)),
        session=_session("reviewer-session", "reviewer-001"),
    )
    SQLiteAuditEventRepository(connection).append(
        AuditEvent(
            entity_type="calibration_job",
            entity_id="job-001",
            action=AuditAction.CALCULATION_RUN,
            user_id="operator-001",
            timestamp=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
        )
    )

    result = approve_technical_review_for_session(
        connection=connection,
        session_id="reviewer-session",
        job_id="job-001",
        software_version="0.1.0",
        timestamp=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
    )

    assert result.job.state is WorkflowState.QA_REVIEW
    assert result.audit_event.user_id == "reviewer-001"


def test_qa_release_approval_rejects_same_user_technical_reviewer():
    connection = _connection_with_job_and_user(
        job_state=WorkflowState.QA_REVIEW,
        user=_user("qa-001", (Role.QA_APPROVER,)),
        session=_session("qa-session", "qa-001"),
    )
    SQLiteAuditEventRepository(connection).append(
        AuditEvent(
            entity_type="calibration_job",
            entity_id="job-001",
            action=AuditAction.WORKFLOW_TRANSITIONED,
            user_id="qa-001",
            timestamp=datetime(2026, 6, 1, 14, 30, tzinfo=timezone.utc),
            previous_value={"state": "technical_review"},
            new_value={"state": "qa_review"},
        )
    )

    with pytest.raises(ReviewWorkflowServiceError):
        approve_qa_release_for_session(
            connection=connection,
            session_id="qa-session",
            job_id="job-001",
            software_version="0.1.0",
            timestamp=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
        )

    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.QA_REVIEW
    )


def _connection_with_job_and_user(
    *,
    job_state: WorkflowState,
    user: UserAccount,
    session: UserSession,
) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    SQLiteCalibrationJobRepository(connection).add(_job(job_state))
    SQLiteUserAccountRepository(connection).add(user)
    SQLiteUserSessionRepository(connection).add(session)
    return connection


def _job(state: WorkflowState) -> CalibrationJob:
    return CalibrationJob(
        id="job-001",
        client=Client(name="SIMVal customer", address="Validated Road 1"),
        discipline=Discipline.TEMPERATURE,
        measurement_mode=MeasurementMode.AUTOMATIC,
        method="ValProbe RT linked XLSX/PDF workflow",
        created_by="operator-001",
        state=state,
        created_at=datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
    )


def _user(user_id: str, roles: tuple[Role, ...]) -> UserAccount:
    return UserAccount(
        id=user_id,
        display_name=f"{user_id} User",
        email=f"{user_id}@example.com",
        roles=roles,
        created_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
    )


def _session(session_id: str, user_id: str) -> UserSession:
    return UserSession(
        id=session_id,
        user_id=user_id,
        issued_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 1, 16, 0, tzinfo=timezone.utc),
    )
