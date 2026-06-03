"""Controlled certificate metadata used for preview and rendering."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


class CertificateMetadataError(ValueError):
    """Raised when certificate metadata is incomplete or inconsistent."""


@dataclass(frozen=True, slots=True)
class CertificateMetadata:
    job_id: str
    certificate_date: date
    calibration_date: date
    receipt_date: date
    task_number: str
    purchase_order: str
    client_name: str
    client_address: str
    procedure: str
    place: str
    approved_by_label: str
    remarks: str
    traceability_statement: str
    uncertainty_statement: str
    ambient_conditions: str
    temperature_scale: str
    recorded_by: str
    recorded_at: datetime

    def __post_init__(self) -> None:
        for field_name in (
            "job_id",
            "task_number",
            "purchase_order",
            "client_name",
            "client_address",
            "procedure",
            "place",
            "approved_by_label",
            "remarks",
            "traceability_statement",
            "uncertainty_statement",
            "ambient_conditions",
            "temperature_scale",
            "recorded_by",
        ):
            _require_text(getattr(self, field_name), field_name)
        for field_name in (
            "certificate_date",
            "calibration_date",
            "receipt_date",
        ):
            _require_date(getattr(self, field_name), field_name)
        if self.receipt_date > self.calibration_date:
            raise CertificateMetadataError(
                "Receipt date cannot be after calibration date."
            )
        if self.calibration_date > self.certificate_date:
            raise CertificateMetadataError(
                "Calibration date cannot be after certificate date."
            )
        _require_timezone_aware(self.recorded_at, "Metadata recorded_at")


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise CertificateMetadataError(f"{field_name} is required.")


def _require_date(value: date, field_name: str) -> None:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise CertificateMetadataError(f"{field_name} must be a date.")


def _require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CertificateMetadataError(f"{field_name} must be timezone-aware.")
