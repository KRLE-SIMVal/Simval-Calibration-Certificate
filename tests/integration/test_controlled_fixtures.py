import os
from pathlib import Path

import pytest

from app.backend.imports.fixture_manifest import load_manifest, sha256_file
from app.backend.imports.valprobe_workbook import inspect_valprobe_workbook
from app.backend.imports.verification_pdf_contract import (
    VerificationPdfContract,
    VerificationPdfExtractionNotImplemented,
    extract_irtd_reference_rows,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "tests" / "fixtures" / "example_files_manifest.json"


def test_fixture_manifest_registers_examples_as_controlled_data():
    records = load_manifest(MANIFEST)
    assert {record.fixture_id for record in records} == {
        "kaye_valprobe_calibration_xlsx",
        "kaye_valprobe_verification_pdf",
        "simval_certificate_layout_xlsx",
        "third_party_certificate_design_reference_pdf",
        "third_party_certificate_output_pdf",
    }
    assert all(
        record.confidentiality == "controlled_internal_confidential"
        for record in records
    )
    assert all(record.allowed_in_ci is False for record in records)


@pytest.mark.controlled_fixture
@pytest.mark.skipif(
    os.environ.get("SIMVAL_RUN_CONTROLLED_FIXTURE_TESTS") != "1",
    reason="Controlled example files are not approved for default CI execution.",
)
def test_controlled_example_file_hashes_match_manifest():
    for record in load_manifest(MANIFEST):
        path = REPO_ROOT / record.path
        assert path.exists()
        assert sha256_file(path) == record.sha256


@pytest.mark.controlled_fixture
@pytest.mark.skipif(
    os.environ.get("SIMVAL_RUN_CONTROLLED_FIXTURE_TESTS") != "1",
    reason="Controlled example files are not approved for default CI execution.",
)
def test_valprobe_workbook_contract_matches_observed_structure():
    workbook_path = (
        REPO_ROOT
        / "Docs"
        / "Input and output file examples"
        / "Calibration_input_file_Valprobe RT Loggers.xlsx"
    )
    structure = inspect_valprobe_workbook(workbook_path)
    assert structure.sheet_names == ("Temperature", "Messages and Comments")
    assert structure.temperature_range == "A2:AL524"
    assert structure.messages_range == "A1:E86"
    assert structure.temperature_populated_rows == 521
    assert structure.messages_populated_rows == 80
    assert len(structure.sensor_headers) == 37
    assert structure.sensor_headers[0] == "Sensor1(deg C)"
    assert structure.sensor_headers[-1] == "Sensor37(deg C)"
    assert len(structure.logger_ids) == 37
    assert structure.logger_ids[0] == "MJT1-A"
    assert structure.logger_ids[-1] == "NWU2-A"
    assert structure.first_numeric_data_row == 12


@pytest.mark.parser_contract
def test_verification_pdf_irtd_contract_is_second_column_next_to_time():
    contract = VerificationPdfContract()
    assert contract.time_column_name == "Time"
    assert contract.irtd_column_position == 2


@pytest.mark.parser_contract
def test_verification_pdf_extraction_is_not_silent_before_dependency_selection():
    with pytest.raises(VerificationPdfExtractionNotImplemented):
        extract_irtd_reference_rows(Path("not-used-in-p1.pdf"))
