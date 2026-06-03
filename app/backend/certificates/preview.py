"""Certificate preview models built from locked calculation summaries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from math import isfinite

from app.backend.certificates.metadata import CertificateMetadata


class CertificatePreviewError(ValueError):
    """Raised when a certificate preview would be incomplete or inconsistent."""


@dataclass(frozen=True, slots=True)
class CertificatePreviewRow:
    point_id: str
    dut_id: str
    measurement_window_id: str
    reference: float
    indication: float
    error_of_indication: float
    display_error_of_indication: Decimal
    reported_expanded_uncertainty: Decimal
    unit: str

    def __post_init__(self) -> None:
        for field_name in (
            "point_id",
            "dut_id",
            "measurement_window_id",
            "unit",
        ):
            _require_text(getattr(self, field_name), field_name)
        _require_decimal(
            self.display_error_of_indication,
            "display_error_of_indication",
        )
        _require_decimal(
            self.reported_expanded_uncertainty,
            "reported_expanded_uncertainty",
        )


@dataclass(frozen=True, slots=True)
class CertificatePreviewDut:
    dut_id: str
    make: str
    model: str
    serial_number: str
    channel_id: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "dut_id",
            "make",
            "model",
            "serial_number",
        ):
            _require_text(getattr(self, field_name), field_name)
        if self.channel_id is not None:
            _require_text(self.channel_id, "channel_id")

    @property
    def display_name(self) -> str:
        base = f"{self.make} {self.model} SN: {self.serial_number}"
        if self.channel_id is None:
            return base
        return f"{base} Channel: {self.channel_id}"


@dataclass(frozen=True, slots=True)
class CertificatePreviewReferenceEquipment:
    equipment_id: str
    simval_id: str
    equipment_type: str
    serial_number: str
    calibration_certificate_reference: str
    calibration_due_date: date
    range_minimum: float
    range_maximum: float
    range_unit: str
    traceability_statement: str

    def __post_init__(self) -> None:
        for field_name in (
            "equipment_id",
            "simval_id",
            "equipment_type",
            "serial_number",
            "calibration_certificate_reference",
            "range_unit",
            "traceability_statement",
        ):
            _require_text(getattr(self, field_name), field_name)
        if not isinstance(self.calibration_due_date, date) or isinstance(
            self.calibration_due_date,
            datetime,
        ):
            raise CertificatePreviewError(
                "Reference equipment calibration_due_date must be a date."
            )
        if not isfinite(self.range_minimum) or not isfinite(self.range_maximum):
            raise CertificatePreviewError(
                "Reference equipment range limits must be finite."
            )
        if self.range_minimum > self.range_maximum:
            raise CertificatePreviewError(
                "Reference equipment range minimum cannot exceed maximum."
            )

    @property
    def range_text(self) -> str:
        return (
            f"{self.range_minimum:g} to {self.range_maximum:g} "
            f"{self.range_unit}"
        )


@dataclass(frozen=True, slots=True)
class CertificatePreview:
    job_id: str
    generated_by: str
    generated_at: datetime
    software_version: str
    calculation_engine_version: str
    constant_set_version: str
    budget_version: str
    template_version: str
    metadata: CertificateMetadata
    duts: tuple[CertificatePreviewDut, ...]
    reference_equipment: tuple[CertificatePreviewReferenceEquipment, ...]
    rows: tuple[CertificatePreviewRow, ...]
    accreditation_mark_allowed: bool = True

    def __post_init__(self) -> None:
        for field_name in (
            "job_id",
            "generated_by",
            "software_version",
            "calculation_engine_version",
            "constant_set_version",
            "budget_version",
            "template_version",
        ):
            _require_text(getattr(self, field_name), field_name)
        _require_timezone_aware(self.generated_at, "Preview generated_at")
        if not isinstance(self.metadata, CertificateMetadata):
            raise CertificatePreviewError("Certificate metadata is invalid.")
        if self.metadata.job_id != self.job_id:
            raise CertificatePreviewError("Certificate metadata must belong to the job.")
        for dut in self.duts:
            if not isinstance(dut, CertificatePreviewDut):
                raise CertificatePreviewError("Certificate DUT metadata is invalid.")
        if len(self.reference_equipment) == 0:
            raise CertificatePreviewError(
                "Certificate preview requires reference equipment."
            )
        for equipment in self.reference_equipment:
            if not isinstance(equipment, CertificatePreviewReferenceEquipment):
                raise CertificatePreviewError(
                    "Certificate reference equipment is invalid."
                )
        if len(self.rows) == 0:
            raise CertificatePreviewError("Certificate preview requires result rows.")
        if not isinstance(self.accreditation_mark_allowed, bool):
            raise CertificatePreviewError(
                "Certificate accreditation mark decision must be a bool."
            )
        dut_ids = {dut.dut_id for dut in self.duts}
        missing_dut_ids = sorted({row.dut_id for row in self.rows} - dut_ids)
        if missing_dut_ids:
            raise CertificatePreviewError(
                "Certificate preview missing DUT metadata for: "
                + ", ".join(missing_dut_ids)
            )

    @property
    def summary_ids(self) -> tuple[str, ...]:
        return tuple(row.point_id for row in self.rows)


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise CertificatePreviewError(f"{field_name} is required.")


def _require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CertificatePreviewError(f"{field_name} must be timezone-aware.")


def _require_decimal(value: Decimal, field_name: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise CertificatePreviewError(f"{field_name} must be a finite Decimal.")
