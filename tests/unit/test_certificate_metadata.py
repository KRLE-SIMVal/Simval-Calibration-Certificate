from datetime import date, datetime, timezone

import pytest

from app.backend.certificates.metadata import (
    CertificateMetadata,
    CertificateMetadataError,
)


def test_certificate_metadata_records_required_certificate_fields():
    metadata = _metadata()

    assert metadata.job_id == "job-001"
    assert metadata.task_number == "TASK-2026-001"
    assert metadata.purchase_order == "PO-12345"
    assert metadata.client_name == "SIMVal customer"
    assert metadata.client_address == "Validated Road 1, 2800 Lyngby"
    assert metadata.procedure == "SIMVal SOP-TEMP-001"
    assert metadata.place == "SIMVal Temperature Laboratory, Lyngby"
    assert metadata.approved_by_label == "QA User"
    assert metadata.temperature_scale == "ITS-90"
    assert metadata.recorded_by == "operator-001"


def test_certificate_metadata_rejects_missing_required_text():
    with pytest.raises(CertificateMetadataError):
        _metadata(client_name=" ")


def test_certificate_metadata_rejects_invalid_date_order():
    with pytest.raises(CertificateMetadataError):
        _metadata(
            certificate_date=date(2026, 6, 1),
            calibration_date=date(2026, 6, 2),
            receipt_date=date(2026, 6, 1),
        )


def test_certificate_metadata_rejects_naive_recorded_timestamp():
    with pytest.raises(CertificateMetadataError):
        _metadata(recorded_at=datetime(2026, 6, 1, 14, 0))


def _metadata(**overrides) -> CertificateMetadata:
    values = {
        "job_id": "job-001",
        "certificate_date": date(2026, 6, 3),
        "calibration_date": date(2026, 6, 1),
        "receipt_date": date(2026, 5, 31),
        "task_number": "TASK-2026-001",
        "purchase_order": "PO-12345",
        "client_name": "SIMVal customer",
        "client_address": "Validated Road 1, 2800 Lyngby",
        "procedure": "SIMVal SOP-TEMP-001",
        "place": "SIMVal Temperature Laboratory, Lyngby",
        "approved_by_label": "QA User",
        "remarks": "Aflæsning af logger data via ValProbe RT.",
        "traceability_statement": (
            "Measurements are metrologically traceable through calibrated "
            "reference equipment under ILAC/EA/DANAK principles."
        ),
        "uncertainty_statement": (
            "The reported expanded uncertainty is based on standard uncertainty "
            "multiplied by coverage factor k=2."
        ),
        "ambient_conditions": "Room temperature 23 +/- 2 deg C.",
        "temperature_scale": "ITS-90",
        "recorded_by": "operator-001",
        "recorded_at": datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
    }
    values.update(overrides)
    return CertificateMetadata(**values)
