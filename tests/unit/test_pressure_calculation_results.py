from decimal import Decimal

import pytest

from app.calculation_engine.pressure.results import (
    AdditionalStandardUncertainty,
    PressureCalculationError,
    PressureKind,
    PressurePointUncertaintyInput,
    calculate_automatic_pressure_point,
    calculate_manual_pressure_point,
)


def test_manual_gauge_pressure_averages_up_down_indications_and_omits_barometer():
    result = calculate_manual_pressure_point(
        point_id="point-001",
        job_id="job-001",
        dut_id="dut-001",
        measurement_window_id="manual-pressure-001",
        reference_pressure=10.000,
        indication_values=(10.004, 10.006),
        uncertainty_input=PressurePointUncertaintyInput(
            setpoint=10.0,
            unit="bar",
            pressure_kind=PressureKind.GAUGE,
            cmc_floor=Decimal("0.001"),
            reference_expanded_uncertainty=0.004,
            dut_resolution=0.002,
        ),
        calculation_engine_version="calc-engine-0.1.0",
        constant_set_version="constants-pressure-001",
        budget_version="budget-pressure-001",
    )

    summary = result.summary
    assert summary.reference == pytest.approx(10.000)
    assert summary.indication == pytest.approx(10.005)
    assert summary.error_of_indication == pytest.approx(0.005)
    assert result.combined_standard_uncertainty == pytest.approx(
        0.002081666,
        abs=1e-9,
    )
    assert result.calculated_expanded_uncertainty == pytest.approx(
        Decimal("0.00416333"),
        abs=Decimal("0.000001"),
    )
    assert summary.reported_expanded_uncertainty == Decimal("0.0042")
    assert tuple(contribution.name for contribution in result.contributions) == (
        "reference_pressure_mpe",
        "dut_resolution",
    )


def test_manual_absolute_pressure_includes_barometer_contribution():
    result = calculate_manual_pressure_point(
        point_id="point-001",
        job_id="job-001",
        dut_id="dut-001",
        measurement_window_id="manual-pressure-001",
        reference_pressure=1.000,
        indication_values=(1.003,),
        uncertainty_input=PressurePointUncertaintyInput(
            setpoint=1.0,
            unit="bar",
            pressure_kind=PressureKind.ABSOLUTE,
            cmc_floor=Decimal("0.001"),
            reference_expanded_uncertainty=0.004,
            dut_resolution=0.002,
            barometer_expanded_uncertainty=0.006,
        ),
        calculation_engine_version="calc-engine-0.1.0",
        constant_set_version="constants-pressure-001",
        budget_version="budget-pressure-001",
    )

    assert tuple(contribution.name for contribution in result.contributions) == (
        "reference_pressure_mpe",
        "dut_resolution",
        "barometer",
    )
    assert result.summary.error_of_indication == pytest.approx(0.003)
    assert result.summary.reported_expanded_uncertainty == Decimal("0.0073")


def test_automatic_pressure_calculates_means_repeatability_and_error():
    result = calculate_automatic_pressure_point(
        point_id="point-001",
        job_id="job-001",
        dut_id="dut-001",
        measurement_window_id="auto-pressure-001",
        reference_values=(100.000, 100.002, 100.001),
        indication_values=(100.004, 100.006, 100.005),
        uncertainty_input=PressurePointUncertaintyInput(
            setpoint=100.0,
            unit="bar",
            pressure_kind=PressureKind.GAUGE,
            cmc_floor=Decimal("0.001"),
            reference_expanded_uncertainty=0.004,
            dut_resolution=0.002,
        ),
        calculation_engine_version="calc-engine-0.1.0",
        constant_set_version="constants-pressure-001",
        budget_version="budget-pressure-001",
    )

    summary = result.summary
    assert summary.reference == pytest.approx(100.001)
    assert summary.indication == pytest.approx(100.005)
    assert summary.error_of_indication == pytest.approx(0.004)
    assert result.combined_standard_uncertainty == pytest.approx(
        0.002236067,
        abs=1e-9,
    )
    assert summary.reported_expanded_uncertainty == Decimal("0.0045")
    assert tuple(contribution.name for contribution in result.contributions) == (
        "reference_pressure_mpe",
        "dut_resolution",
        "reference_pressure_repeatability",
        "dut_indication_repeatability",
    )


