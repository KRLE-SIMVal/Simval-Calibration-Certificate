from decimal import Decimal
from zipfile import ZipFile

from app.backend.certificates.uncertainty_export import (
    render_uncertainty_budget_xlsx,
)
from app.backend.certificates.records import ArtifactType
from app.calculation_engine.temperature.results import (
    TemperaturePointUncertaintyInput,
    calculate_automatic_temperature_point,
)


def test_render_uncertainty_budget_xlsx_is_deterministic_and_traceable():
    calculation = _calculation()

    first = render_uncertainty_budget_xlsx(
        certificate_number="SIMVAL-CAL-0001",
        calculation=calculation,
        coverage_factor=2.0,
    )
    second = render_uncertainty_budget_xlsx(
        certificate_number="SIMVAL-CAL-0001",
        calculation=calculation,
        coverage_factor=2.0,
    )

    assert first.artifact_type is ArtifactType.XLSX
    assert first.filename == "SIMVAL-CAL-0001-uncertainty-budget.xlsx"
    assert first.content_bytes == second.content_bytes
    assert first.checksum_sha256 == second.checksum_sha256
    assert first.content_bytes.startswith(b"PK")

    with ZipFile(_bytes_path(first.content_bytes)) as workbook:
        assert workbook.namelist() == [
            "[Content_Types].xml",
            "_rels/.rels",
            "xl/workbook.xml",
            "xl/_rels/workbook.xml.rels",
            "xl/worksheets/sheet1.xml",
        ]
        sheet_xml = workbook.read("xl/worksheets/sheet1.xml").decode("utf-8")

    assert "Uncertainty Budget" in sheet_xml
    assert "SIMVAL-CAL-0001" in sheet_xml
    assert "point-001" in sheet_xml
    assert "reference_sensor_calibration" in sheet_xml
    assert "dut_resolution" in sheet_xml
    assert "combined_standard_uncertainty" in sheet_xml
    assert "calculated_expanded_uncertainty" in sheet_xml
    assert "reported_expanded_uncertainty" in sheet_xml
    assert "calc-engine-0.1.0" in sheet_xml
    assert "constants-2026-001" in sheet_xml
    assert "budget-temp-001" in sheet_xml


def test_render_uncertainty_budget_xlsx_rejects_blank_certificate_number():
    try:
        render_uncertainty_budget_xlsx(
            certificate_number=" ",
            calculation=_calculation(),
            coverage_factor=2.0,
        )
    except ValueError as error:
        assert "Certificate number" in str(error)
    else:
        raise AssertionError("Blank certificate number should be rejected.")


def _calculation():
    return calculate_automatic_temperature_point(
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


def _bytes_path(content: bytes):
    from io import BytesIO

    return BytesIO(content)
