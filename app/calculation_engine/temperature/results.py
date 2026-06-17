"""Temperature certificate result calculations."""

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


class TemperatureCalculationError(ValueError):
    """Raised when a temperature point cannot be calculated safely."""


class TemperatureTypeAMethod(StrEnum):
    INDEPENDENT_REFERENCE_AND_DUT = "independent_reference_and_dut"
    PAIRED_ERROR_DIFFERENCES = "paired_error_differences"


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
            raise TemperatureCalculationError(
                "Additional uncertainty sensitivity coefficient must be finite."
            )


@dataclass(frozen=True, slots=True)
class TemperaturePointUncertaintyInput:
    setpoint: float
    unit: str
    cmc_floor: Decimal
    reference_expanded_uncertainty: float
    reference_coverage_factor: float = 2.0
    bath_expanded_uncertainty: float = 0.0
    bath_coverage_factor: float = 2.0
    dut_resolution: float = 0.0
    coverage_factor: float = 2.0
    type_a_method: TemperatureTypeAMethod = (
        TemperatureTypeAMethod.INDEPENDENT_REFERENCE_AND_DUT
    )
    additional_standard_uncertainties: tuple[AdditionalStandardUncertainty, ...] = field(
        default_factory=tuple
    )

    def __post_init__(self) -> None:
        if not isfinite(self.setpoint):
            raise TemperatureCalculationError("Setpoint must be finite.")
        _require_text(self.unit, "Temperature unit")
        if (
            not isinstance(self.cmc_floor, Decimal)
            or not self.cmc_floor.is_finite()
            or self.cmc_floor < 0
        ):
            raise TemperatureCalculationError("CMC floor must be a finite Decimal >= 0.")
        _require_non_negative_finite(
            self.reference_expanded_uncertainty,
            "Reference expanded uncertainty",
        )
        _require_positive_finite(
            self.reference_coverage_factor,
            "Reference coverage factor",
        )
        _require_non_negative_finite(
            self.bath_expanded_uncertainty,
            "Bath expanded uncertainty",
        )
        _require_positive_finite(self.bath_coverage_factor, "Bath coverage factor")
        _require_non_negative_finite(self.dut_resolution, "DUT resolution")
        _require_positive_finite(self.coverage_factor, "Coverage factor")
        if not isinstance(self.type_a_method, TemperatureTypeAMethod):
            raise TemperatureCalculationError("Temperature Type A method is invalid.")


@dataclass(frozen=True, slots=True)
class TemperatureContributionSummary:
    name: str
    standard_uncertainty: float
    sensitivity_coefficient: float
    effective_standard_uncertainty: float


@dataclass(frozen=True, slots=True)
class AutomaticTemperaturePointCalculation:
    summary: MeasurementPointSummary
    contributions: tuple[TemperatureContributionSummary, ...]
    combined_standard_uncertainty: float
    calculated_expanded_uncertainty: Decimal


def calculate_automatic_temperature_point(
    *,
    point_id: str,
    job_id: str,
    dut_id: str,
    measurement_window_id: str,
    reference_values: tuple[float, ...],
    indication_values: tuple[float, ...],
    uncertainty_input: TemperaturePointUncertaintyInput,
    calculation_engine_version: str,
    constant_set_version: str,
    budget_version: str,
) -> AutomaticTemperaturePointCalculation:
    """Calculate one automatic temperature certificate point.

    Reference and indication values must be paired linked logger/IRTD readings
    selected for the same measurement window. At least two pairs are required so
    Type A repeatability terms can be calculated from the selected data.
    """
    _require_equal_point_lengths(reference_values, indication_values)
    if len(reference_values) < 2:
        raise TemperatureCalculationError(
            "Automatic temperature calculation requires at least two linked readings."
        )

    try:
        reference_mean = mean(reference_values)
        indication_mean = mean(indication_values)
        contributions = _temperature_contributions(
            reference_values=reference_values,
            indication_values=indication_values,
            uncertainty_input=uncertainty_input,
        )
        combined_standard_uncertainty = combine_standard_uncertainties(
            [
                UncertaintyContribution(
                    name=contribution.name,
                    standard_uncertainty=contribution.standard_uncertainty,
                    sensitivity_coefficient=contribution.sensitivity_coefficient,
                )
                for contribution in contributions
            ]
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
            reference=reference_mean,
            indication=indication_mean,
            unit=uncertainty_input.unit,
            calculated_expanded_uncertainty=calculated_u,
            cmc_floor=uncertainty_input.cmc_floor,
            calculation_engine_version=calculation_engine_version,
            constant_set_version=constant_set_version,
            budget_version=budget_version,
        )
    except (StatisticsError, UncertaintyError, CalculationSummaryError) as exc:
        raise TemperatureCalculationError(str(exc)) from exc

    return AutomaticTemperaturePointCalculation(
        summary=summary,
        contributions=tuple(
            TemperatureContributionSummary(
                name=contribution.name,
                standard_uncertainty=contribution.standard_uncertainty,
                sensitivity_coefficient=contribution.sensitivity_coefficient,
                effective_standard_uncertainty=contribution.effective_standard_uncertainty,
            )
            for contribution in contributions
        ),
        combined_standard_uncertainty=combined_standard_uncertainty,
        calculated_expanded_uncertainty=calculated_u,
    )


