from decimal import Decimal

import pytest

from app.calculation_engine.temperature.results import (
    AdditionalStandardUncertainty,
    TemperatureCalculationError,
    TemperaturePointUncertaintyInput,
    calculate_automatic_temperature_point,
)


def test_automatic_temperature_point_calculates_linked_means_error_and_uncertainty():
    result = calculate_automatic_temperature_point(
        point_id="point-001",
        job_id="job-001",
        dut_id="dut-001",
        measurement_window_id="window-001",
        reference_values=(-80.031, -80.030),
        indication_values=(-80.036, -80.034),
        uncertainty_input=TemperaturePointUncertaintyInput(
            setpoint=-80.0,
            unit="deg C",
            cmc_floor=Decimal("0.010"),
            reference_expanded_uncertainty=0.010,
            bath_expanded_uncertainty=0.004,
            dut_resolution=0.010,
        ),
        calculation_engine_version="calc-engine-0.1.0",
        constant_set_version="constants-2026-001",
        budget_version="budget-temp-001",
    )

    summary = result.summary
    assert summary.reference == pytest.approx(-80.0305)
    assert summary.indication == pytest.approx(-80.035)
    assert summary.error_of_indication == pytest.approx(-0.0045)
    assert result.combined_standard_uncertainty == pytest.approx(
        0.006211548,
        abs=1e-9,
    )
    assert result.calculated_expanded_uncertainty == pytest.approx(
        Decimal("0.0124231"),
        abs=Decimal("0.000001"),
    )
    assert summary.reported_expanded_uncertainty == Decimal("0.012")
    assert summary.display_error_of_indication == Decimal("-0.004")
    assert tuple(contribution.name for contribution in result.contributions) == (
        "reference_sensor_calibration",
        "reference_sensor_repeatability",
        "dut_indication_repeatability",
        "bath_or_thermostat",
        "dut_resolution",
    )


def test_automatic_temperature_point_applies_cmc_floor_to_reported_uncertainty():
    result = calculate_automatic_temperature_point(
        point_id="point-001",
        job_id="job-001",
        dut_id="dut-001",
        measurement_window_id="window-001",
        reference_values=(0.000, 0.002),
        indication_values=(0.001, 0.003),
        uncertainty_input=TemperaturePointUncertaintyInput(
            setpoint=0.0,
            unit="deg C",
            cmc_floor=Decimal("0.020"),
            reference_expanded_uncertainty=0.002,
            bath_expanded_uncertainty=0.0,
            dut_resolution=0.001,
        ),
        calculation_engine_version="calc-engine-0.1.0",
        constant_set_version="constants-2026-001",
        budget_version="budget-temp-001",
    )

    assert result.summary.reported_expanded_uncertainty == Decimal("0.020")
    assert result.summary.cmc_floor_applied is True


def test_automatic_temperature_point_includes_additional_standard_terms():
    result = calculate_automatic_temperature_point(
        point_id="point-001",
        job_id="job-001",
        dut_id="dut-001",
        measurement_window_id="window-001",
        reference_values=(0.000, 0.002),
        indication_values=(0.001, 0.003),
        uncertainty_input=TemperaturePointUncertaintyInput(
            setpoint=0.0,
            unit="deg C",
            cmc_floor=Decimal("0.001"),
            reference_expanded_uncertainty=0.002,
            additional_standard_uncertainties=(
                AdditionalStandardUncertainty(
                    name="method_stability",
                    standard_uncertainty=0.003,
                    sensitivity_coefficient=2.0,
                ),
            ),
        ),
        calculation_engine_version="calc-engine-0.1.0",
        constant_set_version="constants-2026-001",
        budget_version="budget-temp-001",
    )

    method_stability = result.contributions[-1]
    assert method_stability.name == "method_stability"
    assert method_stability.effective_standard_uncertainty == pytest.approx(0.006)


def test_automatic_temperature_point_rejects_too_few_linked_readings():
    with pytest.raises(TemperatureCalculationError):
        calculate_automatic_temperature_point(
            point_id="point-001",
            job_id="job-001",
            dut_id="dut-001",
            measurement_window_id="window-001",
            reference_values=(-80.031,),
            indication_values=(-80.036,),
            uncertainty_input=TemperaturePointUncertaintyInput(
                setpoint=-80.0,
                unit="deg C",
                cmc_floor=Decimal("0.010"),
                reference_expanded_uncertainty=0.010,
            ),
            calculation_engine_version="calc-engine-0.1.0",
            constant_set_version="constants-2026-001",
            budget_version="budget-temp-001",
        )


def test_automatic_temperature_point_rejects_unpaired_reading_counts():
    with pytest.raises(TemperatureCalculationError):
        calculate_automatic_temperature_point(
            point_id="point-001",
            job_id="job-001",
            dut_id="dut-001",
            measurement_window_id="window-001",
            reference_values=(-80.031, -80.030),
            indication_values=(-80.036,),
            uncertainty_input=TemperaturePointUncertaintyInput(
                setpoint=-80.0,
                unit="deg C",
                cmc_floor=Decimal("0.010"),
                reference_expanded_uncertainty=0.010,
            ),
            calculation_engine_version="calc-engine-0.1.0",
            constant_set_version="constants-2026-001",
            budget_version="budget-temp-001",
        )
