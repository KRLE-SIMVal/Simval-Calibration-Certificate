"""Deterministic certificate rendering from locked preview data."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
import re

from app.backend.certificates.preview import CertificatePreview, CertificatePreviewRow
from app.backend.certificates.records import ArtifactType


class CertificateRenderingError(ValueError):
    """Raised when certificate rendering inputs are incomplete or unsafe."""


_CERTIFICATE_NUMBER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass(frozen=True, slots=True)
class RenderedCertificateArtifact:
    artifact_type: ArtifactType
    filename: str
    content_bytes: bytes
    checksum_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.artifact_type, ArtifactType):
            raise CertificateRenderingError("Artifact type is invalid.")
        _require_text(self.filename, "Artifact filename")
        if len(self.content_bytes) == 0:
            raise CertificateRenderingError("Artifact content bytes are required.")
        calculated_checksum = hashlib.sha256(self.content_bytes).hexdigest()
        if self.checksum_sha256 != calculated_checksum:
            raise CertificateRenderingError(
                "Artifact checksum must match the content bytes."
            )


def render_certificate_pdf(
    *,
    certificate_id: str,
    certificate_number: str,
    preview: CertificatePreview,
) -> RenderedCertificateArtifact:
    """Render a minimal PDF artifact from locked preview rows.

    This renderer does not calculate certificate result values. It only formats
    values already locked into the certificate preview model.
    """
    _require_text(certificate_id, "Certificate id")
    _require_certificate_number(certificate_number)

    pages = tuple(
        _pdf_content_stream(page_lines)
        for page_lines in _certificate_pages(
            certificate_id=certificate_id,
            certificate_number=certificate_number,
            preview=preview,
        )
    )
    pdf_bytes = _pdf_document(pages)
    return RenderedCertificateArtifact(
        artifact_type=ArtifactType.PDF,
        filename=f"{certificate_number}.pdf",
        content_bytes=pdf_bytes,
        checksum_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
    )


def _certificate_pages(
    *,
    certificate_id: str,
    certificate_number: str,
    preview: CertificatePreview,
) -> tuple[tuple[str, ...], ...]:
    dut_groups = _group_rows_by_dut(preview.rows)
    total_pages = len(dut_groups) + 2
    pages = [
        _cover_page_lines(
            certificate_id=certificate_id,
            certificate_number=certificate_number,
            preview=preview,
            dut_ids=tuple(dut_groups),
            total_pages=total_pages,
        )
    ]
    for page_index, (dut_id, rows) in enumerate(dut_groups.items(), start=2):
        pages.append(
            _result_page_lines(
                certificate_number=certificate_number,
                dut_id=dut_id,
                rows=rows,
                page_number=page_index,
                total_pages=total_pages,
            )
        )
    pages.append(
        _reference_equipment_page_lines(
            certificate_number=certificate_number,
            preview=preview,
            page_number=total_pages,
            total_pages=total_pages,
        )
    )
    return tuple(pages)


def _cover_page_lines(
    *,
    certificate_id: str,
    certificate_number: str,
    preview: CertificatePreview,
    dut_ids: tuple[str, ...],
    total_pages: int,
) -> tuple[str, ...]:
    certificate_date = preview.generated_at.date().isoformat()
    item_text = dut_ids[0] if len(dut_ids) == 1 else ", ".join(dut_ids)
    return (
        "SIMVal A/S",
        "Kalibreringscertifikat",
        "Calibration certificate",
        _page_label(1, total_pages),
        f"Certifikat dato / Certificate date: {certificate_date}",
        f"Godkendt af / Approved by: {preview.generated_by}",
        "Digital Signatur / Digital Signature",
        f"Certifikat nummer / Certificate number: {certificate_number}",
        f"Certificate ID: {certificate_id}",
        f"Job ID: {preview.job_id}",
        "Rekvirent / Client: not captured in P4 preview model",
        f"Kalibreringsobjekt / Item calibrated: {item_text}",
        f"Kalibreringsdato / Date of calibration: {certificate_date}",
        f"Modtagelsesdato / Date of receipt: {certificate_date}",
        "Sporbarhed / Traceability:",
        (
            "This calibration certificate is intended to support metrological "
            "traceability under ILAC/EA/DANAK principles."
        ),
        "Kalibreringssted / Place of calibration: SIMVal laboratory",
        "Procedure / Procedure: SIMVal SOP for calibration",
        "Måleusikkerhed / Uncertainty:",
        (
            "Reported expanded uncertainty is based on standard uncertainty "
            "multiplied by coverage factor k=2."
        ),
        f"Template Version: {preview.template_version}",
        f"Software Version: {preview.software_version}",
        f"Calculation Engine Version: {preview.calculation_engine_version}",
        f"Constant Set Version: {preview.constant_set_version}",
        f"Budget Version: {preview.budget_version}",
        f"Preview Generated At: {preview.generated_at.isoformat()}",
        "SIMVal A/S | Lyngby Hovedgade 98 | DK-2800 Lyngby",
        "T: +45 XX XX XX XX | info@simval.dk | www.simval.dk",
    )


def _result_page_lines(
    *,
    certificate_number: str,
    dut_id: str,
    rows: tuple[CertificatePreviewRow, ...],
    page_number: int,
    total_pages: int,
) -> tuple[str, ...]:
    lines = [
        f"Certifikat nummer / Certificate number: {certificate_number}",
        _page_label(page_number, total_pages),
        "KALIBRERINGSCERTIFIKAT / Calibration Certificate",
        f"Kalibreringsobjekt / Item calibrated: DUT: {dut_id}",
        "Bemærkninger / Remarks: not captured in P4 preview model",
        "Omgivelsesforhold / Measurement conditions: not captured in P4 preview model",
        "Temperaturskala / Temperature scale: ITS-90",
        "Måleresultater / Measurement Results:",
        (
            "Reference value | Indication | Error of indication +/- expanded "
            "uncertainty"
        ),
    ]
    for row in rows:
        lines.append(_result_row_line(row))
    return tuple(lines)


def _reference_equipment_page_lines(
    *,
    certificate_number: str,
    preview: CertificatePreview,
    page_number: int,
    total_pages: int,
) -> tuple[str, ...]:
    return (
        f"Certifikat nummer / Certificate number: {certificate_number}",
        _page_label(page_number, total_pages),
        "Referenceudstyr / Reference equipment:",
        "Reference equipment selection is not yet captured in the P4 preview model.",
        "Released certificate evidence remains tied to:",
        f"Calculation Engine Version: {preview.calculation_engine_version}",
        f"Constant Set Version: {preview.constant_set_version}",
        f"Budget Version: {preview.budget_version}",
    )


def _result_row_line(row: CertificatePreviewRow) -> str:
    return " | ".join(
        (
            f"Point {row.point_id}",
            f"DUT {row.dut_id}",
            f"Window {row.measurement_window_id}",
            f"Reference {row.reference:g} {row.unit}",
            f"Indication {row.indication:g} {row.unit}",
            "Error "
            f"{_decimal_to_text(row.display_error_of_indication)} +/- "
            f"{_decimal_to_text(row.reported_expanded_uncertainty)} "
            f"{row.unit}",
        )
    )


def _group_rows_by_dut(
    rows: tuple[CertificatePreviewRow, ...],
) -> dict[str, tuple[CertificatePreviewRow, ...]]:
    grouped: dict[str, list[CertificatePreviewRow]] = {}
    for row in rows:
        grouped.setdefault(row.dut_id, []).append(row)
    return {dut_id: tuple(dut_rows) for dut_id, dut_rows in grouped.items()}


def _page_label(page_number: int, total_pages: int) -> str:
    return f"Side {page_number} af {total_pages} / Page {page_number} of {total_pages}"


def _pdf_content_stream(lines: tuple[str, ...]) -> bytes:
    content_lines = ["BT", "/F1 10 Tf", "50 800 Td"]
    emitted_lines = 0
    for line in lines:
        for wrapped_line in _wrap_line(line):
            if emitted_lines > 0:
                content_lines.append("0 -14 Td")
            content_lines.append(f"({_escape_pdf_text(wrapped_line)}) Tj")
            emitted_lines += 1
    content_lines.append("ET")
    return ("\n".join(content_lines) + "\n").encode("latin-1")


def _pdf_document(page_contents: tuple[bytes, ...]) -> bytes:
    page_count = len(page_contents)
    page_object_numbers = tuple(range(4, 4 + page_count))
    content_object_numbers = tuple(range(4 + page_count, 4 + page_count * 2))
    kids = " ".join(f"{number} 0 R" for number in page_object_numbers)
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>".encode("ascii"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for content_number in content_object_numbers:
        objects.append(
            (
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                b"/Resources << /Font << /F1 3 0 R >> >> /Contents "
                + f"{content_number} 0 R".encode("ascii")
                + b" >>"
            )
        )
    for content in page_contents:
        objects.append(
            b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n"
            + content
            + b"endstream"
        )

    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for object_number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{object_number} 0 obj\n".encode("ascii"))
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(output)


def _wrap_line(line: str, limit: int = 92) -> tuple[str, ...]:
    if len(line) <= limit:
        return (line,)
    words = line.split(" ")
    wrapped: list[str] = []
    current = ""
    for word in words:
        candidate = word if current == "" else f"{current} {word}"
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            wrapped.append(current)
        current = word
    if current:
        wrapped.append(current)
    return tuple(wrapped)


def _escape_pdf_text(value: str) -> str:
    encoded = value.encode("latin-1", errors="replace").decode("latin-1")
    return encoded.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _decimal_to_text(value: Decimal) -> str:
    return format(value, "f")


def _require_certificate_number(value: str) -> None:
    _require_text(value, "Certificate number")
    if _CERTIFICATE_NUMBER_PATTERN.fullmatch(value) is None:
        raise CertificateRenderingError(
            "Certificate number must be safe for artifact filenames."
        )


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise CertificateRenderingError(f"{field_name} is required.")
