import math

import pytest

from app.calculation_engine.common.statistics import (
    StatisticsError,
    mean,
    sample_standard_deviation,
    standard_uncertainty_of_mean,
)


def test_mean_handles_negative_temperatures():
    assert mean([-90.03, -90.05, -90.04]) == pytest.approx(-90.04)


def test_sample_standard_deviation_uses_n_minus_one():
    assert sample_standard_deviation([1.0, 2.0, 3.0]) == pytest.approx(1.0)


def test_standard_uncertainty_of_mean_uses_s_over_sqrt_n():
    values = [1.0, 2.0, 3.0]
    assert standard_uncertainty_of_mean(values) == pytest.approx(1.0 / math.sqrt(3))


def test_statistics_reject_nonfinite_values():
    with pytest.raises(StatisticsError):
        mean([1.0, float("nan")])


def test_sample_standard_deviation_requires_two_values():
    with pytest.raises(StatisticsError):
        sample_standard_deviation([1.0])

