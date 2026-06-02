import sqlite3
from datetime import datetime, timezone

import pytest

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
    PersistenceError,
    SQLiteCalibrationJobRepository,
    SQLiteDeviceUnderTestRepository,
    SQLiteMeasurementWindowRepository,
    SQLiteUploadedFileRepository,
    initialize_schema,
)


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    SQLiteCalibrationJobRepository(connection).add(_job())
    return connection


def _job() -> CalibrationJob:
    return CalibrationJob(
        id="job-001",
        client=Client(name="SIMVal customer", address="Validated Road 1"),
        discipline=Discipline.TEMPERATURE,
        measurement_mode=MeasurementMode.AUTOMATIC,
        method="ValProbe RT linked XLSX/PDF workflow",
        created_by="operator-001",
        state=WorkflowState.DRAFT,
        created_at=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
    )


def _uploaded_file() -> UploadedFile:
    return UploadedFile(
        id="file-001",
        job_id="job-001",
        original_filename="Calibration_input_file_Valprobe RT Loggers.xlsx",
        checksum_sha256="A" * 64,
        file_kind=UploadedFileKind.CALIBRATION_XLSX,
        storage_uri="controlled-local://Calibration_input_file_Valprobe RT Loggers.xlsx",
        parser_version="valprobe-xlsx-contract-v1",
        uploaded_at=datetime(2026, 6, 1, 14, 5, tzinfo=timezone.utc),
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


def _measurement_window() -> MeasurementWindow:
    first = MeasurementReading(
        timestamp=datetime(2026, 4, 8, 15, 45, tzinfo=timezone.utc),
        channel_id="MJT1-A",
        value=-80.036,
        unit="deg C",
        source=SourceLocation(
            uploaded_file_id="file-001",
            source_label="Temperature",
            row_number=12,
            column_label="B",
        ),
    )
    second = MeasurementReading(
        timestamp=datetime(2026, 4, 8, 15, 46, tzinfo=timezone.utc),
        channel_id="MJT1-A",
        value=-80.034,
        unit="deg C",
        source=SourceLocation(
            uploaded_file_id="file-001",
            source_label="Temperature",
            row_number=13,
            column_label="B",
        ),
        quality_flag="stable-window",
    )
    return MeasurementWindow(
        id="window-001",
        job_id="job-001",
        dut_id="dut-001",
        setpoint=-80.0,
        unit="deg C",
        selected_by="operator-001",
        selected_at=datetime(2026, 6, 1, 14, 10, tzinfo=timezone.utc),
        readings=(first, second),
    )


def test_sqlite_uploaded_file_repository_round_trips_file_evidence():
    connection = _connection()
    repository = SQLiteUploadedFileRepository(connection)
    uploaded_file = _uploaded_file()

    repository.add(uploaded_file)

    loaded = repository.get("file-001")
    assert loaded == uploaded_file
    assert loaded.checksum_sha256 == "a" * 64


def test_sqlite_uploaded_file_repository_rejects_unknown_job():
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    repository = SQLiteUploadedFileRepository(connection)

    with pytest.raises(PersistenceError):
        repository.add(_uploaded_file())


def test_sqlite_dut_repository_round_trips_and_lists_for_job():
    connection = _connection()
    repository = SQLiteDeviceUnderTestRepository(connection)
    first = _dut()
    second = DeviceUnderTest(
        id="dut-002",
        job_id="job-001",
        make="Kaye",
        model="ValProbe RT",
        serial_number="NWU2",
        channel_id="NWU2-A",
    )

    repository.add(second)
    repository.add(first)

    assert repository.get("dut-001") == first
    assert repository.list_for_job("job-001") == (first, second)


def test_sqlite_dut_repository_rejects_duplicate_identity_within_job():
    connection = _connection()
    repository = SQLiteDeviceUnderTestRepository(connection)
    repository.add(_dut())

    with pytest.raises(PersistenceError):
        repository.add(
            DeviceUnderTest(
                id="dut-002",
                job_id="job-001",
                make="Kaye",
                model="ValProbe RT",
                serial_number="MJT1",
                channel_id="MJT1-A",
            )
        )


def test_sqlite_measurement_window_repository_round_trips_reading_sources():
    connection = _connection()
    SQLiteUploadedFileRepository(connection).add(_uploaded_file())
    SQLiteDeviceUnderTestRepository(connection).add(_dut())
    repository = SQLiteMeasurementWindowRepository(connection)
    window = _measurement_window()

    repository.add(window)

    loaded = repository.get("window-001")
    assert loaded == window
    assert loaded.readings[0].source.uploaded_file_id == "file-001"
    assert loaded.readings[0].source.row_number == 12
    assert loaded.readings[1].quality_flag == "stable-window"
    assert repository.list_for_job("job-001") == (window,)


def test_sqlite_measurement_window_repository_rejects_unknown_source_file():
    connection = _connection()
    SQLiteDeviceUnderTestRepository(connection).add(_dut())
    repository = SQLiteMeasurementWindowRepository(connection)

    with pytest.raises(PersistenceError):
        repository.add(_measurement_window())


def test_sqlite_measurement_window_repository_rejects_unknown_dut():
    connection = _connection()
    SQLiteUploadedFileRepository(connection).add(_uploaded_file())
    repository = SQLiteMeasurementWindowRepository(connection)

    with pytest.raises(PersistenceError):
        repository.add(_measurement_window())
