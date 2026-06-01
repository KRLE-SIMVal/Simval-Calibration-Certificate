"""Statistical primitives used by calculation methods."""

from __future__ import annotations

from math import isfinite, sqrt
from typing import Iterable


class StatisticsError(ValueError):
    """Raised when a statistical calculation is not valid for the input."""


def mean(values: Iterable[float]) -> float:
    """Return arithmetic mean for finite values."""
    data = _finite_values(values)
    if not data:
        raise StatisticsError("Mean requires at least one value.")
    return sum(data) / len(data)


def sample_standard_deviation(values: Iterable[float]) -> float:
    """Return sample standard deviation using n - 1 denominator."""
    data = _finite_values(values)
    if len(data) < 2:
        raise StatisticsError("Sample standard deviation requires at least two values.")
    avg = mean(data)
    variance = sum((value - avg) ** 2 for value in data) / (len(data) - 1)
    return sqrt(variance)


def standard_uncertainty_of_mean(values: Iterable[float]) -> float:
    """Return Type A standard uncertainty of the mean."""
    data = _finite_values(values)
    return sample_standard_deviation(data) / sqrt(len(data))


def _finite_values(values: Iterable[float]) -> list[float]:
    data = [float(value) for value in values]
    if any(not isfinite(value) for value in data):
        raise StatisticsError("Values must be finite.")
    return data

