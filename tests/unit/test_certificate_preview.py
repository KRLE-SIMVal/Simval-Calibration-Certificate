from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.backend.certificates.preview import (
    CertificatePreview,
    CertificatePreviewError,
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
        rows=(_row(),),
    )

    assert preview.summary_ids == ("point-001",)
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
            rows=(_row(),),
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
