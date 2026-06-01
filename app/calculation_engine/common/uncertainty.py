"""GUM-style standard uncertainty primitives."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite, sqrt


class Distribution(StrEnum):
    NORMAL = "normal"
    RECTANGULAR = "rectangular"
    TRIANGULAR = "triangular"
    U_SHAPED = "u_shaped"


class UncertaintyError(ValueError):
    """Raised when uncertainty input is invalid."""


@dataclass(frozen=True, slots=True)
class UncertaintyContribution:
    name: str
    standard_uncertainty: float
    sensitivity_coefficient: float = 1.0

    @property
    def effective_standard_uncertainty(self) -> float:
        return abs(self.sensitivity_coefficient) * self.standard_uncertainty


def expanded_to_standard(expanded_uncertainty: float, coverage_factor: float) -> float:
    """Convert expanded uncertainty U to standard uncertainty u."""
    _require_non_negative(expanded_uncertainty, "expanded_uncertainty")
    if coverage_factor <= 0 or not isfinite(coverage_factor):
        raise UncertaintyError("Coverage factor must be finite and > 0.")
    return expanded_uncertainty / coverage_factor


def half_width_to_standard(half_width: float, distribution: Distribution) -> float:
    """Convert a distribution half-width to standard uncertainty."""
    _require_non_negative(half_width, "half_width")
    if distribution is Distribution.RECTANGULAR:
        return half_width / sqrt(3)
    if distribution is Distribution.TRIANGULAR:
        return half_width / sqrt(6)
    if distribution is Distribution.U_SHAPED:
        return half_width / sqrt(2)
    raise UncertaintyError("Normal distribution requires supplied standard uncertainty.")


def resolution_to_standard(resolution: float) -> float:
    """Convert digital resolution to standard uncertainty using rectangular half-step."""
    _require_non_negative(resolution, "resolution")
    return (resolution / 2) / sqrt(3)


def combine_standard_uncertainties(
    contributions: list[UncertaintyContribution],
) -> float:
    """Combine independent standard uncertainties by root-sum-square."""
    if not contributions:
        raise UncertaintyError("At least one uncertainty contribution is required.")
    for contribution in contributions:
        if not contribution.name:
            raise UncertaintyError("Contribution name is required.")
        _require_non_negative(
            contribution.standard_uncertainty, "standard_uncertainty"
        )
        if not isfinite(contribution.sensitivity_coefficient):
            raise UncertaintyError("Sensitivity coefficient must be finite.")
    return sqrt(
        sum(
            contribution.effective_standard_uncertainty**2
            for contribution in contributions
        )
    )


def expand_uncertainty(
    combined_standard_uncertainty: float,
    coverage_factor: float = 2.0,
) -> float:
    """Return expanded uncertainty."""
    _require_non_negative(
        combined_standard_uncertainty, "combined_standard_uncertainty"
    )
    if coverage_factor <= 0 or not isfinite(coverage_factor):
        raise UncertaintyError("Coverage factor must be finite and > 0.")
    return combined_standard_uncertainty * coverage_factor


def _require_non_negative(value: float, name: str) -> None:
    if not isfinite(value) or value < 0:
        raise UncertaintyError(f"{name} must be finite and >= 0.")

