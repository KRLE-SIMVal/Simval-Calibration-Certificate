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
from app.backend.domain.equipment import (
    EquipmentRange,
    EquipmentStatus,
    ReferenceEquipment,
)
from app.backend.domain.workflow import WorkflowState
from app.backend.persistence.sqlite import (
    SQLiteAuditEventRepository,
    SQLiteCalibrationJobRepository,
    SQLiteSelectedReferenceEquipmentRepository,
    SQLiteUserAccountRepository,
    SQLiteUserSessionRepository,
    initialize_schema,
)
from app.backend.services.authentication import AuthorizationServiceError
from app.backend.services.certificates import (
    CertificateReferenceEquipmentServiceError,
    select_reference_equipment_for_session,
)


def test_select_reference_equipment_for_session_records_selection_and_audits():
    connection = _connection()

    result = select_reference_equipment_for_session(
        connection=connection,
        session_id="session-001",
        job_id="job-001",
        equipment=_equipment(),
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
    )

    assert result.selection.selected_by == "user-001"
    assert result.selection.selected_at == datetime(
        2026,
        6,
        1,
        15,
        0,
        tzinfo=timezone.utc,
    )
    assert result.selection_audit_event_id == 1
    assert result.workflow_audit_event_id == 2
    assert result.selection_audit_event.action is (
        AuditAction.REFERENCE_EQUIPMENT_SELECTED
    )
    assert result.selection_audit_event.new_value == {
        "equipment_id": "ref-001",
        "simval_id": "SIM-T-001",
        "equipment_type": "IRTD",
        "serial_number": "IRT-123",
        "calibration_certificate_reference": "DANAK-CAL-12345",
        "calibration_due_date": "2027-04-30",
        "range": "-90 to 140 deg C",
        "selected_at": "2026-06-01T15:00:00+00:00",
    }
    assert result.workflow_audit_event.action is AuditAction.WORKFLOW_TRANSITIONED
    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.EQUIPMENT_SELECTED
    )
    assert SQLiteSelectedReferenceEquipmentRepository(connection).list_for_job(
        "job-001"
    ) == (result.selection,)
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    ) == (result.selection_audit_event, result.workflow_audit_event)


def test_select_reference_equipment_for_session_rejects_unauthorized_actor():
    connection = _connection(user_roles=(Role.READ_ONLY,))

    with pytest.raises(AuthorizationServiceError):
        select_reference_equipment_for_session(
            connection=connection,
            session_id="session-001",
            job_id="job-001",
            equipment=_equipment(),
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
        )

    assert SQLiteSelectedReferenceEquipmentRepository(connection).list_for_job(
        "job-001"
    ) == ()
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    ) == ()


def test_select_reference_equipment_for_session_rejects_wrong_workflow_state():
    connection = _connection(job_state=WorkflowState.DRAFT)

    with pytest.raises(CertificateReferenceEquipmentServiceError):
        select_reference_equipment_for_session(
            connection=connection,
            session_id="session-001",
            job_id="job-001",
            equipment=_equipment(),
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
        )

    assert SQLiteSelectedReferenceEquipmentRepository(connection).list_for_job(
        "job-001"
    ) == ()
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    ) == ()


def _connection(
    *,
    job_state: WorkflowState = WorkflowState.METADATA_COMPLETE,
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


def _equipment() -> ReferenceEquipment:
    return ReferenceEquipment(
        id="ref-001",
        simval_id="SIM-T-001",
        equipment_type="IRTD",
        serial_number="IRT-123",
        discipline=Discipline.TEMPERATURE,
        calibration_certificate_reference="DANAK-CAL-12345",
        calibration_due_date=date(2027, 4, 30),
        status=EquipmentStatus.ACTIVE,
        usable_range=EquipmentRange(minimum=-90.0, maximum=140.0, unit="deg C"),
        traceability_statement="Accredited calibration with SI traceability.",
    )
