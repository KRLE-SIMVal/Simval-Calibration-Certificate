"""Common certificate result primitives."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


class ResultCalculationError(ValueError):
    """Raised when result-row inputs are invalid."""


@dataclass(frozen=True, slots=True)
class ResultRow:
    reference: float
    indication: float
    error_of_indication: float


def calculate_error_of_indication(reference: float, indication: float) -> float:
    """Return indication minus reference."""
    if not isfinite(reference) or not isfinite(indication):
        raise ResultCalculationError("Reference and indication must be finite.")
    return indication - reference


def build_result_row(reference: float, indication: float) -> ResultRow:
    """Build an immutable result row using the common error rule."""
    return ResultRow(
        reference=reference,
        indication=indication,
        error_of_indication=calculate_error_of_indication(reference, indication),
    )

