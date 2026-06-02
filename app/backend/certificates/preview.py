"""Certificate preview models built from locked calculation summaries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


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
class CertificatePreview:
    job_id: str
    generated_by: str
    generated_at: datetime
    software_version: str
    calculation_engine_version: str
    constant_set_version: str
    budget_version: str
    template_version: str
    rows: tuple[CertificatePreviewRow, ...]

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
        if len(self.rows) == 0:
            raise CertificatePreviewError("Certificate preview requires result rows.")

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
