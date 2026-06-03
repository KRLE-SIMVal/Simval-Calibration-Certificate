import sqlite3
from datetime import date, datetime, timezone

import pytest

from app.backend.audit.events import AuditAction
from app.backend.auth.permissions import Role
from app.backend.auth.users import UserAccount, UserSession
from app.backend.domain.entities import (
    CalibrationJob,
    Client,
    Discipline,
    MeasurementMode,
)
from app.backend.domain.workflow import WorkflowState
from app.backend.persistence.sqlite import (
    SQLiteAuditEventRepository,
    SQLiteCalibrationJobRepository,
    SQLiteCertificateMetadataRepository,
    SQLiteUserAccountRepository,
    SQLiteUserSessionRepository,
    initialize_schema,
)
from app.backend.services.authentication import AuthorizationServiceError
from app.backend.services.certificates import (
    CertificateMetadataServiceError,
    capture_certificate_metadata_for_session,
)


def test_capture_certificate_metadata_for_session_records_metadata_and_audits():
    connection = _connection()

    result = capture_certificate_metadata_for_session(
        connection=connection,
        session_id="session-001",
        job_id="job-001",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 14, 30, tzinfo=timezone.utc),
        **_metadata_fields(),
    )

    assert result.metadata.recorded_by == "user-001"
    assert result.metadata.recorded_at == datetime(
        2026,
        6,
        1,
        14,
        30,
        tzinfo=timezone.utc,
    )
    assert result.metadata_audit_event_id == 1
    assert result.workflow_audit_event_id == 2
    assert result.metadata_audit_event.action is AuditAction.METADATA_CHANGED
    assert result.metadata_audit_event.new_value == {
        "certificate_date": "2026-06-03",
        "calibration_date": "2026-06-01",
        "receipt_date": "2026-05-31",
        "task_number": "TASK-2026-001",
        "purchase_order": "PO-12345",
        "client_name": "SIMVal customer",
        "procedure": "SIMVal SOP-TEMP-001",
        "place": "SIMVal Temperature Laboratory, Lyngby",
        "temperature_scale": "ITS-90",
        "recorded_at": "2026-06-01T14:30:00+00:00",
    }
    assert result.workflow_audit_event.action is AuditAction.WORKFLOW_TRANSITIONED
    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.METADATA_COMPLETE
    )
    assert SQLiteCertificateMetadataRepository(connection).get("job-001") == (
        result.metadata
    )
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    ) == (result.metadata_audit_event, result.workflow_audit_event)


def test_capture_certificate_metadata_for_session_rejects_unauthorized_actor():
    connection = _connection(user_roles=(Role.READ_ONLY,))

    with pytest.raises(AuthorizationServiceError):
        capture_certificate_metadata_for_session(
            connection=connection,
            session_id="session-001",
            job_id="job-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 14, 30, tzinfo=timezone.utc),
            **_metadata_fields(),
        )

    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.DRAFT
    )
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    ) == ()


def test_capture_certificate_metadata_for_session_rejects_non_draft_job():
    connection = _connection(job_state=WorkflowState.CALCULATED)

    with pytest.raises(CertificateMetadataServiceError):
        capture_certificate_metadata_for_session(
            connection=connection,
            session_id="session-001",
            job_id="job-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 14, 30, tzinfo=timezone.utc),
            **_metadata_fields(),
        )

    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    ) == ()


def _connection(
    *,
    job_state: WorkflowState = WorkflowState.DRAFT,
    user_roles: tuple[Role, ...] = (Role.OPERATOR,),
) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    SQLiteCalibrationJobRepository(connection).add(
        CalibrationJob(
            id="job-001",
            client=Client(name="SIMVal customer", address="Validated Road 1"),
            discipline=Discipline.TEMPERATURE,
            measurement_mode=MeasurementMode.AUTOMATIC,
            method="ValProbe RT linked XLSX/PDF workflow",
            created_by="operator-001",
            state=job_state,
            created_at=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
        )
    )
    SQLiteUserAccountRepository(connection).add(
        UserAccount(
            id="user-001",
            display_name="Operator User",
            email="operator@example.com",
            roles=user_roles,
            active=True,
            created_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
        )
    )
    SQLiteUserSessionRepository(connection).add(
        UserSession(
            id="session-001",
            user_id="user-001",
            issued_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
            expires_at=datetime(2026, 6, 1, 16, 0, tzinfo=timezone.utc),
        )
    )
    return connection


def _metadata_fields() -> dict:
    return {
        "certificate_date": date(2026, 6, 3),
        "calibration_date": date(2026, 6, 1),
        "receipt_date": date(2026, 5, 31),
        "task_number": "TASK-2026-001",
        "purchase_order": "PO-12345",
        "client_name": "SIMVal customer",
        "client_address": "Validated Road 1, 2800 Lyngby",
        "procedure": "SIMVal SOP-TEMP-001",
        "place": "SIMVal Temperature Laboratory, Lyngby",
        "approved_by_label": "QA User",
        "remarks": "Aflæsning af logger data via ValProbe RT.",
        "traceability_statement": "Measurements are metrologically traceable.",
        "uncertainty_statement": "Expanded uncertainty uses k=2.",
        "ambient_conditions": "Room temperature 23 +/- 2 deg C.",
        "temperature_scale": "ITS-90",
    }
