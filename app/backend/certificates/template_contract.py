"""Template-contract validation for rendered certificate artifacts."""

from __future__ import annotations

from dataclasses import dataclass
import re

from app.backend.certificates.preview import CertificatePreview
from app.backend.certificates.records import ArtifactType
from app.backend.certificates.rendering import RenderedCertificateArtifact


class CertificateTemplateContractError(ValueError):
    """Raised when a rendered certificate fails the approved template contract."""


@dataclass(frozen=True, slots=True)
class CertificateTemplateValidationResult:
    checks: tuple[str, ...]


def validate_certificate_template_contract(
    *,
    artifact: RenderedCertificateArtifact,
    preview: CertificatePreview,
    certificate_number: str,
) -> CertificateTemplateValidationResult:
    """Validate rendered PDF content against the approved P7 template contract.

    This validates structure and evidence emitted by the renderer. It does not
    inspect or recalculate measurement values.
    """
    blockers: list[str] = []
    if artifact.artifact_type is not ArtifactType.PDF:
        blockers.append("Rendered certificate artifact must be a PDF.")
    if not artifact.content_bytes.startswith(b"%PDF-1.4\n"):
        blockers.append("Rendered certificate must be a PDF 1.4 document.")
    text = artifact.content_bytes.decode("latin-1", errors="replace")
    expected_page_count = _expected_page_count(preview)
    _require_text(text, f"/Count {expected_page_count}", blockers)
    _require_text(text, f"Certificate number: {certificate_number}", blockers)
    for marker in _required_template_markers(preview):
        _require_text(text, marker, blockers)
    _validate_logo_scope(text, preview, blockers)
    if "placeholder" in text.lower():
        blockers.append("Rendered certificate must not contain placeholder text.")
    if blockers:
        raise CertificateTemplateContractError("; ".join(blockers))
    return CertificateTemplateValidationResult(
        checks=(
            "pdf_header",
            "page_count",
            "certificate_number",
            "cover_structure",
            "result_structure",
            "reference_equipment_structure",
            "version_evidence",
            "logo_scope",
            "no_placeholder_text",
        )
    )


def _expected_page_count(preview: CertificatePreview) -> int:
    dut_ids = tuple(dict.fromkeys(row.dut_id for row in preview.rows))
    result_pages = 0
    for dut_id in dut_ids:
        row_count = sum(1 for row in preview.rows if row.dut_id == dut_id)
        result_pages += max(1, (row_count + 33) // 34)
    return result_pages + 2


def _required_template_markers(preview: CertificatePreview) -> tuple[str, ...]:
    return (
        "Kalibreringscertifikat",
        "Calibration certificate",
        "Sporbarhed / Traceability:",
        "Måleusikkerhed / Uncertainty:",
        "Måleresultater / Measurement Results:",
        "Referenceudstyr / Reference equipment:",
        "Released certificate evidence remains tied to:",
        f"Template Version: {preview.template_version}",
        f"Software Version: {preview.software_version}",
        f"Calculation Engine Version: {preview.calculation_engine_version}",
        f"Constant Set Version: {preview.constant_set_version}",
        f"Budget Version: {preview.budget_version}",
    )


def _validate_logo_scope(
    text: str,
    preview: CertificatePreview,
    blockers: list[str],
) -> None:
    simval_width = _image_draw_width(text, "ImSimval")
    if simval_width is None:
        blockers.append("Rendered certificate must include the SIMVal logo.")
    danak_width = _image_draw_width(text, "ImDanak")
    if preview.accreditation_mark_allowed:
        if danak_width is None:
            blockers.append(
                "Rendered accredited certificate must include the DANAK/ILAC mark."
            )
        elif simval_width is not None and simval_width <= danak_width:
            blockers.append("SIMVal logo must be larger than the DANAK/ILAC mark.")
        _require_text(text, "Accreditation mark: DANAK/ILAC CAL Reg.nr. 647", blockers)
    else:
        if danak_width is not None or "/ImDanak" in text:
            blockers.append(
                "Rendered non-accredited-scope certificate must not include the DANAK/ILAC mark."
            )
        _require_text(
            text,
            "Accreditation mark: not applied for this certificate scope.",
            blockers,
        )


def _image_draw_width(text: str, image_name: str) -> float | None:
    pattern = re.compile(
        rf"(?P<width>\d+(?:\.\d+)?) 0 0 \d+(?:\.\d+)? "
        rf"\d+(?:\.\d+)? \d+(?:\.\d+)? cm\n/{image_name} Do"
    )
    match = pattern.search(text)
    if match is None:
        return None
    return float(match.group("width"))


def _require_text(text: str, marker: str, blockers: list[str]) -> None:
    if marker not in text:
        blockers.append(f"Rendered certificate is missing required text: {marker}")
