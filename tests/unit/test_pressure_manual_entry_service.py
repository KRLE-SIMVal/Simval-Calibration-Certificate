import sqlite3
from datetime import datetime, timezone

import pytest

from app.backend.audit.events import AuditAction
from app.backend.auth.permissions import Role
from app.backend.auth.users import UserAccount, UserSession
from app.backend.domain.entities import (
    CalibrationJob,
    Client,
    Discipline,
    MeasurementMode,
    UploadedFile,
    UploadedFileKind,
)
from app.backend.domain.workflow import WorkflowState
from app.backend.persistence.sqlite import (
    SQLiteAuditEventRepository,
    SQLiteCalibrationJobRepository,
    SQLiteDeviceUnderTestRepository,
    SQLiteMeasurementWindowRepository,
    SQLiteUploadedFileRepository,
    SQLiteUserAccountRepository,
    SQLiteUserSessionRepository,
    initialize_schema,
)
from app.backend.services.authentication import AuthenticationServiceError
from app.backend.services.pressure_manual_entry import (
    ManualPressureReadingInput,
    PressureManualEntryServiceError,
    record_manual_pressure_entry_for_session,
)


def test_record_manual_pressure_entry_creates_dut_window_and_audit_evidence():
    connection = _connection_with_pressure_job()

    result = record_manual_pressure_entry_for_session(
        connection=connection,
        session_id="session-001",
        job_id="pressure-job-001",
        uploaded_file_id="pressure-file-001",
        dut_id="pressure-dut-001",
        dut_make="PressureCo",
        dut_model="Gauge",
        dut_serial_number="PG-001",
        dut_channel_id="PG-001",
        window_id="pressure-window-001",
        setpoint=10.0,
        unit="bar",
        readings=_readings(),
        software_version="app-0.1.0",
        timestamp=_timestamp(),
    )

    assert result.state is WorkflowState.WINDOWS_SELECTED
    assert result.dut_id == "pressure-dut-001"
    assert result.window_id == "pressure-window-001"
    assert result.reading_count == 2
    assert SQLiteCalibrationJobRepository(connection).get("pressure-job-001").state is (
        WorkflowState.WINDOWS_SELECTED
    )
    assert SQLiteDeviceUnderTestRepository(connection).get("pressure-dut-001").job_id == (
        "pressure-job-001"
    )
    window = SQLiteMeasurementWindowRepository(connection).get("pressure-window-001")
    assert window.reading_count == 2
    assert [reading.value for reading in window.readings] == [10.004, 10.006]

    job_events = SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "pressure-job-001",
    )
    assert tuple(event.action for event in job_events) == (
        AuditAction.DATA_ENTRY_RECORDED,
        AuditAction.WORKFLOW_TRANSITIONED,
        AuditAction.WORKFLOW_TRANSITIONED,
    )
    window_events = SQLiteAuditEventRepository(connection).list_for_entity(
        "measurement_window",
        "pressure-window-001",
    )
    assert tuple(event.action for event in window_events) == (
        AuditAction.MANUAL_READING_CHANGED,
        AuditAction.MEASUREMENT_WINDOW_CHANGED,
    )
    assert window_events[0].new_value["uploaded_file_id"] == "pressure-file-001"
    assert window_events[0].new_value["readings"][0]["row_number"] == 2


def test_record_manual_pressure_entry_rejects_unauthorized_before_writes():
    connection = _connection_with_pressure_job(user_roles=(Role.READ_ONLY,))

    with pytest.raises(AuthenticationServiceError):
        record_manual_pressure_entry_for_session(
            connection=connection,
            session_id="session-001",
            job_id="pressure-job-001",
            uploaded_file_id="pressure-file-001",
            dut_id="pressure-dut-001",
            dut_make="PressureCo",
            dut_model="Gauge",
            dut_serial_number="PG-001",
            dut_channel_id="PG-001",
            window_id="pressure-window-001",
            setpoint=10.0,
            unit="bar",
            readings=(),
            software_version="app-0.1.0",
            timestamp=_timestamp(),
        )

    assert SQLiteDeviceUnderTestRepository(connection).list_for_job(
        "pressure-job-001"
    ) == ()
    assert SQLiteMeasurementWindowRepository(connection).list_for_job(
        "pressure-job-001"
    ) == ()
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "pressure-job-001",
    ) == ()


