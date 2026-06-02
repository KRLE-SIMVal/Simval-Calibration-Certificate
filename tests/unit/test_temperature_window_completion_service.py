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
    MeasurementMode,
    MeasurementReading,
    MeasurementWindow,
    RequiredTemperatureSetpoint,
    SourceLocation,
    UploadedFile,
    UploadedFileKind,
)
from app.backend.domain.workflow import WorkflowState
from app.backend.persistence.sqlite import (
    SQLiteAuditEventRepository,
    SQLiteCalibrationJobRepository,
    SQLiteDeviceUnderTestRepository,
    SQLiteMeasurementWindowRepository,
    SQLiteRequiredTemperatureSetpointRepository,
    SQLiteUserAccountRepository,
    SQLiteUserSessionRepository,
    SQLiteUploadedFileRepository,
    initialize_schema,
)
from app.backend.services.authentication import AuthenticationServiceError
from app.backend.services.measurement_windows import (
    MeasurementWindowSelectionError,
    complete_temperature_window_selection,
    complete_temperature_window_selection_for_session,
)


def _connection_with_job(
    *,
    job_state: WorkflowState = WorkflowState.DATA_ENTERED,
    user_roles: tuple[Role, ...] = (Role.OPERATOR,),
) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    SQLiteCalibrationJobRepository(connection).add(_job(job_state))
    SQLiteUploadedFileRepository(connection).add(_uploaded_file())
    SQLiteUserAccountRepository(connection).add(_user(user_roles))
    SQLiteUserSessionRepository(connection).add(_session())
    return connection


def test_complete_temperature_window_selection_transitions_when_all_duts_have_windows():
    connection = _connection_with_job()
    dut_repository = SQLiteDeviceUnderTestRepository(connection)
    window_repository = SQLiteMeasurementWindowRepository(connection)
    setpoint_repository = SQLiteRequiredTemperatureSetpointRepository(connection)
    dut_repository.add(_dut("dut-001", "MJT1", "MJT1-A"))
    dut_repository.add(_dut("dut-002", "NWU2", "NWU2-A"))
    setpoint_repository.add_many((_setpoint("setpoint-001", -80.0, 0),))
    window_repository.add(_window("window-001", "dut-001", "MJT1-A"))
    window_repository.add(_window("window-002", "dut-002", "NWU2-A"))

    result = complete_temperature_window_selection(
        connection=connection,
        job_id="job-001",
        user_id="operator-001",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 14, 30, tzinfo=timezone.utc),
    )

    assert result.job.state is WorkflowState.WINDOWS_SELECTED
    assert result.audit_event_id == 1
    assert result.audit_event.action is AuditAction.WORKFLOW_TRANSITIONED
    assert result.audit_event.previous_value == {"state": "data_entered"}
    assert result.audit_event.new_value == {"state": "windows_selected"}
    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.WINDOWS_SELECTED
    )


def test_complete_temperature_window_selection_for_session_uses_actor_for_audit():
    connection = _connection_with_job()
    dut_repository = SQLiteDeviceUnderTestRepository(connection)
    window_repository = SQLiteMeasurementWindowRepository(connection)
    setpoint_repository = SQLiteRequiredTemperatureSetpointRepository(connection)
    dut_repository.add(_dut("dut-001", "MJT1", "MJT1-A"))
    setpoint_repository.add_many((_setpoint("setpoint-001", -80.0, 0),))
    window_repository.add(_window("window-001", "dut-001", "MJT1-A"))

    result = complete_temperature_window_selection_for_session(
        connection=connection,
        session_id="session-001",
        job_id="job-001",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 14, 30, tzinfo=timezone.utc),
    )

    assert result.job.state is WorkflowState.WINDOWS_SELECTED
    assert result.audit_event.user_id == "user-001"


def test_complete_temperature_window_selection_for_session_rejects_unauthorized_actor():
    connection = _connection_with_job(user_roles=(Role.READ_ONLY,))
    dut_repository = SQLiteDeviceUnderTestRepository(connection)
    window_repository = SQLiteMeasurementWindowRepository(connection)
    setpoint_repository = SQLiteRequiredTemperatureSetpointRepository(connection)
    dut_repository.add(_dut("dut-001", "MJT1", "MJT1-A"))
    setpoint_repository.add_many((_setpoint("setpoint-001", -80.0, 0),))
    window_repository.add(_window("window-001", "dut-001", "MJT1-A"))

    with pytest.raises(AuthenticationServiceError):
        complete_temperature_window_selection_for_session(
            connection=connection,
            session_id="session-001",
            job_id="job-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 14, 30, tzinfo=timezone.utc),
        )

    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.DATA_ENTERED
    )
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    ) == ()


def test_complete_temperature_window_selection_rejects_missing_dut_window():
    connection = _connection_with_job()
    dut_repository = SQLiteDeviceUnderTestRepository(connection)
    window_repository = SQLiteMeasurementWindowRepository(connection)
    setpoint_repository = SQLiteRequiredTemperatureSetpointRepository(connection)
    dut_repository.add(_dut("dut-001", "MJT1", "MJT1-A"))
    dut_repository.add(_dut("dut-002", "NWU2", "NWU2-A"))
    setpoint_repository.add_many((_setpoint("setpoint-001", -80.0, 0),))
    window_repository.add(_window("window-001", "dut-001", "MJT1-A"))

    with pytest.raises(MeasurementWindowSelectionError) as exc_info:
        complete_temperature_window_selection(
            connection=connection,
            job_id="job-001",
            user_id="operator-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 14, 30, tzinfo=timezone.utc),
        )

    assert "dut-002@-80 deg C" in str(exc_info.value)
    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.DATA_ENTERED
    )
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    ) == ()


