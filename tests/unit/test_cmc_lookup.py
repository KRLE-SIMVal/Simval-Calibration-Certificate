import pytest

from app.calculation_engine.cmc.models import (
    CmcEntry,
    CmcExpressionType,
    CmcLookupError,
    CmcRange,
    apply_cmc_floor,
    lookup_cmc,
)


def test_constant_cmc_lookup_inside_range():
    entry = CmcEntry(
        entry_id="temp-low",
        version="1",
        expression_type=CmcExpressionType.CONSTANT,
        range=CmcRange(lower=-90.0, upper=-50.0),
        unit="deg C",
        value=0.02,
    )
    result = lookup_cmc(-80.0, [entry], unit="deg C")
    assert result.raw_cmc == pytest.approx(0.02)
    assert result.interpolated is False


def test_linear_cmc_lookup_interpolates_approved_segment():
    entry = CmcEntry(
        entry_id="temp-linear",
        version="1",
        expression_type=CmcExpressionType.LINEAR_SEGMENT,
        range=CmcRange(lower=0.0, upper=100.0),
        unit="deg C",
        lower_value=0.01,
        upper_value=0.03,
    )
    result = lookup_cmc(50.0, [entry], unit="deg C")
    assert result.raw_cmc == pytest.approx(0.02)
    assert result.interpolated is True


def test_table_worst_case_uses_interval_value_without_interpolation():
    entry = CmcEntry(
        entry_id="temp-table",
        version="1",
        expression_type=CmcExpressionType.TABLE_WORST_CASE,
        range=CmcRange(lower=-50.0, upper=0.0),
        unit="deg C",
        value=0.05,
    )
    result = lookup_cmc(-25.0, [entry], unit="deg C")
    assert result.raw_cmc == pytest.approx(0.05)
    assert result.interpolated is False


def test_out_of_range_cmc_blocks_lookup():
    entry = CmcEntry(
        entry_id="temp-low",
        version="1",
        expression_type=CmcExpressionType.CONSTANT,
        range=CmcRange(lower=-90.0, upper=-50.0),
        unit="deg C",
        value=0.02,
    )
    with pytest.raises(CmcLookupError):
        lookup_cmc(-49.99, [entry], unit="deg C")


def test_overlapping_cmc_entries_block_ambiguous_lookup():
    entries = [
        CmcEntry(
            entry_id="a",
            version="1",
            expression_type=CmcExpressionType.CONSTANT,
            range=CmcRange(lower=0.0, upper=100.0),
            unit="deg C",
            value=0.02,
        ),
        CmcEntry(
            entry_id="b",
            version="1",
            expression_type=CmcExpressionType.CONSTANT,
            range=CmcRange(lower=50.0, upper=150.0),
            unit="deg C",
            value=0.03,
        ),
    ]
    with pytest.raises(CmcLookupError):
        lookup_cmc(75.0, entries, unit="deg C")


def test_apply_cmc_floor_never_reports_below_cmc():
    assert apply_cmc_floor(0.01, 0.03) == pytest.approx(0.03)
    assert apply_cmc_floor(0.05, 0.03) == pytest.approx(0.05)