def test_record_manual_pressure_entry_requires_pressure_job():
    connection = _connection_with_pressure_job()
    connection.execute(
        "UPDATE calibration_jobs SET discipline = ? WHERE id = ?",
        (Discipline.TEMPERATURE.value, "pressure-job-001"),
    )
    connection.commit()

    with pytest.raises(PressureManualEntryServiceError) as exc_info:
        record_manual_pressure_entry_for_session(
            connection=connection,
            session_id="session-001",
            job_id="pressure-job-001",
            uploaded_file_id="pressure-file-001",
            dut_id="pressure-dut-001",
            dut_make="PressureCo",
            dut_model="Gauge",
            dut_serial_number="PG-001",
            dut_channel_id="PG-001",
            window_id="pressure-window-001",
            setpoint=10.0,
            unit="bar",
            readings=_readings(),
            software_version="app-0.1.0",
            timestamp=_timestamp(),
        )

    assert "pressure discipline" in str(exc_info.value)
    assert SQLiteDeviceUnderTestRepository(connection).list_for_job(
        "pressure-job-001"
    ) == ()


def test_record_manual_pressure_entry_requires_uploaded_evidence_for_job():
    connection = _connection_with_pressure_job()

    with pytest.raises(PressureManualEntryServiceError) as exc_info:
        record_manual_pressure_entry_for_session(
            connection=connection,
            session_id="session-001",
            job_id="pressure-job-001",
            uploaded_file_id="missing-file",
            dut_id="pressure-dut-001",
            dut_make="PressureCo",
            dut_model="Gauge",
            dut_serial_number="PG-001",
            dut_channel_id="PG-001",
            window_id="pressure-window-001",
            setpoint=10.0,
            unit="bar",
            readings=_readings(),
            software_version="app-0.1.0",
            timestamp=_timestamp(),
        )

    assert "uploaded evidence file was not found" in str(exc_info.value)
    assert SQLiteMeasurementWindowRepository(connection).list_for_job(
        "pressure-job-001"
    ) == ()


def _connection_with_pressure_job(
    *,
    user_roles: tuple[Role, ...] = (Role.OPERATOR,),
) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    SQLiteCalibrationJobRepository(connection).add(_job())
    SQLiteUploadedFileRepository(connection).add(_uploaded_file())
    SQLiteUserAccountRepository(connection).add(_user(user_roles))
    SQLiteUserSessionRepository(connection).add(_session())
    return connection


def _job() -> CalibrationJob:
    return CalibrationJob(
        id="pressure-job-001",
        client=Client(name="SIMVal pressure customer", address="Pressure Road 1"),
        discipline=Discipline.PRESSURE,
        measurement_mode=MeasurementMode.MANUAL,
        method="SIMVal pressure method",
        created_by="operator-001",
        state=WorkflowState.EQUIPMENT_SELECTED,
        created_at=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
    )


def _uploaded_file() -> UploadedFile:
    return UploadedFile(
        id="pressure-file-001",
        job_id="pressure-job-001",
        original_filename="pressure-readings.csv",
        checksum_sha256="c" * 64,
        file_kind=UploadedFileKind.OTHER,
        storage_uri="controlled-local://pressure-readings.csv",
        parser_version=None,
        uploaded_at=datetime(2026, 6, 1, 14, 5, tzinfo=timezone.utc),
    )


def _readings() -> tuple[ManualPressureReadingInput, ...]:
    return (
        ManualPressureReadingInput(
            timestamp=datetime(2026, 6, 1, 14, 20, tzinfo=timezone.utc),
            value=10.004,
            source_label="Pressure",
            row_number=2,
            column_label="indication",
        ),
        ManualPressureReadingInput(
            timestamp=datetime(2026, 6, 1, 14, 21, tzinfo=timezone.utc),
            value=10.006,
            source_label="Pressure",
            row_number=3,
            column_label="indication",
        ),
    )


def _user(roles: tuple[Role, ...]) -> UserAccount:
    return UserAccount(
        id="user-001",
        display_name="Operator User",
        email="operator@example.com",
        roles=roles,
        active=True,
        created_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
    )


def _session() -> UserSession:
    return UserSession(
        id="session-001",
        user_id="user-001",
        issued_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 1, 16, 0, tzinfo=timezone.utc),
    )


def _timestamp() -> datetime:
    return datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc)
