import sqlite3
from datetime import date, datetime, timezone

import pytest

from app.backend.domain.entities import (
    CalibrationJob,
    Client,
    Discipline,
    MeasurementMode,
)
from app.backend.domain.equipment import (
    EquipmentRange,
    EquipmentStatus,
    ReferenceEquipment,
    SelectedReferenceEquipment,
)
from app.backend.domain.workflow import WorkflowState
from app.backend.persistence.sqlite import (
    PersistenceError,
    SQLiteCalibrationJobRepository,
    SQLiteSelectedReferenceEquipmentRepository,
    initialize_schema,
)


def test_store_and_list_selected_reference_equipment_for_job():
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    SQLiteCalibrationJobRepository(connection).add(_job())

    repository = SQLiteSelectedReferenceEquipmentRepository(connection)
    repository.add(_selection())

    assert repository.list_for_job("job-001") == (_selection(),)


def test_store_duplicate_selected_reference_equipment_for_job_is_rejected():
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    SQLiteCalibrationJobRepository(connection).add(_job())
    repository = SQLiteSelectedReferenceEquipmentRepository(connection)
    repository.add(_selection())

    with pytest.raises(PersistenceError):
        repository.add(_selection())

    assert repository.list_for_job("job-001") == (_selection(),)


def test_selected_reference_equipment_for_unknown_job_is_rejected():
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)

    with pytest.raises(PersistenceError):
        SQLiteSelectedReferenceEquipmentRepository(connection).add(_selection())


def test_selected_reference_equipment_is_immutable():
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    SQLiteCalibrationJobRepository(connection).add(_job())
    SQLiteSelectedReferenceEquipmentRepository(connection).add(_selection())

    with pytest.raises(sqlite3.DatabaseError):
        connection.execute(
            """
            UPDATE selected_reference_equipment
            SET serial_number = 'CHANGED'
            WHERE job_id = 'job-001'
            """
        )

    with pytest.raises(sqlite3.DatabaseError):
        connection.execute(
            "DELETE FROM selected_reference_equipment WHERE job_id = 'job-001'"
        )


def _selection() -> SelectedReferenceEquipment:
    return SelectedReferenceEquipment(
        job_id="job-001",
        equipment=ReferenceEquipment(
            id="ref-001",
            simval_id="SIM-T-001",
            equipment_type="IRTD",
            serial_number="IRT-123",
            discipline=Discipline.TEMPERATURE,
            calibration_certificate_reference="DANAK-CAL-12345",
            calibration_due_date=date(2027, 4, 30),
            status=EquipmentStatus.ACTIVE,
            usable_range=EquipmentRange(minimum=-90.0, maximum=140.0, unit="deg C"),
            traceability_statement="Accredited calibration with SI traceability.",
        ),
        selected_by="operator-001",
        selected_at=datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
    )


def _job() -> CalibrationJob:
    return CalibrationJob(
        id="job-001",
        client=Client(name="SIMVal customer", address="Validated Road 1"),
        discipline=Discipline.TEMPERATURE,
        measurement_mode=MeasurementMode.AUTOMATIC,
        method="ValProbe RT linked XLSX/PDF workflow",
        created_by="operator-001",
        state=WorkflowState.EQUIPMENT_SELECTED,
        created_at=datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc),
    )