def test_pressure_point_applies_cmc_floor_to_reported_uncertainty():
    result = calculate_manual_pressure_point(
        point_id="point-001",
        job_id="job-001",
        dut_id="dut-001",
        measurement_window_id="manual-pressure-001",
        reference_pressure=1.000,
        indication_values=(1.001,),
        uncertainty_input=PressurePointUncertaintyInput(
            setpoint=1.0,
            unit="bar",
            pressure_kind=PressureKind.GAUGE,
            cmc_floor=Decimal("0.010"),
            reference_expanded_uncertainty=0.002,
            dut_resolution=0.001,
        ),
        calculation_engine_version="calc-engine-0.1.0",
        constant_set_version="constants-pressure-001",
        budget_version="budget-pressure-001",
    )

    assert result.summary.reported_expanded_uncertainty == Decimal("0.010")
    assert result.summary.cmc_floor_applied is True


def test_pressure_point_includes_additional_standard_terms():
    result = calculate_manual_pressure_point(
        point_id="point-001",
        job_id="job-001",
        dut_id="dut-001",
        measurement_window_id="manual-pressure-001",
        reference_pressure=1.000,
        indication_values=(1.001,),
        uncertainty_input=PressurePointUncertaintyInput(
            setpoint=1.0,
            unit="bar",
            pressure_kind=PressureKind.GAUGE,
            cmc_floor=Decimal("0.001"),
            reference_expanded_uncertainty=0.002,
            additional_standard_uncertainties=(
                AdditionalStandardUncertainty(
                    name="method_hysteresis",
                    standard_uncertainty=0.003,
                    sensitivity_coefficient=2.0,
                ),
            ),
        ),
        calculation_engine_version="calc-engine-0.1.0",
        constant_set_version="constants-pressure-001",
        budget_version="budget-pressure-001",
    )

    method_hysteresis = result.contributions[-1]
    assert method_hysteresis.name == "method_hysteresis"
    assert method_hysteresis.effective_standard_uncertainty == pytest.approx(0.006)


def test_gauge_pressure_rejects_barometer_uncertainty():
    with pytest.raises(PressureCalculationError, match="absolute pressure"):
        PressurePointUncertaintyInput(
            setpoint=10.0,
            unit="bar",
            pressure_kind=PressureKind.GAUGE,
            cmc_floor=Decimal("0.001"),
            reference_expanded_uncertainty=0.004,
            barometer_expanded_uncertainty=0.006,
        )


def test_automatic_pressure_rejects_too_few_linked_readings():
    with pytest.raises(PressureCalculationError):
        calculate_automatic_pressure_point(
            point_id="point-001",
            job_id="job-001",
            dut_id="dut-001",
            measurement_window_id="auto-pressure-001",
            reference_values=(100.000,),
            indication_values=(100.004,),
            uncertainty_input=PressurePointUncertaintyInput(
                setpoint=100.0,
                unit="bar",
                pressure_kind=PressureKind.GAUGE,
                cmc_floor=Decimal("0.001"),
                reference_expanded_uncertainty=0.004,
            ),
            calculation_engine_version="calc-engine-0.1.0",
            constant_set_version="constants-pressure-001",
            budget_version="budget-pressure-001",
        )


def test_automatic_pressure_rejects_unpaired_reading_counts():
    with pytest.raises(PressureCalculationError):
        calculate_automatic_pressure_point(
            point_id="point-001",
            job_id="job-001",
            dut_id="dut-001",
            measurement_window_id="auto-pressure-001",
            reference_values=(100.000, 100.001),
            indication_values=(100.004,),
            uncertainty_input=PressurePointUncertaintyInput(
                setpoint=100.0,
                unit="bar",
                pressure_kind=PressureKind.GAUGE,
                cmc_floor=Decimal("0.001"),
                reference_expanded_uncertainty=0.004,
            ),
            calculation_engine_version="calc-engine-0.1.0",
            constant_set_version="constants-pressure-001",
            budget_version="budget-pressure-001",
        )
