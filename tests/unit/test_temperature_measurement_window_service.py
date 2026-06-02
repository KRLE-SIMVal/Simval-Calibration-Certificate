import sqlite3
from datetime import datetime, timezone

import pytest

from app.backend.audit.events import AuditAction
from app.backend.auth.permissions import Role
from app.backend.auth.users import UserAccount, UserSession
from app.backend.domain.entities import (
    CalibrationJob,
    Client,
    DeviceUnderTest,
    Discipline,
    LinkedTemperatureReading,
    MeasurementMode,
    MeasurementReading,
    SourceLocation,
    UploadedFile,
    UploadedFileKind,
)
from app.backend.domain.workflow import WorkflowState
from app.backend.persistence.sqlite import (
    SQLiteAuditEventRepository,
    SQLiteCalibrationJobRepository,
    SQLiteDeviceUnderTestRepository,
    SQLiteLinkedTemperatureReadingRepository,
    SQLiteMeasurementWindowRepository,
    SQLiteUserAccountRepository,
    SQLiteUserSessionRepository,
    SQLiteUploadedFileRepository,
    initialize_schema,
)
from app.backend.services.authentication import AuthenticationServiceError
from app.backend.services.measurement_windows import (
    MeasurementWindowSelectionError,
    select_temperature_window_from_linked_readings,
    select_temperature_window_from_linked_readings_for_session,
)


def _connection_with_linked_readings(
    *,
    job_state: WorkflowState = WorkflowState.DATA_ENTERED,
    user_roles: tuple[Role, ...] = (Role.OPERATOR,),
) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    SQLiteCalibrationJobRepository(connection).add(_job(job_state))
    file_repository = SQLiteUploadedFileRepository(connection)
    file_repository.add(_calibration_file())
    file_repository.add(_verification_file())
    SQLiteDeviceUnderTestRepository(connection).add(_dut())
    SQLiteLinkedTemperatureReadingRepository(connection).add_many(
        job_id="job-001",
        linked_readings=_linked_readings(),
    )
    SQLiteUserAccountRepository(connection).add(_user(user_roles))
    SQLiteUserSessionRepository(connection).add(_session())
    return connection


def test_select_temperature_window_persists_window_and_audit_event():
    connection = _connection_with_linked_readings()

    result = select_temperature_window_from_linked_readings(
        connection=connection,
        window_id="window-001",
        job_id="job-001",
        dut_id="dut-001",
        dut_channel_id="MJT1-A",
        setpoint=-80.0,
        unit="deg C",
        start_timestamp=datetime(2026, 4, 8, 15, 45, tzinfo=timezone.utc),
        end_timestamp=datetime(2026, 4, 8, 15, 46, tzinfo=timezone.utc),
        selected_by="operator-001",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 14, 20, tzinfo=timezone.utc),
    )

    assert result.audit_event_id == 1
    assert result.window.id == "window-001"
    assert result.window.reading_count == 2
    assert result.window.start_timestamp == datetime(
        2026,
        4,
        8,
        15,
        45,
        tzinfo=timezone.utc,
    )
    assert result.window.end_timestamp == datetime(
        2026,
        4,
        8,
        15,
        46,
        tzinfo=timezone.utc,
    )
    assert result.window.readings[0].source.uploaded_file_id == "file-001"
    assert tuple(pair.reference.value for pair in result.linked_readings) == (
        -80.031,
        -80.030,
    )
    assert (
        SQLiteMeasurementWindowRepository(connection).get("window-001")
        == result.window
    )
    events = SQLiteAuditEventRepository(connection).list_for_entity(
        "measurement_window",
        "window-001",
    )
    assert events == (result.audit_event,)
    assert events[0].action is AuditAction.MEASUREMENT_WINDOW_CHANGED
    assert events[0].new_value == {
        "job_id": "job-001",
        "dut_id": "dut-001",
        "dut_channel_id": "MJT1-A",
        "setpoint": -80.0,
        "unit": "deg C",
        "start_timestamp": "2026-04-08T15:45:00+00:00",
        "end_timestamp": "2026-04-08T15:46:00+00:00",
        "linked_reading_count": 2,
    }


def test_select_temperature_window_for_session_uses_actor_for_selection_and_audit():
    connection = _connection_with_linked_readings()

    result = select_temperature_window_from_linked_readings_for_session(
        connection=connection,
        session_id="session-001",
        window_id="window-001",
        job_id="job-001",
        dut_id="dut-001",
        dut_channel_id="MJT1-A",
        setpoint=-80.0,
        unit="deg C",
        start_timestamp=datetime(2026, 4, 8, 15, 45, tzinfo=timezone.utc),
        end_timestamp=datetime(2026, 4, 8, 15, 46, tzinfo=timezone.utc),
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 14, 20, tzinfo=timezone.utc),
    )

    assert result.window.selected_by == "user-001"
    assert result.audit_event.user_id == "user-001"


