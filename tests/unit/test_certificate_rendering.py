from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.backend.certificates.preview import CertificatePreview, CertificatePreviewRow
from app.backend.certificates.rendering import (
    CertificateRenderingError,
    render_certificate_pdf,
)


def test_render_certificate_pdf_returns_deterministic_pdf_bytes_and_checksum():
    preview = _preview()

    first = render_certificate_pdf(
        certificate_id="cert-001",
        certificate_number="SIMVAL-CAL-0001",
        preview=preview,
    )
    second = render_certificate_pdf(
        certificate_id="cert-001",
        certificate_number="SIMVAL-CAL-0001",
        preview=preview,
    )

    assert first.content_bytes == second.content_bytes
    assert first.checksum_sha256 == second.checksum_sha256
    assert first.filename == "SIMVAL-CAL-0001.pdf"
    assert first.artifact_type.value == "pdf"
    assert first.content_bytes.startswith(b"%PDF-1.4\n")
    assert first.checksum_sha256 == (
        "24c1c4a81035f6e943a6c126e90d4b88bcf3a5acc3f6069ea87b694f9455c2d8"
    )


def test_render_certificate_pdf_uses_locked_preview_values_without_recalculation():
    preview = CertificatePreview(
        job_id="job-001",
        generated_by="qa-001",
        generated_at=datetime(2026, 6, 1, 15, 20, tzinfo=timezone.utc),
        software_version="app-0.1.0",
        calculation_engine_version="calc-engine-0.1.0",
        constant_set_version="constants-2026-001",
        budget_version="budget-temp-001",
        template_version="template-2026-001",
        rows=(
            CertificatePreviewRow(
                point_id="point-001",
                dut_id="dut-001",
                measurement_window_id="window-001",
                reference=0.0,
                indication=100.0,
                error_of_indication=100.0,
                display_error_of_indication=Decimal("9.999"),
                reported_expanded_uncertainty=Decimal("0.012"),
                unit="deg C",
            ),
        ),
    )

    artifact = render_certificate_pdf(
        certificate_id="cert-001",
        certificate_number="SIMVAL-CAL-0001",
        preview=preview,
    )

    content_text = artifact.content_bytes.decode("latin-1")
    assert "9.999 +/- 0.012 deg C" in content_text
    assert "100.000 +/- 0.012 deg C" not in content_text


def test_render_certificate_pdf_rejects_blank_certificate_number():
    with pytest.raises(CertificateRenderingError):
        render_certificate_pdf(
            certificate_id="cert-001",
            certificate_number=" ",
            preview=_preview(),
        )


def _preview() -> CertificatePreview:
    return CertificatePreview(
        job_id="job-001",
        generated_by="qa-001",
        generated_at=datetime(2026, 6, 1, 15, 20, tzinfo=timezone.utc),
        software_version="app-0.1.0",
        calculation_engine_version="calc-engine-0.1.0",
        constant_set_version="constants-2026-001",
        budget_version="budget-temp-001",
        template_version="template-2026-001",
        rows=(
            CertificatePreviewRow(
                point_id="point-001",
                dut_id="dut-001",
                measurement_window_id="window-001",
                reference=-80.0305,
                indication=-80.035,
                error_of_indication=-0.0045,
                display_error_of_indication=Decimal("-0.004"),
                reported_expanded_uncertainty=Decimal("0.012"),
                unit="deg C",
            ),
        ),
    )
