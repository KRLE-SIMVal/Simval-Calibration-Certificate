import sqlite3
from datetime import datetime, timezone

import pytest

from app.backend.audit.events import AuditAction, AuditEvent
from app.backend.persistence.sqlite import SQLiteAuditEventRepository, initialize_schema
from app.backend.services.reviewer_independence import (
    ReviewerIndependenceError,
    ReviewerIndependenceStage,
    assert_reviewer_independence,
)


def test_reviewer_independence_rejects_preparation_actor_as_technical_reviewer():
    connection = _connection_with_events(
        AuditEvent(
            entity_type="calibration_job",
            entity_id="job-001",
            action=AuditAction.CALCULATION_RUN,
            user_id="user-001",
            timestamp=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
        )
    )

    with pytest.raises(ReviewerIndependenceError) as exc_info:
        assert_reviewer_independence(
            connection=connection,
            job_id="job-001",
            user_id="user-001",
            stage=ReviewerIndependenceStage.TECHNICAL_REVIEW_APPROVAL,
        )

    assert "reviewer_independence_violation" in str(exc_info.value)


def test_reviewer_independence_allows_different_technical_reviewer():
    connection = _connection_with_events(
        AuditEvent(
            entity_type="calibration_job",
            entity_id="job-001",
            action=AuditAction.CALCULATION_RUN,
            user_id="operator-001",
            timestamp=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
        )
    )

    assert_reviewer_independence(
        connection=connection,
        job_id="job-001",
        user_id="reviewer-001",
        stage=ReviewerIndependenceStage.TECHNICAL_REVIEW_APPROVAL,
    )


def test_reviewer_independence_rejects_qa_approval_by_technical_reviewer():
    connection = _connection_with_events(
        AuditEvent(
            entity_type="calibration_job",
            entity_id="job-001",
            action=AuditAction.WORKFLOW_TRANSITIONED,
            user_id="reviewer-001",
            timestamp=datetime(2026, 6, 1, 14, 30, tzinfo=timezone.utc),
            previous_value={"state": "technical_review"},
            new_value={"state": "qa_review"},
        )
    )

    with pytest.raises(ReviewerIndependenceError):
        assert_reviewer_independence(
            connection=connection,
            job_id="job-001",
            user_id="reviewer-001",
            stage=ReviewerIndependenceStage.QA_RELEASE_APPROVAL,
        )


def test_reviewer_independence_rejects_release_by_qa_approver():
    connection = _connection_with_events(
        AuditEvent(
            entity_type="calibration_job",
            entity_id="job-001",
            action=AuditAction.WORKFLOW_TRANSITIONED,
            user_id="qa-001",
            timestamp=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
            previous_value={"state": "qa_review"},
            new_value={"state": "approved"},
        )
    )

    with pytest.raises(ReviewerIndependenceError):
        assert_reviewer_independence(
            connection=connection,
            job_id="job-001",
            user_id="qa-001",
            stage=ReviewerIndependenceStage.CERTIFICATE_RELEASE,
        )


def _connection_with_events(*events: AuditEvent) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    repository = SQLiteAuditEventRepository(connection)
    for event in events:
        repository.append(event)
    return connection