def test_select_temperature_window_for_session_rejects_unauthorized_actor():
    connection = _connection_with_linked_readings(user_roles=(Role.READ_ONLY,))

    with pytest.raises(AuthenticationServiceError):
        select_temperature_window_from_linked_readings_for_session(
            connection=connection,
            session_id="session-001",
            window_id="window-001",
            job_id="job-001",
            dut_id="dut-001",
            dut_channel_id="MJT1-A",
            setpoint=-80.0,
            unit="deg C",
            start_timestamp=datetime(2026, 4, 8, 15, 45, tzinfo=timezone.utc),
            end_timestamp=datetime(2026, 4, 8, 15, 46, tzinfo=timezone.utc),
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 14, 20, tzinfo=timezone.utc),
        )

    assert SQLiteMeasurementWindowRepository(connection).list_for_job("job-001") == ()
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "measurement_window",
        "window-001",
    ) == ()


def test_select_temperature_window_filters_channel_and_range():
    connection = _connection_with_linked_readings()

    result = select_temperature_window_from_linked_readings(
        connection=connection,
        window_id="window-001",
        job_id="job-001",
        dut_id="dut-001",
        dut_channel_id="MJT1-A",
        setpoint=-80.0,
        unit="deg C",
        start_timestamp=datetime(2026, 4, 8, 15, 46, tzinfo=timezone.utc),
        end_timestamp=datetime(2026, 4, 8, 15, 46, tzinfo=timezone.utc),
        selected_by="operator-001",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 14, 20, tzinfo=timezone.utc),
    )

    assert result.window.reading_count == 1
    assert result.window.readings[0].timestamp == datetime(
        2026,
        4,
        8,
        15,
        46,
        tzinfo=timezone.utc,
    )
    assert result.linked_readings[0].dut_channel_id == "MJT1-A"


def test_select_temperature_window_rejects_empty_selection_without_persistence():
    connection = _connection_with_linked_readings()

    with pytest.raises(MeasurementWindowSelectionError):
        select_temperature_window_from_linked_readings(
            connection=connection,
            window_id="window-001",
            job_id="job-001",
            dut_id="dut-001",
            dut_channel_id="MJT1-A",
            setpoint=-80.0,
            unit="deg C",
            start_timestamp=datetime(2026, 4, 8, 16, 0, tzinfo=timezone.utc),
            end_timestamp=datetime(2026, 4, 8, 16, 5, tzinfo=timezone.utc),
            selected_by="operator-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 14, 20, tzinfo=timezone.utc),
        )

    assert SQLiteMeasurementWindowRepository(connection).list_for_job("job-001") == ()
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "measurement_window",
        "window-001",
    ) == ()


def test_select_temperature_window_rejects_dut_channel_mismatch():
    connection = _connection_with_linked_readings()

    with pytest.raises(MeasurementWindowSelectionError):
        select_temperature_window_from_linked_readings(
            connection=connection,
            window_id="window-001",
            job_id="job-001",
            dut_id="dut-001",
            dut_channel_id="NWU2-A",
            setpoint=-80.0,
            unit="deg C",
            start_timestamp=datetime(2026, 4, 8, 15, 45, tzinfo=timezone.utc),
            end_timestamp=datetime(2026, 4, 8, 15, 46, tzinfo=timezone.utc),
            selected_by="operator-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 14, 20, tzinfo=timezone.utc),
        )

    assert SQLiteMeasurementWindowRepository(connection).list_for_job("job-001") == ()


def test_select_temperature_window_rejects_dut_from_another_job():
    connection = _connection_with_linked_readings()
    SQLiteCalibrationJobRepository(connection).add(
        CalibrationJob(
            id="job-002",
            client=Client(name="Other customer", address="Validated Road 2"),
            discipline=Discipline.TEMPERATURE,
            measurement_mode=MeasurementMode.AUTOMATIC,
            method="ValProbe RT linked XLSX/PDF workflow",
            created_by="operator-001",
            state=WorkflowState.DATA_ENTERED,
            created_at=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
        )
    )
    SQLiteDeviceUnderTestRepository(connection).add(
        DeviceUnderTest(
            id="dut-002",
            job_id="job-002",
            make="Kaye",
            model="ValProbe RT",
            serial_number="MJT1",
            channel_id="MJT1-A",
        )
    )

    with pytest.raises(MeasurementWindowSelectionError):
        select_temperature_window_from_linked_readings(
            connection=connection,
            window_id="window-001",
            job_id="job-001",
            dut_id="dut-002",
            dut_channel_id="MJT1-A",
            setpoint=-80.0,
            unit="deg C",
            start_timestamp=datetime(2026, 4, 8, 15, 45, tzinfo=timezone.utc),
            end_timestamp=datetime(2026, 4, 8, 15, 46, tzinfo=timezone.utc),
            selected_by="operator-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 14, 20, tzinfo=timezone.utc),
        )

    assert SQLiteMeasurementWindowRepository(connection).list_for_job("job-001") == ()


