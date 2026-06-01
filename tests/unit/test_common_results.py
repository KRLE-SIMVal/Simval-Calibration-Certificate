import pytest

from app.calculation_engine.common.results import (
    ResultCalculationError,
    build_result_row,
    calculate_error_of_indication,
)


def test_error_of_indication_is_indication_minus_reference():
    assert calculate_error_of_indication(-90.032, -90.130) == pytest.approx(-0.098)


def test_error_of_indication_handles_zero_reference():
    assert calculate_error_of_indication(0.0, -0.01) == pytest.approx(-0.01)


def test_result_row_retains_inputs_and_raw_error():
    row = build_result_row(reference=-80.036, indication=-80.110)
    assert row.reference == pytest.approx(-80.036)
    assert row.indication == pytest.approx(-80.110)
    assert row.error_of_indication == pytest.approx(-0.074)


def test_error_of_indication_rejects_nonfinite_input():
    with pytest.raises(ResultCalculationError):
        calculate_error_of_indication(float("inf"), 1.0)

