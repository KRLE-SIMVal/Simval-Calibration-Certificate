import sqlite3
from datetime import datetime, timezone

import pytest

from app.backend.audit.events import AuditAction, AuditEvent
from app.backend.domain.entities import (
    CalibrationJob,
    Client,
    Discipline,
    MeasurementMode,
)
from app.backend.domain.workflow import WorkflowState, WorkflowTransitionError
from app.backend.persistence.sqlite import (
    ConcurrencyError,
    PersistenceError,
    SQLiteAuditEventRepository,
    SQLiteCalibrationJobRepository,
    initialize_schema,
)
from app.backend.persistence.workflow import persist_workflow_transition


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    return connection


def _created_at() -> datetime:
    return datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc)


def _transition_at() -> datetime:
    return datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc)


def _job(state: WorkflowState = WorkflowState.DRAFT) -> CalibrationJob:
    return CalibrationJob(
        id="job-001",
        client=Client(name="SIMVal customer", address="Validated Road 1"),
        discipline=Discipline.TEMPERATURE,
        measurement_mode=MeasurementMode.AUTOMATIC,
        method="ValProbe RT linked XLSX/PDF workflow",
        created_by="operator-001",
        state=state,
        created_at=_created_at(),
    )


def _audit_event() -> AuditEvent:
    return AuditEvent(
        entity_type="calibration_job",
        entity_id="job-001",
        action=AuditAction.WORKFLOW_TRANSITIONED,
        user_id="operator-001",
        timestamp=_transition_at(),
        previous_value={"state": "draft"},
        new_value={"state": "metadata_complete"},
        software_version="app-0.1.0",
        constant_set_version="constants-2026-001",
        budget_version="budget-temp-001",
    )


def test_sqlite_job_repository_round_trips_calibration_job():
    connection = _connection()
    repository = SQLiteCalibrationJobRepository(connection)
    job = _job()

    repository.add(job)

    loaded = repository.get("job-001")
    assert loaded == job


def test_sqlite_job_repository_rejects_duplicate_job_id():
    connection = _connection()
    repository = SQLiteCalibrationJobRepository(connection)
    job = _job()
    repository.add(job)

    with pytest.raises(PersistenceError):
        repository.add(job)

    assert repository.get("job-001") == job


def test_sqlite_audit_repository_appends_and_reads_by_entity_in_order():
    connection = _connection()
    repository = SQLiteAuditEventRepository(connection)
    first = _audit_event()
    second = AuditEvent(
        entity_type="calibration_job",
        entity_id="job-001",
        action=AuditAction.METADATA_CHANGED,
        user_id="operator-002",
        timestamp=datetime(2026, 6, 1, 15, 5, tzinfo=timezone.utc),
        previous_value={"method": "draft method"},
        new_value={"method": "approved method"},
        reason="Corrected method label before review.",
        software_version="app-0.1.0",
    )

    first_id = repository.append(first)
    second_id = repository.append(second)

    assert first_id == 1
    assert second_id == 2
    events = repository.list_for_entity("calibration_job", "job-001")
    assert events == (first, second)
    assert events[0].new_value == {"state": "metadata_complete"}
    assert events[0].constant_set_version == "constants-2026-001"


def test_sqlite_audit_events_are_append_only_at_database_level():
    connection = _connection()
    repository = SQLiteAuditEventRepository(connection)
    event_id = repository.append(_audit_event())

    with pytest.raises(sqlite3.DatabaseError):
        connection.execute(
            "UPDATE audit_events SET reason = ? WHERE id = ?",
            ("changed after release", event_id),
        )
    connection.rollback()

    with pytest.raises(sqlite3.DatabaseError):
        connection.execute("DELETE FROM audit_events WHERE id = ?", (event_id,))
    connection.rollback()

    assert repository.list_for_entity("calibration_job", "job-001") == (_audit_event(),)


def test_persisted_workflow_transition_updates_state_and_appends_audit_event():
    connection = _connection()
    job_repository = SQLiteCalibrationJobRepository(connection)
    audit_repository = SQLiteAuditEventRepository(connection)
    job_repository.add(_job())

    result = persist_workflow_transition(
        connection=connection,
        job_id="job-001",
        target=WorkflowState.METADATA_COMPLETE,
        user_id="operator-001",
        software_version="app-0.1.0",
        timestamp=_transition_at(),
    )

    assert result.job.state is WorkflowState.METADATA_COMPLETE
    assert result.audit_event_id == 1
    assert job_repository.get("job-001").state is WorkflowState.METADATA_COMPLETE
    events = audit_repository.list_for_entity("calibration_job", "job-001")
    assert len(events) == 1
    assert events[0].previous_value == {"state": "draft"}
    assert events[0].new_value == {"state": "metadata_complete"}


def test_invalid_persisted_workflow_transition_rolls_back_state_and_audit_event():
    connection = _connection()
    job_repository = SQLiteCalibrationJobRepository(connection)
    audit_repository = SQLiteAuditEventRepository(connection)
    job_repository.add(_job())

    with pytest.raises(WorkflowTransitionError):
        persist_workflow_transition(
            connection=connection,
            job_id="job-001",
            target=WorkflowState.RELEASED,
            user_id="operator-001",
            software_version="app-0.1.0",
            timestamp=_transition_at(),
        )

    assert job_repository.get("job-001").state is WorkflowState.DRAFT
    assert audit_repository.list_for_entity("calibration_job", "job-001") == ()


def test_sqlite_job_repository_rejects_stale_state_update():
    connection = _connection()
    repository = SQLiteCalibrationJobRepository(connection)
    repository.add(_job())

    with pytest.raises(ConcurrencyError):
        repository.update_state(
            job_id="job-001",
            expected_state=WorkflowState.METADATA_COMPLETE,
            new_state=WorkflowState.DATA_ENTERED,
        )

    assert repository.get("job-001").state is WorkflowState.DRAFT