def test_complete_temperature_window_selection_rejects_job_without_duts():
    connection = _connection_with_job()
    SQLiteRequiredTemperatureSetpointRepository(connection).add_many(
        (_setpoint("setpoint-001", -80.0, 0),)
    )

    with pytest.raises(MeasurementWindowSelectionError):
        complete_temperature_window_selection(
            connection=connection,
            job_id="job-001",
            user_id="operator-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 14, 30, tzinfo=timezone.utc),
        )

    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.DATA_ENTERED
    )


def test_complete_temperature_window_selection_rejects_job_without_setpoint_plan():
    connection = _connection_with_job()
    dut_repository = SQLiteDeviceUnderTestRepository(connection)
    window_repository = SQLiteMeasurementWindowRepository(connection)
    dut_repository.add(_dut("dut-001", "MJT1", "MJT1-A"))
    window_repository.add(_window("window-001", "dut-001", "MJT1-A"))

    with pytest.raises(MeasurementWindowSelectionError) as exc_info:
        complete_temperature_window_selection(
            connection=connection,
            job_id="job-001",
            user_id="operator-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 14, 30, tzinfo=timezone.utc),
        )

    assert "required setpoint" in str(exc_info.value)
    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.DATA_ENTERED
    )


def test_complete_temperature_window_selection_requires_each_dut_setpoint_pair():
    connection = _connection_with_job()
    dut_repository = SQLiteDeviceUnderTestRepository(connection)
    window_repository = SQLiteMeasurementWindowRepository(connection)
    setpoint_repository = SQLiteRequiredTemperatureSetpointRepository(connection)
    dut_repository.add(_dut("dut-001", "MJT1", "MJT1-A"))
    dut_repository.add(_dut("dut-002", "NWU2", "NWU2-A"))
    setpoint_repository.add_many(
        (
            _setpoint("setpoint-001", -80.0, 0),
            _setpoint("setpoint-002", 0.0, 1),
        )
    )
    window_repository.add(_window("window-001", "dut-001", "MJT1-A", setpoint=-80.0))
    window_repository.add(_window("window-002", "dut-001", "MJT1-A", setpoint=0.0))
    window_repository.add(_window("window-003", "dut-002", "NWU2-A", setpoint=-80.0))

    with pytest.raises(MeasurementWindowSelectionError) as exc_info:
        complete_temperature_window_selection(
            connection=connection,
            job_id="job-001",
            user_id="operator-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 14, 30, tzinfo=timezone.utc),
        )

    assert "dut-002@0 deg C" in str(exc_info.value)
    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.DATA_ENTERED
    )


def test_complete_temperature_window_selection_rejects_before_data_entered():
    connection = _connection_with_job(job_state=WorkflowState.EQUIPMENT_SELECTED)
    dut_repository = SQLiteDeviceUnderTestRepository(connection)
    window_repository = SQLiteMeasurementWindowRepository(connection)
    setpoint_repository = SQLiteRequiredTemperatureSetpointRepository(connection)
    dut_repository.add(_dut("dut-001", "MJT1", "MJT1-A"))
    setpoint_repository.add_many((_setpoint("setpoint-001", -80.0, 0),))
    window_repository.add(_window("window-001", "dut-001", "MJT1-A"))

    with pytest.raises(MeasurementWindowSelectionError):
        complete_temperature_window_selection(
            connection=connection,
            job_id="job-001",
            user_id="operator-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 14, 30, tzinfo=timezone.utc),
        )

    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.EQUIPMENT_SELECTED
    )


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


def _uploaded_file() -> UploadedFile:
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


def _dut(dut_id: str, serial_number: str, channel_id: str) -> DeviceUnderTest:
    return DeviceUnderTest(
        id=dut_id,
        job_id="job-001",
        make="Kaye",
        model="ValProbe RT",
        serial_number=serial_number,
        channel_id=channel_id,
    )


def _setpoint(
    setpoint_id: str,
    setpoint: float,
    sequence_index: int,
) -> RequiredTemperatureSetpoint:
    return RequiredTemperatureSetpoint(
        id=setpoint_id,
        job_id="job-001",
        setpoint=setpoint,
        unit="deg C",
        sequence_index=sequence_index,
        created_by="operator-001",
        created_at=datetime(2026, 6, 1, 14, 15, tzinfo=timezone.utc),
    )


def _window(
    window_id: str,
    dut_id: str,
    channel_id: str,
    *,
    setpoint: float = -80.0,
) -> MeasurementWindow:
    timestamp = datetime(2026, 4, 8, 15, 45, tzinfo=timezone.utc)
    return MeasurementWindow(
        id=window_id,
        job_id="job-001",
        dut_id=dut_id,
        setpoint=setpoint,
        unit="deg C",
        selected_by="operator-001",
        selected_at=datetime(2026, 6, 1, 14, 20, tzinfo=timezone.utc),
        readings=(
            MeasurementReading(
                timestamp=timestamp,
                channel_id=channel_id,
                value=-80.036,
                unit="deg C",
                source=SourceLocation(
                    uploaded_file_id="file-001",
                    source_label="Temperature",
                    row_number=12,
                    column_label="B",
                ),
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
