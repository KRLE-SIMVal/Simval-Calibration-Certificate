from datetime import date

import pytest

from app.backend.domain.equipment import (
    EquipmentRange,
    EquipmentStatus,
    ReferenceEquipment,
    reference_equipment_blockers,
)
from app.backend.domain.entities import Discipline, DomainValidationError


def _active_temperature_reference() -> ReferenceEquipment:
    return ReferenceEquipment(
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
    )


def test_reference_equipment_requires_traceability_metadata():
    equipment = _active_temperature_reference()

    assert equipment.simval_id == "SIM-T-001"
    assert equipment.calibration_certificate_reference == "DANAK-CAL-12345"
    assert equipment.usable_range.contains(-80.0, "deg C")


def test_reference_equipment_rejects_missing_certificate_reference():
    with pytest.raises(DomainValidationError):
        ReferenceEquipment(
            id="ref-001",
            simval_id="SIM-T-001",
            equipment_type="IRTD",
            serial_number="IRT-123",
            discipline=Discipline.TEMPERATURE,
            calibration_certificate_reference=" ",
            calibration_due_date=date(2027, 4, 30),
            status=EquipmentStatus.ACTIVE,
            usable_range=EquipmentRange(minimum=-90.0, maximum=140.0, unit="deg C"),
            traceability_statement="Accredited calibration with SI traceability.",
        )


def test_reference_equipment_rejects_invalid_status():
    with pytest.raises(DomainValidationError):
        ReferenceEquipment(
            id="ref-001",
            simval_id="SIM-T-001",
            equipment_type="IRTD",
            serial_number="IRT-123",
            discipline=Discipline.TEMPERATURE,
            calibration_certificate_reference="DANAK-CAL-12345",
            calibration_due_date=date(2027, 4, 30),
            status="active",
            usable_range=EquipmentRange(minimum=-90.0, maximum=140.0, unit="deg C"),
            traceability_statement="Accredited calibration with SI traceability.",
        )


def test_equipment_range_rejects_inverted_range():
    with pytest.raises(DomainValidationError):
        EquipmentRange(minimum=10.0, maximum=-10.0, unit="deg C")


def test_reference_equipment_accepts_due_date_on_use_date():
    blockers = reference_equipment_blockers(
        _active_temperature_reference(),
        use_date=date(2027, 4, 30),
        point=-80.0,
        unit="deg C",
        discipline=Discipline.TEMPERATURE,
    )

    assert blockers == ()


def test_missing_reference_equipment_blocks_release():
    blockers = reference_equipment_blockers(
        None,
        use_date=date(2026, 4, 8),
        point=-80.0,
        unit="deg C",
        discipline=Discipline.TEMPERATURE,
    )

    assert blockers == ("missing_reference_equipment",)


def test_overdue_reference_equipment_blocks_release():
    equipment = _active_temperature_reference()

    blockers = reference_equipment_blockers(
        equipment,
        use_date=date(2027, 5, 1),
        point=-80.0,
        unit="deg C",
        discipline=Discipline.TEMPERATURE,
    )

    assert blockers == ("equipment_overdue",)


def test_inactive_reference_equipment_blocks_release():
    equipment = ReferenceEquipment(
        id="ref-001",
        simval_id="SIM-T-001",
        equipment_type="IRTD",
        serial_number="IRT-123",
        discipline=Discipline.TEMPERATURE,
        calibration_certificate_reference="DANAK-CAL-12345",
        calibration_due_date=date(2027, 4, 30),
        status=EquipmentStatus.INACTIVE,
        usable_range=EquipmentRange(minimum=-90.0, maximum=140.0, unit="deg C"),
        traceability_statement="Accredited calibration with SI traceability.",
    )

    blockers = reference_equipment_blockers(
        equipment,
        use_date=date(2026, 4, 8),
        point=-80.0,
        unit="deg C",
        discipline=Discipline.TEMPERATURE,
    )

    assert blockers == ("equipment_inactive",)


@pytest.mark.parametrize(
    ("point", "unit", "discipline"),
    [
        (-90.1, "deg C", Discipline.TEMPERATURE),
        (140.1, "deg C", Discipline.TEMPERATURE),
        (-80.0, "K", Discipline.TEMPERATURE),
        (-80.0, "deg C", Discipline.PRESSURE),
    ],
)
def test_reference_equipment_outside_scope_blocks_release(point, unit, discipline):
    blockers = reference_equipment_blockers(
        _active_temperature_reference(),
        use_date=date(2026, 4, 8),
        point=point,
        unit=unit,
        discipline=discipline,
    )

    assert blockers == ("equipment_out_of_range",)


def test_reference_equipment_reports_multiple_blockers_when_needed():
    equipment = ReferenceEquipment(
        id="ref-001",
        simval_id="SIM-T-001",
        equipment_type="IRTD",
        serial_number="IRT-123",
        discipline=Discipline.TEMPERATURE,
        calibration_certificate_reference="DANAK-CAL-12345",
        calibration_due_date=date(2026, 1, 1),
        status=EquipmentStatus.INACTIVE,
        usable_range=EquipmentRange(minimum=-90.0, maximum=140.0, unit="deg C"),
        traceability_statement="Accredited calibration with SI traceability.",
    )

    blockers = reference_equipment_blockers(
        equipment,
        use_date=date(2026, 4, 8),
        point=200.0,
        unit="deg C",
        discipline=Discipline.TEMPERATURE,
    )

    assert blockers == (
        "equipment_inactive",
        "equipment_overdue",
        "equipment_out_of_range",
    )
