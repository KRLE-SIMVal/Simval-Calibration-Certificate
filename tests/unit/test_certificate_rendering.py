from datetime import date, datetime, timezone
from dataclasses import replace
from decimal import Decimal
import hashlib
from pathlib import Path
import re

import pytest

from app.backend.certificates.metadata import CertificateMetadata
from app.backend.certificates.preview import (
    CertificatePreview,
    CertificatePreviewReferenceEquipment,
    CertificatePreviewRow,
)
from app.backend.certificates.preview import CertificatePreviewDut
from app.backend.certificates.rendering import (
    CertificateLogoAssets,
    CertificateRenderingError,
    RenderedCertificateArtifact,
    render_certificate_pdf,
)
from app.backend.certificates.template_contract import (
    CertificateTemplateContractError,
    validate_certificate_template_contract,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SIMVAL_LOGO_PATH = (
    _REPO_ROOT / "Docs" / "Design Document" / "Logo - SIMVal.png"
)
_DANAK_LOGO_PATH = (
    _REPO_ROOT / "Docs" / "Design Document" / "DANAK Logo 647.png"
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


def test_render_certificate_pdf_embeds_default_simval_and_danak_logo_assets():
    assert _SIMVAL_LOGO_PATH.is_file()
    assert _DANAK_LOGO_PATH.is_file()

    artifact = render_certificate_pdf(
        certificate_id="cert-001",
        certificate_number="SIMVAL-CAL-0001",
        preview=_preview(),
    )

    content_text = artifact.content_bytes.decode("latin-1")
    assert "/XObject << /ImSimval" in content_text
    assert "/ImDanak" in content_text
    assert content_text.count("/Subtype /Image") == 2
    assert "/Width 701 /Height 725" in content_text
    assert "/Width 176 /Height 75" in content_text
    simval_draw = _image_draw(content_text, "ImSimval")
    danak_draw = _image_draw(content_text, "ImDanak")
    assert simval_draw is not None
    assert danak_draw is not None
    assert float(simval_draw.group("width")) > float(danak_draw.group("width"))
    assert float(simval_draw.group("height")) > float(danak_draw.group("height"))


def test_render_certificate_pdf_suppresses_danak_mark_when_scope_disallows_it():
    artifact = render_certificate_pdf(
        certificate_id="cert-001",
        certificate_number="SIMVAL-CAL-0001",
        preview=replace(_preview(), accreditation_mark_allowed=False),
    )

    content_text = artifact.content_bytes.decode("latin-1")
    assert "/ImSimval" in content_text
    assert "/ImDanak" not in content_text
    assert content_text.count("/Subtype /Image") == 1
    assert "Accreditation mark: not applied for this certificate scope." in (
        content_text
    )


def test_render_certificate_pdf_rejects_corrupt_logo_asset(tmp_path):
    corrupt_logo_path = tmp_path / "corrupt-logo.png"
    corrupt_logo_path.write_bytes(b"not a png")

    with pytest.raises(CertificateRenderingError, match="not a supported PNG"):
        render_certificate_pdf(
            certificate_id="cert-001",
            certificate_number="SIMVAL-CAL-0001",
            preview=_preview(),
            logo_assets=CertificateLogoAssets(simval_logo_path=corrupt_logo_path),
        )


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
    assert "TASK-2026-001" in content_text
    assert "PO-12345" in content_text
    assert "SIMVal customer" in content_text
    assert "Validated Road 1, 2800 Lyngby" in content_text
    assert "Kaye ValProbe RT SN: MJT1 Channel: MJT1-A" in content_text
    assert "SIMVal SOP-TEMP-001" in content_text
    assert "Room temperature 23 +/- 2 deg C." in content_text
    assert "SIM-T-001" in content_text
    assert "IRTD" in content_text
    assert "IRT-123" in content_text
    assert "DANAK-CAL-12345" in content_text
    assert "-90 to 140 deg C" in content_text
    assert "Accredited calibration with SI traceability." in content_text
    assert "not captured in P4 preview model" not in content_text


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
        metadata=_metadata(),
        duts=(_dut(),),
        reference_equipment=(_reference_equipment(),),
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
    assert "Kaye ValProbe RT SN: MJT1 Channel: MJT1-A" in content_text
    assert "Kaye ValProbe RT SN: NWU2 Channel: NWU2-A" in content_text
    assert "Point point-001" in content_text
    assert "Point point-002" in content_text


def test_render_certificate_pdf_splits_large_dut_result_table_across_pages():
    artifact = render_certificate_pdf(
        certificate_id="cert-001",
        certificate_number="SIMVAL-CAL-0001",
        preview=_many_row_preview(),
    )

    content_text = artifact.content_bytes.decode("latin-1")
    assert "/Count 4" in content_text
    assert "Side 1 af 4 / Page 1 of 4" in content_text
    assert "Side 2 af 4 / Page 2 of 4" in content_text
    assert "Side 3 af 4 / Page 3 of 4" in content_text
    assert "Side 4 af 4 / Page 4 of 4" in content_text
    assert "Point point-001" in content_text
    assert "Point point-034" in content_text
    assert "Point point-035" in content_text
    assert "Point point-040" in content_text
    assert content_text.count("Referenceudstyr / Reference equipment:") == 1


def test_render_certificate_pdf_rejects_blank_certificate_number():
    with pytest.raises(CertificateRenderingError):
        render_certificate_pdf(
            certificate_id="cert-001",
            certificate_number=" ",
            preview=_preview(),
        )


def test_certificate_template_contract_accepts_rendered_certificate():
    preview = _preview()
    artifact = render_certificate_pdf(
        certificate_id="cert-001",
        certificate_number="SIMVAL-CAL-0001",
        preview=preview,
    )

    result = validate_certificate_template_contract(
        artifact=artifact,
        preview=preview,
        certificate_number="SIMVAL-CAL-0001",
    )

    assert "page_count" in result.checks
    assert "logo_scope" in result.checks
    assert "version_evidence" in result.checks


def test_certificate_template_contract_accepts_non_accredited_scope():
    preview = replace(_preview(), accreditation_mark_allowed=False)
    artifact = render_certificate_pdf(
        certificate_id="cert-001",
        certificate_number="SIMVAL-CAL-0001",
        preview=preview,
    )

    result = validate_certificate_template_contract(
        artifact=artifact,
        preview=preview,
        certificate_number="SIMVAL-CAL-0001",
    )

    assert "logo_scope" in result.checks


def test_certificate_template_contract_rejects_missing_required_marker():
    preview = _preview()
    artifact = render_certificate_pdf(
        certificate_id="cert-001",
        certificate_number="SIMVAL-CAL-0001",
        preview=preview,
    )
    modified_bytes = artifact.content_bytes.replace(
        b"Referenceudstyr / Reference equipment:",
        b"Reference equipment removed:",
    )
    invalid_artifact = RenderedCertificateArtifact(
        artifact_type=artifact.artifact_type,
        filename=artifact.filename,
        content_bytes=modified_bytes,
        checksum_sha256=hashlib.sha256(modified_bytes).hexdigest(),
    )

    with pytest.raises(
        CertificateTemplateContractError,
        match="Referenceudstyr / Reference equipment",
    ):
        validate_certificate_template_contract(
            artifact=invalid_artifact,
            preview=preview,
            certificate_number="SIMVAL-CAL-0001",
        )


def _image_draw(content_text: str, image_name: str) -> re.Match[str] | None:
    return re.search(
        rf"q\n(?P<width>[0-9.]+) 0 0 (?P<height>[0-9.]+) "
        rf"(?P<x>[0-9.]+) (?P<y>[0-9.]+) cm\n/{image_name} Do\nQ",
        content_text,
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
        metadata=_metadata(),
        duts=(_dut(),),
        reference_equipment=(_reference_equipment(),),
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
        metadata=_metadata(),
        duts=(
            _dut(),
            CertificatePreviewDut(
                dut_id="dut-002",
                make="Kaye",
                model="ValProbe RT",
                serial_number="NWU2",
                channel_id="NWU2-A",
            ),
        ),
        reference_equipment=(_reference_equipment(),),
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


def _many_row_preview() -> CertificatePreview:
    return CertificatePreview(
        job_id="job-001",
        generated_by="qa-001",
        generated_at=datetime(2026, 6, 1, 15, 20, tzinfo=timezone.utc),
        software_version="app-0.1.0",
        calculation_engine_version="calc-engine-0.1.0",
        constant_set_version="constants-2026-001",
        budget_version="budget-temp-001",
        template_version="template-2026-001",
        metadata=_metadata(),
        duts=(_dut(),),
        reference_equipment=(_reference_equipment(),),
        rows=tuple(
            CertificatePreviewRow(
                point_id=f"point-{index:03d}",
                dut_id="dut-001",
                measurement_window_id=f"window-{index:03d}",
                reference=-80.0305 + index,
                indication=-80.035 + index,
                error_of_indication=-0.0045,
                display_error_of_indication=Decimal("-0.004"),
                reported_expanded_uncertainty=Decimal("0.012"),
                unit="deg C",
            )
            for index in range(1, 41)
        ),
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
        traceability_statement=(
            "Measurements are metrologically traceable through calibrated "
            "reference equipment under ILAC/EA/DANAK principles."
        ),
        uncertainty_statement=(
            "The reported expanded uncertainty is based on standard uncertainty "
            "multiplied by coverage factor k=2."
        ),
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
