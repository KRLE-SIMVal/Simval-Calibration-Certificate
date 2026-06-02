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
from app.backend.persistence.sqlite import (
    PersistenceError,
    SQLiteCalibrationJobRepository,
    SQLiteParsedReadingRepository,
    SQLiteUploadedFileRepository,
    initialize_schema,
)


def _connection_with_uploaded_file() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    SQLiteCalibrationJobRepository(connection).add(_job())
    SQLiteUploadedFileRepository(connection).add(_uploaded_file())
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
        original_filename="sanitized-valprobe.xlsx",
        checksum_sha256="a" * 64,
        file_kind=UploadedFileKind.CALIBRATION_XLSX,
        storage_uri="controlled-local://sanitized-valprobe.xlsx",
        parser_version="valprobe-xlsx-parser-v1",
        uploaded_at=datetime(2026, 6, 1, 14, 5, tzinfo=timezone.utc),
    )


def _readings() -> tuple[MeasurementReading, ...]:
    return (
        MeasurementReading(
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
        ),
        MeasurementReading(
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
            quality_flag="parser-warning-reviewed",
        ),
    )


def test_sqlite_parsed_reading_repository_round_trips_raw_readings():
    connection = _connection_with_uploaded_file()
    repository = SQLiteParsedReadingRepository(connection)
    readings = _readings()

    repository.add_many(readings)

    assert repository.list_for_uploaded_file("file-001") == readings


def test_sqlite_parsed_reading_repository_rejects_unknown_uploaded_file():
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    repository = SQLiteParsedReadingRepository(connection)

    with pytest.raises(PersistenceError):
        repository.add_many(_readings())


def test_sqlite_parsed_readings_are_immutable_at_database_level():
    connection = _connection_with_uploaded_file()
    repository = SQLiteParsedReadingRepository(connection)
    repository.add_many(_readings())

    with pytest.raises(sqlite3.DatabaseError):
        connection.execute(
            "UPDATE parsed_readings SET value = ? WHERE uploaded_file_id = ?",
            (-80.0, "file-001"),
        )
    connection.rollback()

    with pytest.raises(sqlite3.DatabaseError):
        connection.execute(
            "DELETE FROM parsed_readings WHERE uploaded_file_id = ?",
            ("file-001",),
        )
    connection.rollback()

    assert repository.list_for_uploaded_file("file-001") == _readings()