def _temperature_contributions(
    *,
    reference_values: tuple[float, ...],
    indication_values: tuple[float, ...],
    uncertainty_input: TemperaturePointUncertaintyInput,
) -> tuple[UncertaintyContribution, ...]:
    contributions = [
        UncertaintyContribution(
            name="reference_sensor_calibration",
            standard_uncertainty=expanded_to_standard(
                uncertainty_input.reference_expanded_uncertainty,
                uncertainty_input.reference_coverage_factor,
            ),
        )
    ]
    contributions.extend(
        _type_a_contributions(
            reference_values=reference_values,
            indication_values=indication_values,
            method=uncertainty_input.type_a_method,
        )
    )
    if uncertainty_input.bath_expanded_uncertainty > 0:
        contributions.append(
            UncertaintyContribution(
                name="bath_or_thermostat",
                standard_uncertainty=expanded_to_standard(
                    uncertainty_input.bath_expanded_uncertainty,
                    uncertainty_input.bath_coverage_factor,
                ),
            )
        )
    if uncertainty_input.dut_resolution > 0:
        contributions.append(
            UncertaintyContribution(
                name="dut_resolution",
                standard_uncertainty=resolution_to_standard(
                    uncertainty_input.dut_resolution
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


def _type_a_contributions(
    *,
    reference_values: tuple[float, ...],
    indication_values: tuple[float, ...],
    method: TemperatureTypeAMethod,
) -> tuple[UncertaintyContribution, ...]:
    if method is TemperatureTypeAMethod.INDEPENDENT_REFERENCE_AND_DUT:
        return (
            UncertaintyContribution(
                name="reference_sensor_repeatability",
                standard_uncertainty=standard_uncertainty_of_mean(reference_values),
            ),
            UncertaintyContribution(
                name="dut_indication_repeatability",
                standard_uncertainty=standard_uncertainty_of_mean(indication_values),
            ),
        )
    if method is TemperatureTypeAMethod.PAIRED_ERROR_DIFFERENCES:
        paired_errors = tuple(
            indication - reference
            for reference, indication in zip(
                reference_values,
                indication_values,
                strict=True,
            )
        )
        return (
            UncertaintyContribution(
                name="paired_error_repeatability",
                standard_uncertainty=standard_uncertainty_of_mean(paired_errors),
            ),
        )
    raise TemperatureCalculationError("Temperature Type A method is invalid.")


def _require_equal_point_lengths(
    reference_values: tuple[float, ...],
    indication_values: tuple[float, ...],
) -> None:
    if len(reference_values) != len(indication_values):
        raise TemperatureCalculationError(
            "Reference and indication reading counts must match."
        )


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise TemperatureCalculationError(f"{field_name} is required.")


def _require_non_negative_finite(value: float, field_name: str) -> None:
    if not isfinite(value) or value < 0:
        raise TemperatureCalculationError(f"{field_name} must be finite and >= 0.")


def _require_positive_finite(value: float, field_name: str) -> None:
    if not isfinite(value) or value <= 0:
        raise TemperatureCalculationError(f"{field_name} must be finite and > 0.")
