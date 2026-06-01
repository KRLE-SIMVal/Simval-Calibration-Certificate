"""Auditable calculation summary models for measurement points."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.calculation_engine.cmc.models import apply_cmc_floor
from app.calculation_engine.common.results import calculate_error_of_indication
from app.calculation_engine.common.rounding import (
    RoundingError,
    round_expanded_uncertainty,
    round_result_to_uncertainty,
)


class CalculationSummaryError(ValueError):
    """Raised when a calculation summary is incomplete or inconsistent."""


@dataclass(frozen=True, slots=True)
class MeasurementPointSummary:
    point_id: str
    job_id: str
    dut_id: str
    measurement_window_id: str
    reference: float
    indication: float
    unit: str
    error_of_indication: float
    calculated_expanded_uncertainty: Decimal
    cmc_floor: Decimal
    reported_expanded_uncertainty: Decimal
    display_error_of_indication: Decimal
    calculation_engine_version: str
    constant_set_version: str
    budget_version: str

    def __post_init__(self) -> None:
        for field_name in (
            "point_id",
            "job_id",
            "dut_id",
            "measurement_window_id",
            "unit",
            "calculation_engine_version",
            "constant_set_version",
            "budget_version",
        ):
            _require_text(getattr(self, field_name), field_name)
        _require_non_negative_decimal(
            self.calculated_expanded_uncertainty,
            "calculated_expanded_uncertainty",
        )
        _require_non_negative_decimal(self.cmc_floor, "cmc_floor")
        _require_non_negative_decimal(
            self.reported_expanded_uncertainty,
            "reported_expanded_uncertainty",
        )
        if self.reported_expanded_uncertainty < self.cmc_floor:
            raise CalculationSummaryError(
                "Reported expanded uncertainty cannot be below CMC floor."
            )

    @property
    def cmc_floor_applied(self) -> bool:
        return self.cmc_floor > self.calculated_expanded_uncertainty


def build_measurement_point_summary(
    *,
    point_id: str,
    job_id: str,
    dut_id: str,
    measurement_window_id: str,
    reference: float,
    indication: float,
    unit: str,
    calculated_expanded_uncertainty: Decimal,
    cmc_floor: Decimal,
    calculation_engine_version: str,
    constant_set_version: str,
    budget_version: str,
) -> MeasurementPointSummary:
    """Build a reproducible measurement-point summary using approved common rules."""
    try:
        error = calculate_error_of_indication(reference, indication)
        floored_uncertainty = Decimal(
            str(
                apply_cmc_floor(
                    float(calculated_expanded_uncertainty),
                    float(cmc_floor),
                )
            )
        )
        rounded_uncertainty = round_expanded_uncertainty(
            floored_uncertainty,
            significant_digits=2,
            cmc_floor=cmc_floor,
        )
        display_error = round_result_to_uncertainty(
            Decimal(str(error)),
            rounded_uncertainty,
        )
    except (RoundingError, ValueError) as exc:
        raise CalculationSummaryError(str(exc)) from exc

    return MeasurementPointSummary(
        point_id=point_id,
        job_id=job_id,
        dut_id=dut_id,
        measurement_window_id=measurement_window_id,
        reference=reference,
        indication=indication,
        unit=unit,
        error_of_indication=error,
        calculated_expanded_uncertainty=calculated_expanded_uncertainty,
        cmc_floor=cmc_floor,
        reported_expanded_uncertainty=rounded_uncertainty.value,
        display_error_of_indication=display_error,
        calculation_engine_version=calculation_engine_version,
        constant_set_version=constant_set_version,
        budget_version=budget_version,
    )


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise CalculationSummaryError(f"{field_name} is required.")


def _require_non_negative_decimal(value: Decimal, field_name: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise CalculationSummaryError(f"{field_name} must be a finite Decimal >= 0.")