def test_select_temperature_window_rejects_before_data_entered_state():
    connection = _connection_with_linked_readings(
        job_state=WorkflowState.EQUIPMENT_SELECTED,
    )

    with pytest.raises(MeasurementWindowSelectionError):
        select_temperature_window_from_linked_readings(
            connection=connection,
            window_id="window-001",
            job_id="job-001",
            dut_id="dut-001",
            dut_channel_id="MJT1-A",
            setpoint=-80.0,
            unit="deg C",
            start_timestamp=datetime(2026, 4, 8, 15, 45, tzinfo=timezone.utc),
            end_timestamp=datetime(2026, 4, 8, 15, 46, tzinfo=timezone.utc),
            selected_by="operator-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 14, 20, tzinfo=timezone.utc),
        )

    assert SQLiteMeasurementWindowRepository(connection).list_for_job("job-001") == ()


def test_select_temperature_window_rejects_inverted_timestamp_range():
    connection = _connection_with_linked_readings()

    with pytest.raises(MeasurementWindowSelectionError):
        select_temperature_window_from_linked_readings(
            connection=connection,
            window_id="window-001",
            job_id="job-001",
            dut_id="dut-001",
            dut_channel_id="MJT1-A",
            setpoint=-80.0,
            unit="deg C",
            start_timestamp=datetime(2026, 4, 8, 15, 46, tzinfo=timezone.utc),
            end_timestamp=datetime(2026, 4, 8, 15, 45, tzinfo=timezone.utc),
            selected_by="operator-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 14, 20, tzinfo=timezone.utc),
        )

    assert SQLiteMeasurementWindowRepository(connection).list_for_job("job-001") == ()


def _job(state: WorkflowState) -> CalibrationJob:
    return CalibrationJob(
        id="job-001",
        client=Client(name="SIMVal customer", address="Validated Road 1"),
        discipline=Discipline.TEMPERATURE,
        measurement_mode=MeasurementMode.AUTOMATIC,
        method="ValProbe RT linked XLSX/PDF workflow",
        created_by="operator-001",
        state=state,
        created_at=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
    )


def _calibration_file() -> UploadedFile:
    return UploadedFile(
        id="file-001",
        job_id="job-001",
        original_filename="sanitized-valprobe.xlsx",
        checksum_sha256="a" * 64,
        file_kind=UploadedFileKind.CALIBRATION_XLSX,
        storage_uri="controlled-local://sanitized-valprobe.xlsx",
        parser_version="valprobe-xlsx-parser-v1",
        uploaded_at=datetime(2026, 6, 1, 14, 5, tzinfo=timezone.utc),
    )


def _verification_file() -> UploadedFile:
    return UploadedFile(
        id="file-002",
        job_id="job-001",
        original_filename="sanitized-verification.pdf",
        checksum_sha256="b" * 64,
        file_kind=UploadedFileKind.VERIFICATION_PDF,
        storage_uri="controlled-local://sanitized-verification.pdf",
        parser_version="verification-irtd-table-parser-v1",
        uploaded_at=datetime(2026, 6, 1, 14, 7, tzinfo=timezone.utc),
    )


def _dut() -> DeviceUnderTest:
    return DeviceUnderTest(
        id="dut-001",
        job_id="job-001",
        make="Kaye",
        model="ValProbe RT",
        serial_number="MJT1",
        channel_id="MJT1-A",
    )


def _linked_readings() -> tuple[LinkedTemperatureReading, ...]:
    first_time = datetime(2026, 4, 8, 15, 45, tzinfo=timezone.utc)
    second_time = datetime(2026, 4, 8, 15, 46, tzinfo=timezone.utc)
    return (
        _linked_reading(first_time, "MJT1-A", -80.036, -80.031, 12, 2),
        _linked_reading(second_time, "MJT1-A", -80.034, -80.030, 13, 3),
        _linked_reading(second_time, "NWU2-A", -80.041, -80.030, 13, 3),
    )


def _linked_reading(
    timestamp: datetime,
    channel_id: str,
    indication_value: float,
    reference_value: float,
    indication_row: int,
    reference_row: int,
) -> LinkedTemperatureReading:
    return LinkedTemperatureReading(
        timestamp=timestamp,
        dut_channel_id=channel_id,
        indication=MeasurementReading(
            timestamp=timestamp,
            channel_id=channel_id,
            value=indication_value,
            unit="deg C",
            source=SourceLocation(
                uploaded_file_id="file-001",
                source_label="Temperature",
                row_number=indication_row,
                column_label="B",
            ),
        ),
        reference=MeasurementReading(
            timestamp=timestamp,
            channel_id="IRTD",
            value=reference_value,
            unit="deg C",
            source=SourceLocation(
                uploaded_file_id="file-002",
                source_label="Verification IRTD",
                row_number=reference_row,
                column_label="IRTD (deg C)",
            ),
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
