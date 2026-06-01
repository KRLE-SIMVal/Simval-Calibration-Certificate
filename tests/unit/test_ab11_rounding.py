from decimal import Decimal

import pytest

from app.calculation_engine.common.rounding import (
    RoundingError,
    round_expanded_uncertainty,
    round_result_to_uncertainty,
)


def test_two_significant_digit_uncertainty_uses_normal_rounding():
    rounded = round_expanded_uncertainty(Decimal("0.01494"), significant_digits=2)
    assert rounded.value == Decimal("0.015")
    assert rounded.decimal_places == 3


def test_one_significant_digit_uncertainty_rounds_up_per_ab11():
    rounded = round_expanded_uncertainty(Decimal("0.32"), significant_digits=1)
    assert rounded.value == Decimal("0.4")
    assert rounded.decimal_places == 1


def test_uncertainty_rounding_never_reports_below_cmc_floor():
    rounded = round_expanded_uncertainty(
        Decimal("0.01444"),
        significant_digits=2,
        cmc_floor=Decimal("0.01444"),
    )
    assert rounded.value == Decimal("0.015")
    assert rounded.value >= Decimal("0.01444")


def test_result_rounds_to_least_significant_digit_of_uncertainty():
    uncertainty = round_expanded_uncertainty(Decimal("0.010"), significant_digits=2)
    assert uncertainty.value == Decimal("0.010")
    assert round_result_to_uncertainty(Decimal("-0.098"), uncertainty) == Decimal(
        "-0.098"
    )


def test_result_rounds_to_uncertainty_precision_for_certificate_example():
    uncertainty = round_expanded_uncertainty(Decimal("0.01"), significant_digits=1)
    assert uncertainty.value == Decimal("0.01")
    assert round_result_to_uncertainty(Decimal("-0.098"), uncertainty) == Decimal(
        "-0.10"
    )


def test_rounding_rejects_negative_uncertainty():
    with pytest.raises(RoundingError):
        round_expanded_uncertainty(Decimal("-0.01"))


def test_rounding_rejects_more_than_two_significant_digits_for_ab11_report():
    with pytest.raises(RoundingError):
        round_expanded_uncertainty(Decimal("0.0123"), significant_digits=3)

