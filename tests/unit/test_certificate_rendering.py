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
    assert first.checksum_sha256 == first.checksum_sha256.lower()


def test_render_certificate_pdf_uses_simval_three_page_structure_for_single_dut():
    artifact = render_certificate_pdf(
        certificate_id="cert-001",
        certificate_number="SIMVAL-CAL-0001",
        preview=_preview(),
    )

    content_text = artifact.content_bytes.decode("latin-1")
    assert "/Count 3" in content_text
    assert "SIMVal A/S" in content_text
    assert "Kalibreringscertifikat" in content_text
    assert "Calibration certificate" in content_text
    assert "Sporbarhed" in content_text
    assert "Traceability" in content_text
    assert "Måleusikkerhed" in content_text
    assert "Uncertainty" in content_text
    assert "Måleresultater" in content_text
    assert "Measurement Results" in content_text
    assert "Referenceudstyr" in content_text
    assert "Reference equipment" in content_text
    assert "Side 1 af 3 / Page 1 of 3" in content_text
    assert "Side 2 af 3 / Page 2 of 3" in content_text
    assert "Side 3 af 3 / Page 3 of 3" in content_text
    assert "DUT: dut-001" in content_text


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


def test_render_certificate_pdf_groups_multiple_duts_in_one_certificate():
    artifact = render_certificate_pdf(
        certificate_id="cert-001",
        certificate_number="SIMVAL-CAL-0001",
        preview=_multi_dut_preview(),
    )

    content_text = artifact.content_bytes.decode("latin-1")
    assert "/Count 4" in content_text
    assert "Side 1 af 4 / Page 1 of 4" in content_text
    assert "Side 2 af 4 / Page 2 of 4" in content_text
    assert "Side 3 af 4 / Page 3 of 4" in content_text
    assert "Side 4 af 4 / Page 4 of 4" in content_text
    assert "DUT: dut-001" in content_text
    assert "DUT: dut-002" in content_text
    assert "Point point-001" in content_text
    assert "Point point-002" in content_text


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


def _multi_dut_preview() -> CertificatePreview:
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
            CertificatePreviewRow(
                point_id="point-002",
                dut_id="dut-002",
                measurement_window_id="window-002",
                reference=-80.0305,
                indication=-79.950,
                error_of_indication=0.0805,
                display_error_of_indication=Decimal("0.080"),
                reported_expanded_uncertainty=Decimal("0.012"),
                unit="deg C",
            ),
        ),
    )
