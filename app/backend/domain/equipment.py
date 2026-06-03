"""Reference equipment traceability and suitability checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from math import isfinite

from app.backend.domain.entities import Discipline, DomainValidationError


class EquipmentStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    RETIRED = "retired"


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise DomainValidationError(f"{field_name} is required.")


def _require_instance(value: object, expected_type: type, field_name: str) -> None:
    if not isinstance(value, expected_type):
        raise DomainValidationError(f"{field_name} is invalid.")


def _require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise DomainValidationError(f"{field_name} must be timezone-aware.")


@dataclass(frozen=True, slots=True)
class EquipmentRange:
    minimum: float
    maximum: float
    unit: str

    def __post_init__(self) -> None:
        if not isfinite(self.minimum) or not isfinite(self.maximum):
            raise DomainValidationError("Equipment range limits must be finite.")
        if self.minimum > self.maximum:
            raise DomainValidationError("Equipment range minimum cannot exceed maximum.")
        _require_text(self.unit, "Equipment range unit")

    def contains(self, point: float, unit: str) -> bool:
        if not isfinite(point):
            return False
        return unit == self.unit and self.minimum <= point <= self.maximum


@dataclass(frozen=True, slots=True)
class ReferenceEquipment:
    id: str
    simval_id: str
    equipment_type: str
    serial_number: str
    discipline: Discipline
    calibration_certificate_reference: str
    calibration_due_date: date
    status: EquipmentStatus
    usable_range: EquipmentRange
    traceability_statement: str

    def __post_init__(self) -> None:
        _require_text(self.id, "Reference equipment id")
        _require_text(self.simval_id, "SIMVal equipment id")
        _require_text(self.equipment_type, "Reference equipment type")
        _require_text(self.serial_number, "Reference equipment serial number")
        _require_instance(self.discipline, Discipline, "Reference equipment discipline")
        _require_instance(self.status, EquipmentStatus, "Reference equipment status")
        _require_text(
            self.calibration_certificate_reference,
            "Reference equipment calibration certificate reference",
        )
        _require_text(
            self.traceability_statement,
            "Reference equipment traceability statement",
        )

    def is_due_on_or_after(self, use_date: date) -> bool:
        return self.calibration_due_date >= use_date

    def covers(self, *, point: float, unit: str, discipline: Discipline) -> bool:
        return self.discipline == discipline and self.usable_range.contains(point, unit)


def reference_equipment_blockers(
    equipment: ReferenceEquipment | None,
    *,
    use_date: date,
    point: float,
    unit: str,
    discipline: Discipline,
) -> tuple[str, ...]:
    """Return release-blocking equipment suitability issues for a measurement point."""
    if equipment is None:
        return ("missing_reference_equipment",)

    blockers: list[str] = []
    if equipment.status is not EquipmentStatus.ACTIVE:
        blockers.append("equipment_inactive")
    if not equipment.is_due_on_or_after(use_date):
        blockers.append("equipment_overdue")
    if not equipment.covers(point=point, unit=unit, discipline=discipline):
        blockers.append("equipment_out_of_range")
    return tuple(blockers)


@dataclass(frozen=True, slots=True)
class SelectedReferenceEquipment:
    job_id: str
    equipment: ReferenceEquipment
    selected_by: str
    selected_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.job_id, "Calibration job id")
        if not isinstance(self.equipment, ReferenceEquipment):
            raise DomainValidationError("Selected reference equipment is invalid.")
        _require_text(self.selected_by, "Selected reference equipment user")
        _require_timezone_aware(self.selected_at, "Selected reference equipment timestamp")
