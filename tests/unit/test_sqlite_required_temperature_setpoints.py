import sqlite3
from datetime import datetime, timezone

import pytest

from app.backend.domain.entities import (
    CalibrationJob,
    Client,
    Discipline,
    MeasurementMode,
    RequiredTemperatureSetpoint,
)
from app.backend.domain.workflow import WorkflowState
from app.backend.persistence.sqlite import (
    PersistenceError,
    SQLiteCalibrationJobRepository,
    SQLiteRequiredTemperatureSetpointRepository,
    initialize_schema,
)


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    SQLiteCalibrationJobRepository(connection).add(_job())
    return connection


def test_sqlite_required_temperature_setpoint_repository_round_trips_plan():
    connection = _connection()
    repository = SQLiteRequiredTemperatureSetpointRepository(connection)
    first = _setpoint("setpoint-001", -80.0, 0)
    second = _setpoint("setpoint-002", 0.0, 1)

    repository.add_many((second, first))

    assert repository.get("setpoint-001") == first
    assert repository.list_for_job("job-001") == (first, second)


def test_sqlite_required_temperature_setpoint_repository_rejects_unknown_job():
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    repository = SQLiteRequiredTemperatureSetpointRepository(connection)

    with pytest.raises(PersistenceError):
        repository.add_many((_setpoint("setpoint-001", -80.0, 0),))


def test_sqlite_required_temperature_setpoint_repository_rejects_duplicate_sequence():
    connection = _connection()
    repository = SQLiteRequiredTemperatureSetpointRepository(connection)
    repository.add_many((_setpoint("setpoint-001", -80.0, 0),))

    with pytest.raises(PersistenceError):
        repository.add_many((_setpoint("setpoint-002", 0.0, 0),))


def test_sqlite_required_temperature_setpoint_repository_rejects_duplicate_value():
    connection = _connection()
    repository = SQLiteRequiredTemperatureSetpointRepository(connection)
    repository.add_many((_setpoint("setpoint-001", -80.0, 0),))

    with pytest.raises(PersistenceError):
        repository.add_many((_setpoint("setpoint-002", -80.0, 1),))


def test_sqlite_required_temperature_setpoints_are_immutable_at_database_level():
    connection = _connection()
    repository = SQLiteRequiredTemperatureSetpointRepository(connection)
    setpoint = _setpoint("setpoint-001", -80.0, 0)
    repository.add_many((setpoint,))

    with pytest.raises(sqlite3.DatabaseError):
        connection.execute(
            "UPDATE required_temperature_setpoints SET setpoint = ? WHERE id = ?",
            (-90.0, "setpoint-001"),
        )
    connection.rollback()

    with pytest.raises(sqlite3.DatabaseError):
        connection.execute(
            "DELETE FROM required_temperature_setpoints WHERE id = ?",
            ("setpoint-001",),
        )
    connection.rollback()

    assert repository.get("setpoint-001") == setpoint


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
