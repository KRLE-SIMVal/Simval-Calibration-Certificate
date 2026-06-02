import sqlite3
from datetime import datetime, timezone

import pytest

from app.backend.domain.entities import (
    CalibrationJob,
    Client,
    Discipline,
    MeasurementMode,
    MeasurementReading,
    SourceLocation,
    UploadedFile,
    UploadedFileKind,
)
from app.backend.domain.workflow import WorkflowState
from app.backend.imports.temperature_alignment import LinkedTemperatureReading
from app.backend.persistence.sqlite import (
    PersistenceError,
    SQLiteCalibrationJobRepository,
    SQLiteLinkedTemperatureReadingRepository,
    SQLiteUploadedFileRepository,
    initialize_schema,
)


def _connection_with_files() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    SQLiteCalibrationJobRepository(connection).add(_job())
    file_repository = SQLiteUploadedFileRepository(connection)
    file_repository.add(_calibration_file())
    file_repository.add(_verification_file())
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


def _linked_readings() -> tuple[LinkedTemperatureReading, ...]:
    first_time = datetime(2026, 4, 8, 15, 45, tzinfo=timezone.utc)
    second_time = datetime(2026, 4, 8, 15, 46, tzinfo=timezone.utc)
    return (
        _linked_reading(first_time, "MJT1-A", -80.036, -80.031, 12, 2),
        _linked_reading(second_time, "MJT1-A", -80.034, -80.030, 13, 3),
    )


def test_sqlite_linked_temperature_repository_round_trips_linked_readings():
    connection = _connection_with_files()
    repository = SQLiteLinkedTemperatureReadingRepository(connection)
    linked_readings = _linked_readings()

    repository.add_many(job_id="job-001", linked_readings=linked_readings)

    assert repository.list_for_job("job-001") == linked_readings


def test_sqlite_linked_temperature_repository_rejects_unknown_source_file():
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    SQLiteCalibrationJobRepository(connection).add(_job())
    SQLiteUploadedFileRepository(connection).add(_calibration_file())
    repository = SQLiteLinkedTemperatureReadingRepository(connection)

    with pytest.raises(PersistenceError):
        repository.add_many(job_id="job-001", linked_readings=_linked_readings())


def test_sqlite_linked_temperature_readings_are_immutable_at_database_level():
    connection = _connection_with_files()
    repository = SQLiteLinkedTemperatureReadingRepository(connection)
    repository.add_many(job_id="job-001", linked_readings=_linked_readings())

    with pytest.raises(sqlite3.DatabaseError):
        connection.execute(
            "UPDATE linked_temperature_readings SET indication_value = ? "
            "WHERE job_id = ?",
            (-80.0, "job-001"),
        )
    connection.rollback()

    with pytest.raises(sqlite3.DatabaseError):
        connection.execute(
            "DELETE FROM linked_temperature_readings WHERE job_id = ?",
            ("job-001",),
        )
    connection.rollback()

    assert repository.list_for_job("job-001") == _linked_readings()


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
