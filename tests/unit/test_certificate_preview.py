from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.backend.certificates.metadata import CertificateMetadata
from app.backend.certificates.preview import (
    CertificatePreview,
    CertificatePreviewDut,
    CertificatePreviewError,
    CertificatePreviewReferenceEquipment,
    CertificatePreviewRow,
)


def test_certificate_preview_records_locked_summary_rows_and_versions():
    preview = CertificatePreview(
        job_id="job-001",
        generated_by="user-001",
        generated_at=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
        software_version="app-0.1.0",
        calculation_engine_version="calc-engine-0.1.0",
        constant_set_version="constants-2026-001",
        budget_version="budget-temp-001",
        template_version="template-2026-001",
        metadata=_metadata(),
        duts=(_dut(),),
        reference_equipment=(_reference_equipment(),),
        rows=(_row(),),
    )

    assert preview.summary_ids == ("point-001",)
    assert preview.metadata.client_name == "SIMVal customer"
    assert preview.duts[0].serial_number == "MJT1"
    assert preview.reference_equipment[0].simval_id == "SIM-T-001"
    assert preview.rows[0].display_error_of_indication == Decimal("-0.004")
    assert preview.rows[0].reported_expanded_uncertainty == Decimal("0.012")


def test_certificate_preview_rejects_empty_rows():
    with pytest.raises(CertificatePreviewError):
        CertificatePreview(
            job_id="job-001",
            generated_by="user-001",
            generated_at=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
            software_version="app-0.1.0",
            calculation_engine_version="calc-engine-0.1.0",
            constant_set_version="constants-2026-001",
            budget_version="budget-temp-001",
            template_version="template-2026-001",
            metadata=_metadata(),
            duts=(_dut(),),
            reference_equipment=(_reference_equipment(),),
            rows=(),
        )


def test_certificate_preview_rejects_naive_timestamp():
    with pytest.raises(CertificatePreviewError):
        CertificatePreview(
            job_id="job-001",
            generated_by="user-001",
            generated_at=datetime(2026, 6, 1, 15, 30),
            software_version="app-0.1.0",
            calculation_engine_version="calc-engine-0.1.0",
            constant_set_version="constants-2026-001",
            budget_version="budget-temp-001",
            template_version="template-2026-001",
            metadata=_metadata(),
            duts=(_dut(),),
            reference_equipment=(_reference_equipment(),),
            rows=(_row(),),
        )


def test_certificate_preview_rejects_row_without_dut_metadata():
    with pytest.raises(CertificatePreviewError):
        CertificatePreview(
            job_id="job-001",
            generated_by="user-001",
            generated_at=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
            software_version="app-0.1.0",
            calculation_engine_version="calc-engine-0.1.0",
            constant_set_version="constants-2026-001",
            budget_version="budget-temp-001",
            template_version="template-2026-001",
            metadata=_metadata(),
            duts=(),
            reference_equipment=(_reference_equipment(),),
            rows=(_row(),),
        )


def test_certificate_preview_rejects_missing_reference_equipment():
    with pytest.raises(CertificatePreviewError):
        CertificatePreview(
            job_id="job-001",
            generated_by="user-001",
            generated_at=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
            software_version="app-0.1.0",
            calculation_engine_version="calc-engine-0.1.0",
            constant_set_version="constants-2026-001",
            budget_version="budget-temp-001",
            template_version="template-2026-001",
            metadata=_metadata(),
            duts=(_dut(),),
            reference_equipment=(),
            rows=(_row(),),
        )


def _metadata() -> CertificateMetadata:
    return CertificateMetadata(
        job_id="job-001",
        certificate_date=date(2026, 6, 3),
        calibration_date=date(2026, 6, 1),
        receipt_date=date(2026, 5, 31),
        task_number="TASK-2026-001",
        purchase_order="PO-12345",
        client_name="SIMVal customer",
        client_address="Validated Road 1, 2800 Lyngby",
        procedure="SIMVal SOP-TEMP-001",
        place="SIMVal Temperature Laboratory, Lyngby",
        approved_by_label="QA User",
        remarks="Aflæsning af logger data via ValProbe RT.",
        traceability_statement="Measurements are metrologically traceable.",
        uncertainty_statement="Expanded uncertainty uses k=2.",
        ambient_conditions="Room temperature 23 +/- 2 deg C.",
        temperature_scale="ITS-90",
        recorded_by="operator-001",
        recorded_at=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
    )


def _dut() -> CertificatePreviewDut:
    return CertificatePreviewDut(
        dut_id="dut-001",
        make="Kaye",
        model="ValProbe RT",
        serial_number="MJT1",
        channel_id="MJT1-A",
    )


def _reference_equipment() -> CertificatePreviewReferenceEquipment:
    return CertificatePreviewReferenceEquipment(
        equipment_id="ref-001",
        simval_id="SIM-T-001",
        equipment_type="IRTD",
        serial_number="IRT-123",
        calibration_certificate_reference="DANAK-CAL-12345",
        calibration_due_date=date(2027, 4, 30),
        range_minimum=-90.0,
        range_maximum=140.0,
        range_unit="deg C",
        traceability_statement="Accredited calibration with SI traceability.",
    )


def _row() -> CertificatePreviewRow:
    return CertificatePreviewRow(
        point_id="point-001",
        dut_id="dut-001",
        measurement_window_id="window-001",
        reference=-80.0305,
        indication=-80.035,
        error_of_indication=-0.0045,
        display_error_of_indication=Decimal("-0.004"),
        reported_expanded_uncertainty=Decimal("0.012"),
        unit="deg C",
    )
