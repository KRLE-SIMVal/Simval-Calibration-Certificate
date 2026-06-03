import sqlite3
from datetime import date, datetime, timezone

import pytest

from app.backend.certificates.metadata import CertificateMetadata
from app.backend.domain.entities import (
    CalibrationJob,
    Client,
    Discipline,
    MeasurementMode,
)
from app.backend.domain.workflow import WorkflowState
from app.backend.persistence.sqlite import (
    PersistenceError,
    SQLiteCalibrationJobRepository,
    SQLiteCertificateMetadataRepository,
    initialize_schema,
)


def test_sqlite_certificate_metadata_repository_round_trips_metadata():
    connection = _connection_with_job()
    repository = SQLiteCertificateMetadataRepository(connection)
    metadata = _metadata()

    repository.add(metadata)

    assert repository.get("job-001") == metadata


def test_sqlite_certificate_metadata_repository_rejects_unknown_job():
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)

    with pytest.raises(PersistenceError):
        SQLiteCertificateMetadataRepository(connection).add(_metadata())


def test_sqlite_certificate_metadata_repository_rejects_duplicate_job_metadata():
    connection = _connection_with_job()
    repository = SQLiteCertificateMetadataRepository(connection)
    repository.add(_metadata())

    with pytest.raises(PersistenceError):
        repository.add(_metadata(recorded_by="operator-002"))


def test_sqlite_certificate_metadata_rows_are_immutable_at_database_level():
    connection = _connection_with_job()
    repository = SQLiteCertificateMetadataRepository(connection)
    repository.add(_metadata())

    with pytest.raises(sqlite3.DatabaseError):
        connection.execute(
            "UPDATE certificate_metadata SET client_name = ? WHERE job_id = ?",
            ("Changed customer", "job-001"),
        )
    connection.rollback()

    with pytest.raises(sqlite3.DatabaseError):
        connection.execute(
            "DELETE FROM certificate_metadata WHERE job_id = ?",
            ("job-001",),
        )
    connection.rollback()

    assert repository.get("job-001") == _metadata()


def _connection_with_job() -> sqlite3.Connection:
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
            state=WorkflowState.DRAFT,
            created_at=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
        )
    )
    return connection


def _metadata(**overrides) -> CertificateMetadata:
    values = {
        "job_id": "job-001",
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
        "traceability_statement": (
            "Measurements are metrologically traceable through calibrated "
            "reference equipment under ILAC/EA/DANAK principles."
        ),
        "uncertainty_statement": (
            "The reported expanded uncertainty is based on standard uncertainty "
            "multiplied by coverage factor k=2."
        ),
        "ambient_conditions": "Room temperature 23 +/- 2 deg C.",
        "temperature_scale": "ITS-90",
        "recorded_by": "operator-001",
        "recorded_at": datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
    }
    values.update(overrides)
    return CertificateMetadata(**values)
