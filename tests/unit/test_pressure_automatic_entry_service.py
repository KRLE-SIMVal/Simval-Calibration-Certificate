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
from app.backend.services.pressure_automatic_entry import (
    PressureAutomaticEntryServiceError,
    record_automatic_pressure_entry_for_session,
)


def test_record_automatic_pressure_entry_imports_csv_window_and_audit_evidence(
    tmp_path,
):
    connection = _connection_with_pressure_job()
    artifact_directory = tmp_path / "artifacts"
    _write_pressure_csv(artifact_directory)

    result = record_automatic_pressure_entry_for_session(
        connection=connection,
        session_id="session-001",
        job_id="pressure-job-001",
        uploaded_file_id="pressure-file-001",
        dut_id="pressure-dut-001",
        dut_make="PressureCo",
        dut_model="Transmitter",
        dut_serial_number="PT-001",
        dut_channel_id="PT-001",
        window_id="pressure-window-001",
        setpoint=10.0,
        unit="bar",
        parser_version="pressure-csv-parser-v1",
        artifact_directory=artifact_directory,
        software_version="app-0.1.0",
        timestamp=_timestamp(),
    )

    assert result.state is WorkflowState.WINDOWS_SELECTED
    assert result.reference_values == (10.0, 10.001)
    assert result.indication_values == (10.004, 10.005)
    assert result.reference_reading_count == 2
    assert result.indication_reading_count == 2
    assert result.warnings == ()
    assert SQLiteCalibrationJobRepository(connection).get("pressure-job-001").state is (
        WorkflowState.WINDOWS_SELECTED
    )
    assert SQLiteDeviceUnderTestRepository(connection).get("pressure-dut-001").job_id == (
        "pressure-job-001"
    )
    window = SQLiteMeasurementWindowRepository(connection).get("pressure-window-001")
    assert [reading.value for reading in window.readings] == [10.004, 10.005]
    assert window.readings[0].source.source_label == "simval-pressure-paired-csv-v1"
    assert window.readings[0].source.row_number == 2

    upload_events = SQLiteAuditEventRepository(connection).list_for_entity(
        "uploaded_file",
        "pressure-file-001",
    )
    assert tuple(event.action for event in upload_events) == (
        AuditAction.PARSER_RESULT_RECORDED,
    )
    assert upload_events[0].new_value["parser_status"] == "parsed"
    assert upload_events[0].new_value["reading_count"] == 4

    job_events = SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "pressure-job-001",
    )
    assert tuple(event.action for event in job_events) == (
        AuditAction.PARSER_RESULT_RECORDED,
        AuditAction.DATA_ENTRY_RECORDED,
        AuditAction.WORKFLOW_TRANSITIONED,
        AuditAction.WORKFLOW_TRANSITIONED,
    )
    window_events = SQLiteAuditEventRepository(connection).list_for_entity(
        "measurement_window",
        "pressure-window-001",
    )
    assert tuple(event.action for event in window_events) == (
        AuditAction.IMPORT_ALIGNMENT_RECORDED,
        AuditAction.MEASUREMENT_WINDOW_CHANGED,
    )
    assert window_events[0].new_value["readings"][0]["reference_value"] == 10.0


def test_record_automatic_pressure_entry_rejects_manual_pressure_job(tmp_path):
    connection = _connection_with_pressure_job(mode=MeasurementMode.MANUAL)
    artifact_directory = tmp_path / "artifacts"
    _write_pressure_csv(artifact_directory)

    with pytest.raises(PressureAutomaticEntryServiceError) as exc_info:
        record_automatic_pressure_entry_for_session(
            connection=connection,
            session_id="session-001",
            job_id="pressure-job-001",
            uploaded_file_id="pressure-file-001",
            dut_id="pressure-dut-001",
            dut_make="PressureCo",
            dut_model="Transmitter",
            dut_serial_number="PT-001",
            dut_channel_id="PT-001",
            window_id="pressure-window-001",
            setpoint=10.0,
            unit="bar",
            parser_version="pressure-csv-parser-v1",
            artifact_directory=artifact_directory,
            software_version="app-0.1.0",
            timestamp=_timestamp(),
        )

    assert "automatic pressure mode" in str(exc_info.value)
    assert SQLiteMeasurementWindowRepository(connection).list_for_job(
        "pressure-job-001"
    ) == ()


