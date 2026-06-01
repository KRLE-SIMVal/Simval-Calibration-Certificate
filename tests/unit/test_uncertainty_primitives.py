import math

import pytest

from app.calculation_engine.common.uncertainty import (
    Distribution,
    UncertaintyContribution,
    UncertaintyError,
    combine_standard_uncertainties,
    expand_uncertainty,
    expanded_to_standard,
    half_width_to_standard,
    resolution_to_standard,
)


def test_expanded_uncertainty_converts_to_standard_uncertainty():
    assert expanded_to_standard(0.02, 2.0) == pytest.approx(0.01)


def test_distribution_half_width_conversions():
    assert half_width_to_standard(0.03, Distribution.RECTANGULAR) == pytest.approx(
        0.03 / math.sqrt(3)
    )
    assert half_width_to_standard(0.03, Distribution.TRIANGULAR) == pytest.approx(
        0.03 / math.sqrt(6)
    )
    assert half_width_to_standard(0.03, Distribution.U_SHAPED) == pytest.approx(
        0.03 / math.sqrt(2)
    )


def test_resolution_to_standard_uses_rectangular_half_step():
    assert resolution_to_standard(0.01) == pytest.approx((0.01 / 2) / math.sqrt(3))


def test_combines_standard_uncertainties_with_sensitivity_coefficients():
    combined = combine_standard_uncertainties(
        [
            UncertaintyContribution("reference", 0.01, 1.0),
            UncertaintyContribution("resolution", 0.02, 0.5),
        ]
    )
    assert combined == pytest.approx(math.sqrt(0.01**2 + 0.01**2))


def test_expand_uncertainty_uses_default_k_2():
    assert expand_uncertainty(0.01) == pytest.approx(0.02)


def test_uncertainty_combination_requires_contributions():
    with pytest.raises(UncertaintyError):
        combine_standard_uncertainties([])

