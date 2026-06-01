from decimal import Decimal

import pytest

from app.calculation_engine.common.summary import (
    CalculationSummaryError,
    MeasurementPointSummary,
    build_measurement_point_summary,
)


def test_measurement_point_summary_records_recalculable_result_and_versions():
    summary = build_measurement_point_summary(
        point_id="point-001",
        job_id="job-001",
        dut_id="dut-001",
        measurement_window_id="window-001",
        reference=-90.032,
        indication=-90.130,
        unit="deg C",
        calculated_expanded_uncertainty=Decimal("0.0104"),
        cmc_floor=Decimal("0.011"),
        calculation_engine_version="calc-engine-0.1.0",
        constant_set_version="constants-2026-001",
        budget_version="budget-temp-001",
    )

    assert summary.reference == pytest.approx(-90.032)
    assert summary.indication == pytest.approx(-90.130)
    assert summary.error_of_indication == pytest.approx(-0.098)
    assert summary.reported_expanded_uncertainty == Decimal("0.011")
    assert summary.display_error_of_indication == Decimal("-0.098")
    assert summary.calculation_engine_version == "calc-engine-0.1.0"
    assert summary.constant_set_version == "constants-2026-001"
    assert summary.budget_version == "budget-temp-001"
    assert summary.cmc_floor_applied is True


def test_measurement_point_summary_uses_calculated_u_when_above_cmc():
    summary = build_measurement_point_summary(
        point_id="point-001",
        job_id="job-001",
        dut_id="dut-001",
        measurement_window_id="window-001",
        reference=0.0,
        indication=-0.01,
        unit="deg C",
        calculated_expanded_uncertainty=Decimal("0.012"),
        cmc_floor=Decimal("0.010"),
        calculation_engine_version="calc-engine-0.1.0",
        constant_set_version="constants-2026-001",
        budget_version="budget-temp-001",
    )

    assert summary.reported_expanded_uncertainty == Decimal("0.012")
    assert summary.display_error_of_indication == Decimal("-0.010")
    assert summary.cmc_floor_applied is False


def test_measurement_point_summary_allows_normal_two_digit_u_rounding_above_cmc():
    summary = build_measurement_point_summary(
        point_id="point-001",
        job_id="job-001",
        dut_id="dut-001",
        measurement_window_id="window-001",
        reference=0.0,
        indication=-0.01,
        unit="deg C",
        calculated_expanded_uncertainty=Decimal("0.0104"),
        cmc_floor=Decimal("0.010"),
        calculation_engine_version="calc-engine-0.1.0",
        constant_set_version="constants-2026-001",
        budget_version="budget-temp-001",
    )

    assert summary.reported_expanded_uncertainty == Decimal("0.010")
    assert summary.cmc_floor_applied is False


@pytest.mark.parametrize(
    "field_name",
    [
        "point_id",
        "job_id",
        "dut_id",
        "measurement_window_id",
        "unit",
        "calculation_engine_version",
        "constant_set_version",
        "budget_version",
    ],
)
def test_measurement_point_summary_rejects_missing_traceability_field(field_name):
    values = {
        "point_id": "point-001",
        "job_id": "job-001",
        "dut_id": "dut-001",
        "measurement_window_id": "window-001",
        "reference": 0.0,
        "indication": -0.01,
        "unit": "deg C",
        "calculated_expanded_uncertainty": Decimal("0.012"),
        "cmc_floor": Decimal("0.010"),
        "calculation_engine_version": "calc-engine-0.1.0",
        "constant_set_version": "constants-2026-001",
        "budget_version": "budget-temp-001",
    }
    values[field_name] = " "

    with pytest.raises(CalculationSummaryError):
        build_measurement_point_summary(**values)


def test_measurement_point_summary_rejects_negative_uncertainty():
    with pytest.raises(CalculationSummaryError):
        build_measurement_point_summary(
            point_id="point-001",
            job_id="job-001",
            dut_id="dut-001",
            measurement_window_id="window-001",
            reference=0.0,
            indication=-0.01,
            unit="deg C",
            calculated_expanded_uncertainty=Decimal("-0.012"),
            cmc_floor=Decimal("0.010"),
            calculation_engine_version="calc-engine-0.1.0",
            constant_set_version="constants-2026-001",
            budget_version="budget-temp-001",
        )


def test_measurement_point_summary_is_immutable():
    summary = build_measurement_point_summary(
        point_id="point-001",
        job_id="job-001",
        dut_id="dut-001",
        measurement_window_id="window-001",
        reference=0.0,
        indication=-0.01,
        unit="deg C",
        calculated_expanded_uncertainty=Decimal("0.012"),
        cmc_floor=Decimal("0.010"),
        calculation_engine_version="calc-engine-0.1.0",
        constant_set_version="constants-2026-001",
        budget_version="budget-temp-001",
    )

    with pytest.raises(AttributeError):
        summary.unit = "K"


def test_measurement_point_summary_direct_construction_validates_reported_u_against_cmc():
    with pytest.raises(CalculationSummaryError):
        MeasurementPointSummary(
            point_id="point-001",
            job_id="job-001",
            dut_id="dut-001",
            measurement_window_id="window-001",
            reference=0.0,
            indication=-0.01,
            unit="deg C",
            error_of_indication=-0.01,
            calculated_expanded_uncertainty=Decimal("0.009"),
            cmc_floor=Decimal("0.010"),
            reported_expanded_uncertainty=Decimal("0.009"),
            display_error_of_indication=Decimal("-0.01"),
            calculation_engine_version="calc-engine-0.1.0",
            constant_set_version="constants-2026-001",
            budget_version="budget-temp-001",
        )
