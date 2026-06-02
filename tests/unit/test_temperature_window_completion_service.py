import sqlite3
from datetime import datetime, timezone

import pytest

from app.backend.audit.events import AuditAction
from app.backend.domain.entities import (
    CalibrationJob,
    Client,
    DeviceUnderTest,
    Discipline,
    MeasurementMode,
    MeasurementReading,
    MeasurementWindow,
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
    SQLiteUploadedFileRepository,
    initialize_schema,
)
from app.backend.services.measurement_windows import (
    MeasurementWindowSelectionError,
    complete_temperature_window_selection,
)


def _connection_with_job(
    *,
    job_state: WorkflowState = WorkflowState.DATA_ENTERED,
) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    SQLiteCalibrationJobRepository(connection).add(_job(job_state))
    SQLiteUploadedFileRepository(connection).add(_uploaded_file())
    return connection


def test_complete_temperature_window_selection_transitions_when_all_duts_have_windows():
    connection = _connection_with_job()
    dut_repository = SQLiteDeviceUnderTestRepository(connection)
    window_repository = SQLiteMeasurementWindowRepository(connection)
    dut_repository.add(_dut("dut-001", "MJT1", "MJT1-A"))
    dut_repository.add(_dut("dut-002", "NWU2", "NWU2-A"))
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


def test_complete_temperature_window_selection_rejects_missing_dut_window():
    connection = _connection_with_job()
    dut_repository = SQLiteDeviceUnderTestRepository(connection)
    window_repository = SQLiteMeasurementWindowRepository(connection)
    dut_repository.add(_dut("dut-001", "MJT1", "MJT1-A"))
    dut_repository.add(_dut("dut-002", "NWU2", "NWU2-A"))
    window_repository.add(_window("window-001", "dut-001", "MJT1-A"))

    with pytest.raises(MeasurementWindowSelectionError) as exc_info:
        complete_temperature_window_selection(
            connection=connection,
            job_id="job-001",
            user_id="operator-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 14, 30, tzinfo=timezone.utc),
        )

    assert "dut-002" in str(exc_info.value)
    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.DATA_ENTERED
    )
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    ) == ()


def test_complete_temperature_window_selection_rejects_job_without_duts():
    connection = _connection_with_job()

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


def test_complete_temperature_window_selection_rejects_before_data_entered():
    connection = _connection_with_job(job_state=WorkflowState.EQUIPMENT_SELECTED)
    dut_repository = SQLiteDeviceUnderTestRepository(connection)
    window_repository = SQLiteMeasurementWindowRepository(connection)
    dut_repository.add(_dut("dut-001", "MJT1", "MJT1-A"))
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


def _window(window_id: str, dut_id: str, channel_id: str) -> MeasurementWindow:
    timestamp = datetime(2026, 4, 8, 15, 45, tzinfo=timezone.utc)
    return MeasurementWindow(
        id=window_id,
        job_id="job-001",
        dut_id=dut_id,
        setpoint=-80.0,
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