def test_record_automatic_pressure_entry_rejects_unauthorized_before_writes(
    tmp_path,
):
    connection = _connection_with_pressure_job(user_roles=(Role.READ_ONLY,))
    artifact_directory = tmp_path / "artifacts"
    _write_pressure_csv(artifact_directory)

    with pytest.raises(AuthenticationServiceError):
        record_automatic_pressure_entry_for_session(
            connection=connection,
            session_id="session-001",
            job_id="pressure-job-001",
            uploaded_file_id="pressure-file-001",
            dut_id="pressure-dut-001",
            dut_make="PressureCo",
            dut_model="Transmitter",
            dut_serial_number="PT-001",
            dut_channel_id="PT-001",
            window_id="pressure-window-001",
            setpoint=10.0,
            unit="bar",
            parser_version="pressure-csv-parser-v1",
            artifact_directory=artifact_directory,
            software_version="app-0.1.0",
            timestamp=_timestamp(),
        )

    assert SQLiteDeviceUnderTestRepository(connection).list_for_job(
        "pressure-job-001"
    ) == ()
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "pressure-job-001",
    ) == ()


def test_record_automatic_pressure_entry_rejects_unit_mismatch(tmp_path):
    connection = _connection_with_pressure_job()
    artifact_directory = tmp_path / "artifacts"
    _write_pressure_csv(artifact_directory, unit="kPa")

    with pytest.raises(PressureAutomaticEntryServiceError) as exc_info:
        record_automatic_pressure_entry_for_session(
            connection=connection,
            session_id="session-001",
            job_id="pressure-job-001",
            uploaded_file_id="pressure-file-001",
            dut_id="pressure-dut-001",
            dut_make="PressureCo",
            dut_model="Transmitter",
            dut_serial_number="PT-001",
            dut_channel_id="PT-001",
            window_id="pressure-window-001",
            setpoint=10.0,
            unit="bar",
            parser_version="pressure-csv-parser-v1",
            artifact_directory=artifact_directory,
            software_version="app-0.1.0",
            timestamp=_timestamp(),
        )

    assert "unit must match" in str(exc_info.value)
    assert SQLiteMeasurementWindowRepository(connection).list_for_job(
        "pressure-job-001"
    ) == ()


def _connection_with_pressure_job(
    *,
    mode: MeasurementMode = MeasurementMode.AUTOMATIC,
    user_roles: tuple[Role, ...] = (Role.OPERATOR,),
) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    SQLiteCalibrationJobRepository(connection).add(_job(mode=mode))
    SQLiteUploadedFileRepository(connection).add(_uploaded_file())
    SQLiteUserAccountRepository(connection).add(_user(user_roles))
    SQLiteUserSessionRepository(connection).add(_session())
    return connection


def _write_pressure_csv(artifact_directory, *, unit: str = "bar") -> None:
    target = (
        artifact_directory
        / "uploads"
        / "pressure-job-001"
        / "pressure-file-001-pressure-readings.csv"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "\n".join(
            (
                "timestamp,reference,indication,unit",
                f"2026-06-01T14:20:00Z,10.000,10.004,{unit}",
                f"2026-06-01T14:21:00Z,10.001,10.005,{unit}",
                "",
            )
        ),
        encoding="utf-8",
    )


def _job(*, mode: MeasurementMode) -> CalibrationJob:
    return CalibrationJob(
        id="pressure-job-001",
        client=Client(name="SIMVal pressure customer", address="Pressure Road 1"),
        discipline=Discipline.PRESSURE,
        measurement_mode=mode,
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
        storage_uri=(
            "controlled-local://uploads/pressure-job-001/"
            "pressure-file-001-pressure-readings.csv"
        ),
        parser_version=None,
        uploaded_at=datetime(2026, 6, 1, 14, 5, tzinfo=timezone.utc),
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
