"""Pressure certificate result calculations."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from math import isfinite

from app.calculation_engine.common.statistics import (
    StatisticsError,
    mean,
    standard_uncertainty_of_mean,
)
from app.calculation_engine.common.summary import (
    CalculationSummaryError,
    MeasurementPointSummary,
    build_measurement_point_summary,
)
from app.calculation_engine.common.uncertainty import (
    UncertaintyContribution,
    UncertaintyError,
    combine_standard_uncertainties,
    expand_uncertainty,
    expanded_to_standard,
    resolution_to_standard,
)


class PressureCalculationError(ValueError):
    """Raised when a pressure point cannot be calculated safely."""


class PressureKind(StrEnum):
    GAUGE = "gauge"
    ABSOLUTE = "absolute"
    DIFFERENTIAL = "differential"


@dataclass(frozen=True, slots=True)
class AdditionalStandardUncertainty:
    name: str
    standard_uncertainty: float
    sensitivity_coefficient: float = 1.0

    def __post_init__(self) -> None:
        _require_text(self.name, "Additional uncertainty name")
        _require_non_negative_finite(
            self.standard_uncertainty,
            "Additional standard uncertainty",
        )
        if not isfinite(self.sensitivity_coefficient):
            raise PressureCalculationError(
                "Additional uncertainty sensitivity coefficient must be finite."
            )


@dataclass(frozen=True, slots=True)
class PressurePointUncertaintyInput:
    setpoint: float
    unit: str
    pressure_kind: PressureKind
    cmc_floor: Decimal
    reference_expanded_uncertainty: float
    reference_coverage_factor: float = 2.0
    dut_resolution: float = 0.0
    barometer_expanded_uncertainty: float = 0.0
    barometer_coverage_factor: float = 2.0
    coverage_factor: float = 2.0
    additional_standard_uncertainties: tuple[AdditionalStandardUncertainty, ...] = field(
        default_factory=tuple
    )

    def __post_init__(self) -> None:
        if not isfinite(self.setpoint):
            raise PressureCalculationError("Setpoint must be finite.")
        _require_text(self.unit, "Pressure unit")
        if not isinstance(self.pressure_kind, PressureKind):
            raise PressureCalculationError("Pressure kind must be controlled.")
        if (
            not isinstance(self.cmc_floor, Decimal)
            or not self.cmc_floor.is_finite()
            or self.cmc_floor < 0
        ):
            raise PressureCalculationError("CMC floor must be a finite Decimal >= 0.")
        _require_non_negative_finite(
            self.reference_expanded_uncertainty,
            "Reference expanded uncertainty",
        )
        _require_positive_finite(
            self.reference_coverage_factor,
            "Reference coverage factor",
        )
        _require_non_negative_finite(self.dut_resolution, "DUT resolution")
        _require_non_negative_finite(
            self.barometer_expanded_uncertainty,
            "Barometer expanded uncertainty",
        )
        _require_positive_finite(
            self.barometer_coverage_factor,
            "Barometer coverage factor",
        )
        _require_positive_finite(self.coverage_factor, "Coverage factor")
        if (
            self.pressure_kind is not PressureKind.ABSOLUTE
            and self.barometer_expanded_uncertainty > 0
        ):
            raise PressureCalculationError(
                "Barometer uncertainty applies only to absolute pressure."
            )


@dataclass(frozen=True, slots=True)
class PressureContributionSummary:
    name: str
    standard_uncertainty: float
    sensitivity_coefficient: float
    effective_standard_uncertainty: float


@dataclass(frozen=True, slots=True)
class PressurePointCalculation:
    summary: MeasurementPointSummary
    contributions: tuple[PressureContributionSummary, ...]
    combined_standard_uncertainty: float
    calculated_expanded_uncertainty: Decimal


def calculate_manual_pressure_point(
    *,
    point_id: str,
    job_id: str,
    dut_id: str,
    measurement_window_id: str,
    reference_pressure: float,
    indication_values: tuple[float, ...],
    uncertainty_input: PressurePointUncertaintyInput,
    calculation_engine_version: str,
    constant_set_version: str,
    budget_version: str,
) -> PressurePointCalculation:
    """Calculate one manual pressure certificate point.

    Manual pressure uses the supplied reference pressure and the arithmetic mean
    of entered DUT indications. If the method records up/down values, both are
    supplied as indication values and averaged before error of indication.
    """
    _require_finite(reference_pressure, "Reference pressure")
    _require_at_least_one(indication_values, "Manual pressure indication values")

    try:
        indication = mean(indication_values)
        contributions = _base_pressure_contributions(uncertainty_input)
        return _build_pressure_result(
            point_id=point_id,
            job_id=job_id,
            dut_id=dut_id,
            measurement_window_id=measurement_window_id,
            reference=reference_pressure,
            indication=indication,
            uncertainty_input=uncertainty_input,
            contributions=contributions,
            calculation_engine_version=calculation_engine_version,
            constant_set_version=constant_set_version,
            budget_version=budget_version,
        )
    except (StatisticsError, UncertaintyError, CalculationSummaryError) as exc:
        raise PressureCalculationError(str(exc)) from exc


def calculate_automatic_pressure_point(
    *,
    point_id: str,
    job_id: str,
    dut_id: str,
    measurement_window_id: str,
    reference_values: tuple[float, ...],
    indication_values: tuple[float, ...],
    uncertainty_input: PressurePointUncertaintyInput,
    calculation_engine_version: str,
    constant_set_version: str,
    budget_version: str,
) -> PressurePointCalculation:
    """Calculate one automatic pressure certificate point from paired readings."""
    _require_equal_point_lengths(reference_values, indication_values)
    if len(reference_values) < 2:
        raise PressureCalculationError(
            "Automatic pressure calculation requires at least two linked readings."
        )

    try:
        reference = mean(reference_values)
        indication = mean(indication_values)
        contributions = (
            *_base_pressure_contributions(uncertainty_input),
            UncertaintyContribution(
                name="reference_pressure_repeatability",
                standard_uncertainty=standard_uncertainty_of_mean(reference_values),
            ),
            UncertaintyContribution(
                name="dut_indication_repeatability",
                standard_uncertainty=standard_uncertainty_of_mean(indication_values),
            ),
        )
        return _build_pressure_result(
            point_id=point_id,
            job_id=job_id,
            dut_id=dut_id,
            measurement_window_id=measurement_window_id,
            reference=reference,
            indication=indication,
            uncertainty_input=uncertainty_input,
            contributions=contributions,
            calculation_engine_version=calculation_engine_version,
            constant_set_version=constant_set_version,
            budget_version=budget_version,
        )
    except (StatisticsError, UncertaintyError, CalculationSummaryError) as exc:
        raise PressureCalculationError(str(exc)) from exc


def _base_pressure_contributions(
    uncertainty_input: PressurePointUncertaintyInput,
) -> tuple[UncertaintyContribution, ...]:
    contributions = [
        UncertaintyContribution(
            name="reference_pressure_mpe",
            standard_uncertainty=expanded_to_standard(
                uncertainty_input.reference_expanded_uncertainty,
                uncertainty_input.reference_coverage_factor,
            ),
        ),
    ]
    if uncertainty_input.dut_resolution > 0:
        contributions.append(
            UncertaintyContribution(
                name="dut_resolution",
                standard_uncertainty=resolution_to_standard(
                    uncertainty_input.dut_resolution
                ),
            )
        )
    if uncertainty_input.pressure_kind is PressureKind.ABSOLUTE:
        contributions.append(
            UncertaintyContribution(
                name="barometer",
                standard_uncertainty=expanded_to_standard(
                    uncertainty_input.barometer_expanded_uncertainty,
                    uncertainty_input.barometer_coverage_factor,
                ),
            )
        )
    contributions.extend(
        UncertaintyContribution(
            name=additional.name,
            standard_uncertainty=additional.standard_uncertainty,
            sensitivity_coefficient=additional.sensitivity_coefficient,
        )
        for additional in uncertainty_input.additional_standard_uncertainties
    )
    return tuple(contributions)


def _build_pressure_result(
    *,
    point_id: str,
    job_id: str,
    dut_id: str,
    measurement_window_id: str,
    reference: float,
    indication: float,
    uncertainty_input: PressurePointUncertaintyInput,
    contributions: tuple[UncertaintyContribution, ...],
    calculation_engine_version: str,
    constant_set_version: str,
    budget_version: str,
) -> PressurePointCalculation:
    combined_standard_uncertainty = combine_standard_uncertainties(
        list(contributions)
    )
    calculated_u = Decimal(
        str(
            expand_uncertainty(
                combined_standard_uncertainty,
                uncertainty_input.coverage_factor,
            )
        )
    )
    summary = build_measurement_point_summary(
        point_id=point_id,
        job_id=job_id,
        dut_id=dut_id,
        measurement_window_id=measurement_window_id,
        reference=reference,
        indication=indication,
        unit=uncertainty_input.unit,
        calculated_expanded_uncertainty=calculated_u,
        cmc_floor=uncertainty_input.cmc_floor,
        calculation_engine_version=calculation_engine_version,
        constant_set_version=constant_set_version,
        budget_version=budget_version,
    )
    return PressurePointCalculation(
        summary=summary,
        contributions=tuple(
            PressureContributionSummary(
                name=contribution.name,
                standard_uncertainty=contribution.standard_uncertainty,
                sensitivity_coefficient=contribution.sensitivity_coefficient,
                effective_standard_uncertainty=(
                    contribution.effective_standard_uncertainty
                ),
            )
            for contribution in contributions
        ),
        combined_standard_uncertainty=combined_standard_uncertainty,
        calculated_expanded_uncertainty=calculated_u,
    )


def _require_equal_point_lengths(
    reference_values: tuple[float, ...],
    indication_values: tuple[float, ...],
) -> None:
    if len(reference_values) != len(indication_values):
        raise PressureCalculationError(
            "Reference and indication reading counts must match."
        )


def _require_at_least_one(values: tuple[float, ...], field_name: str) -> None:
    if len(values) == 0:
        raise PressureCalculationError(f"{field_name} requires at least one value.")
    for value in values:
        _require_finite(value, field_name)


def _require_finite(value: float, field_name: str) -> None:
    if not isfinite(value):
        raise PressureCalculationError(f"{field_name} must be finite.")


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise PressureCalculationError(f"{field_name} is required.")


def _require_non_negative_finite(value: float, field_name: str) -> None:
    if not isfinite(value) or value < 0:
        raise PressureCalculationError(f"{field_name} must be finite and >= 0.")


def _require_positive_finite(value: float, field_name: str) -> None:
    if not isfinite(value) or value <= 0:
        raise PressureCalculationError(f"{field_name} must be finite and > 0.")
