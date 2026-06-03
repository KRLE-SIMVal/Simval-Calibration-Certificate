"""Deterministic certificate rendering from locked preview data."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
import re

from app.backend.certificates.preview import CertificatePreview
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

    content = _pdf_content_stream(
        _certificate_lines(
            certificate_id=certificate_id,
            certificate_number=certificate_number,
            preview=preview,
        )
    )
    pdf_bytes = _pdf_document(content)
    return RenderedCertificateArtifact(
        artifact_type=ArtifactType.PDF,
        filename=f"{certificate_number}.pdf",
        content_bytes=pdf_bytes,
        checksum_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
    )


def _certificate_lines(
    *,
    certificate_id: str,
    certificate_number: str,
    preview: CertificatePreview,
) -> tuple[str, ...]:
    lines = [
        "SIMVal Calibration Certificate",
        f"Certificate ID: {certificate_id}",
        f"Certificate Number: {certificate_number}",
        f"Job ID: {preview.job_id}",
        f"Template Version: {preview.template_version}",
        f"Software Version: {preview.software_version}",
        f"Calculation Engine Version: {preview.calculation_engine_version}",
        f"Constant Set Version: {preview.constant_set_version}",
        f"Budget Version: {preview.budget_version}",
        f"Preview Generated At: {preview.generated_at.isoformat()}",
        "Results:",
    ]
    for row in preview.rows:
        lines.append(
            " | ".join(
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
        )
    return tuple(lines)


def _pdf_content_stream(lines: tuple[str, ...]) -> bytes:
    content_lines = ["BT", "/F1 11 Tf", "50 800 Td"]
    for index, line in enumerate(lines):
        if index > 0:
            content_lines.append("0 -16 Td")
        content_lines.append(f"({_escape_pdf_text(line)}) Tj")
    content_lines.append("ET")
    return ("\n".join(content_lines) + "\n").encode("latin-1")


def _pdf_document(content: bytes) -> bytes:
    objects = (
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n"
        + content
        + b"endstream",
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
