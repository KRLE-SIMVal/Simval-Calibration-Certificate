"""Deterministic certificate rendering from locked preview data."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
from pathlib import Path
import re
import struct
import zlib

from app.backend.certificates.preview import (
    CertificatePreview,
    CertificatePreviewDut,
    CertificatePreviewRow,
)
from app.backend.certificates.records import ArtifactType
from app.backend.domain.entities import Discipline


class CertificateRenderingError(ValueError):
    """Raised when certificate rendering inputs are incomplete or unsafe."""


_CERTIFICATE_NUMBER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_MAX_RESULT_ROWS_PER_PAGE = 34
_PDF_PAGE_WIDTH = 595.0
_LOGO_TOP_Y = 814.0


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


@dataclass(frozen=True, slots=True)
class CertificateLogoAssets:
    simval_logo_path: Path | str | None = None
    danak_logo_path: Path | str | None = None


@dataclass(frozen=True, slots=True)
class _PdfImage:
    name: str
    width: int
    height: int
    rgb_bytes: bytes


@dataclass(frozen=True, slots=True)
class _ImageDraw:
    image_name: str
    width: float
    height: float
    x: float
    y: float


def render_certificate_pdf(
    *,
    certificate_id: str,
    certificate_number: str,
    preview: CertificatePreview,
    logo_assets: CertificateLogoAssets | None = None,
) -> RenderedCertificateArtifact:
    """Render a minimal PDF artifact from locked preview rows.

    This renderer does not calculate certificate result values. It only formats
    values already locked into the certificate preview model.
    """
    _require_text(certificate_id, "Certificate id")
    _require_certificate_number(certificate_number)

    images = _load_logo_images(
        logo_assets or default_certificate_logo_assets(),
        include_danak=preview.accreditation_mark_allowed,
    )
    page_lines = _certificate_pages(
        certificate_id=certificate_id,
        certificate_number=certificate_number,
        preview=preview,
    )
    pages = tuple(
        _pdf_content_stream(
            lines,
            image_draws=_cover_logo_draws(images) if index == 0 else (),
        )
        for index, lines in enumerate(page_lines)
    )
    pdf_bytes = _pdf_document(pages, images=images)
    return RenderedCertificateArtifact(
        artifact_type=ArtifactType.PDF,
        filename=f"{certificate_number}.pdf",
        content_bytes=pdf_bytes,
        checksum_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
    )


def default_certificate_logo_assets() -> CertificateLogoAssets:
    repo_root = Path(__file__).resolve().parents[3]
    design_doc_dir = repo_root / "Docs" / "Design Document"
    return CertificateLogoAssets(
        simval_logo_path=design_doc_dir / "Logo - SIMVal.png",
        danak_logo_path=design_doc_dir / "DANAK Logo 647.png",
    )


def _certificate_pages(
    *,
    certificate_id: str,
    certificate_number: str,
    preview: CertificatePreview,
) -> tuple[tuple[str, ...], ...]:
    dut_groups = _group_rows_by_dut(preview.rows)
    duts_by_id = _duts_by_id(preview.duts)
    result_sections = tuple(
        (dut_id, row_chunk)
        for dut_id, rows in dut_groups.items()
        for row_chunk in _result_row_chunks(rows)
    )
    total_pages = len(result_sections) + 2
    pages = [
        _cover_page_lines(
            certificate_id=certificate_id,
            certificate_number=certificate_number,
            preview=preview,
            duts=tuple(duts_by_id[dut_id] for dut_id in dut_groups),
            total_pages=total_pages,
        )
    ]
    for page_index, (dut_id, rows) in enumerate(result_sections, start=2):
        pages.append(
            _result_page_lines(
                certificate_number=certificate_number,
                dut=duts_by_id[dut_id],
                preview=preview,
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
    duts: tuple[CertificatePreviewDut, ...],
    total_pages: int,
) -> tuple[str, ...]:
    metadata = preview.metadata
    item_text = (
        duts[0].display_name
        if len(duts) == 1
        else f"{len(duts)} devices: " + ", ".join(dut.display_name for dut in duts)
    )
    return (
        "SIMVal A/S",
        "Kalibreringscertifikat",
        "Calibration certificate",
        _accreditation_line(preview.accreditation_mark_allowed),
        _page_label(1, total_pages),
        f"Certifikat dato / Certificate date: {metadata.certificate_date.isoformat()}",
        f"Godkendt af / Approved by: {metadata.approved_by_label}",
        "Digital Signatur / Digital Signature",
        f"Certifikat nummer / Certificate number: {certificate_number}",
        f"Certificate ID: {certificate_id}",
        f"Job ID: {preview.job_id}",
        f"Tasknummer / Task number: {metadata.task_number}",
        f"Rekvisitionsnummer / Purchase order: {metadata.purchase_order}",
        f"Rekvirent / Client: {metadata.client_name}",
        f"Client address: {metadata.client_address}",
        f"Kalibreringsobjekt / Item calibrated: {item_text}",
        (
            "Kalibreringsdato / Date of calibration: "
            f"{metadata.calibration_date.isoformat()}"
        ),
        f"Modtagelsesdato / Date of receipt: {metadata.receipt_date.isoformat()}",
        "Sporbarhed / Traceability:",
        metadata.traceability_statement,
        f"Kalibreringssted / Place of calibration: {metadata.place}",
        f"Procedure / Procedure: {metadata.procedure}",
        "Måleusikkerhed / Uncertainty:",
        metadata.uncertainty_statement,
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
    dut: CertificatePreviewDut,
    preview: CertificatePreview,
    rows: tuple[CertificatePreviewRow, ...],
    page_number: int,
    total_pages: int,
) -> tuple[str, ...]:
    lines = [
        f"Certifikat nummer / Certificate number: {certificate_number}",
        _page_label(page_number, total_pages),
        "KALIBRERINGSCERTIFIKAT / Calibration Certificate",
        f"Kalibreringsobjekt / Item calibrated: {dut.display_name}",
        f"Bemærkninger / Remarks: {preview.metadata.remarks}",
        (
            "Omgivelsesforhold / Measurement conditions: "
            f"{preview.metadata.ambient_conditions}"
        ),
        f"{_scale_or_unit_label(preview.discipline)}: "
        f"{preview.metadata.temperature_scale}",
        _measurement_results_label(preview.discipline),
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
    lines = [
        f"Certifikat nummer / Certificate number: {certificate_number}",
        _page_label(page_number, total_pages),
        "Referenceudstyr / Reference equipment:",
    ]
    for equipment in preview.reference_equipment:
        lines.append(
            " | ".join(
                (
                    f"SIMVal ID {equipment.simval_id}",
                    f"Type {equipment.equipment_type}",
                    f"Serial {equipment.serial_number}",
                    (
                        "Certificate "
                        f"{equipment.calibration_certificate_reference}"
                    ),
                    f"Due {equipment.calibration_due_date.isoformat()}",
                    f"Range {equipment.range_text}",
                )
            )
        )
        lines.append(f"Traceability: {equipment.traceability_statement}")
    lines.extend(
        (
            "Released certificate evidence remains tied to:",
            f"Calculation Engine Version: {preview.calculation_engine_version}",
            f"Constant Set Version: {preview.constant_set_version}",
            f"Budget Version: {preview.budget_version}",
        )
    )
    return tuple(lines)


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


def _scale_or_unit_label(discipline: Discipline) -> str:
    if discipline is Discipline.PRESSURE:
        return "Trykenhed / Pressure unit"
    return "Temperaturskala / Temperature scale"


def _measurement_results_label(discipline: Discipline) -> str:
    if discipline is Discipline.PRESSURE:
        return "Trykresultater / Pressure results:"
    return "Måleresultater / Measurement Results:"


def _group_rows_by_dut(
    rows: tuple[CertificatePreviewRow, ...],
) -> dict[str, tuple[CertificatePreviewRow, ...]]:
    grouped: dict[str, list[CertificatePreviewRow]] = {}
    for row in rows:
        grouped.setdefault(row.dut_id, []).append(row)
    return {dut_id: tuple(dut_rows) for dut_id, dut_rows in grouped.items()}


def _result_row_chunks(
    rows: tuple[CertificatePreviewRow, ...],
) -> tuple[tuple[CertificatePreviewRow, ...], ...]:
    return tuple(
        rows[index : index + _MAX_RESULT_ROWS_PER_PAGE]
        for index in range(0, len(rows), _MAX_RESULT_ROWS_PER_PAGE)
    )


def _duts_by_id(
    duts: tuple[CertificatePreviewDut, ...],
) -> dict[str, CertificatePreviewDut]:
    return {dut.dut_id: dut for dut in duts}


def _page_label(page_number: int, total_pages: int) -> str:
    return f"Side {page_number} af {total_pages} / Page {page_number} of {total_pages}"


def _pdf_content_stream(
    lines: tuple[str, ...],
    *,
    image_draws: tuple[_ImageDraw, ...] = (),
) -> bytes:
    content_lines: list[str] = []
    for draw in image_draws:
        content_lines.extend(
            (
                "q",
                (
                    f"{_pdf_number(draw.width)} 0 0 {_pdf_number(draw.height)} "
                    f"{_pdf_number(draw.x)} {_pdf_number(draw.y)} cm"
                ),
                f"/{draw.image_name} Do",
                "Q",
            )
        )
    text_start_y = 660 if image_draws else 800
    content_lines.extend(("BT", "/F1 10 Tf", f"50 {text_start_y} Td"))
    emitted_lines = 0
    for line in lines:
        for wrapped_line in _wrap_line(line):
            if emitted_lines > 0:
                content_lines.append("0 -14 Td")
            content_lines.append(f"({_escape_pdf_text(wrapped_line)}) Tj")
            emitted_lines += 1
    content_lines.append("ET")
    return ("\n".join(content_lines) + "\n").encode("latin-1")


def _pdf_document(
    page_contents: tuple[bytes, ...],
    *,
    images: tuple[_PdfImage, ...] = (),
) -> bytes:
    page_count = len(page_contents)
    page_object_numbers = tuple(range(4, 4 + page_count))
    content_object_numbers = tuple(range(4 + page_count, 4 + page_count * 2))
    first_image_object_number = 4 + page_count * 2
    image_object_numbers = {
        image.name: first_image_object_number + index
        for index, image in enumerate(images)
    }
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
                b"/Resources "
                + _page_resources(image_object_numbers)
                + b" /Contents "
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
    for image in images:
        objects.append(_pdf_image_object(image))

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


def _page_resources(image_object_numbers: dict[str, int]) -> bytes:
    if not image_object_numbers:
        return b"<< /Font << /F1 3 0 R >> >>"
    xobjects = " ".join(
        f"/{name} {object_number} 0 R"
        for name, object_number in image_object_numbers.items()
    )
    return (
        b"<< /Font << /F1 3 0 R >> /XObject << "
        + xobjects.encode("ascii")
        + b" >> >>"
    )


def _pdf_image_object(image: _PdfImage) -> bytes:
    compressed_rgb = zlib.compress(image.rgb_bytes)
    return (
        (
            "<< /Type /XObject /Subtype /Image "
            f"/Width {image.width} /Height {image.height} "
            "/ColorSpace /DeviceRGB /BitsPerComponent 8 "
            f"/Filter /FlateDecode /Length {len(compressed_rgb)} >>\n"
            "stream\n"
        ).encode("ascii")
        + compressed_rgb
        + b"\nendstream"
    )


def _load_logo_images(
    logo_assets: CertificateLogoAssets,
    *,
    include_danak: bool,
) -> tuple[_PdfImage, ...]:
    logo_paths = (
        ("ImSimval", logo_assets.simval_logo_path),
        ("ImDanak", logo_assets.danak_logo_path),
    )
    loaded: list[_PdfImage] = []
    for image_name, raw_path in logo_paths:
        if image_name == "ImDanak" and not include_danak:
            continue
        if raw_path is None:
            continue
        path = Path(raw_path)
        if not path.is_file():
            continue
        loaded.append(_decode_png_for_pdf(path=path, image_name=image_name))
    return tuple(loaded)


def _cover_logo_draws(images: tuple[_PdfImage, ...]) -> tuple[_ImageDraw, ...]:
    draws: list[_ImageDraw] = []
    for image in images:
        if image.name == "ImSimval":
            width = 120.0
            height = _scaled_height(image=image, width=width)
            draws.append(
                _ImageDraw(
                    image_name=image.name,
                    width=width,
                    height=height,
                    x=50.0,
                    y=_LOGO_TOP_Y - height,
                )
            )
        elif image.name == "ImDanak":
            width = 95.0
            height = _scaled_height(image=image, width=width)
            draws.append(
                _ImageDraw(
                    image_name=image.name,
                    width=width,
                    height=height,
                    x=_PDF_PAGE_WIDTH - 50.0 - width,
                    y=_LOGO_TOP_Y - height,
                )
            )
    return tuple(draws)


def _scaled_height(*, image: _PdfImage, width: float) -> float:
    return width * image.height / image.width


def _decode_png_for_pdf(*, path: Path, image_name: str) -> _PdfImage:
    try:
        png = _decode_png(path.read_bytes())
    except (OSError, ValueError, zlib.error, struct.error) as exc:
        raise CertificateRenderingError(
            f"Certificate logo asset is not a supported PNG: {path}"
        ) from exc
    return _PdfImage(
        name=image_name,
        width=png.width,
        height=png.height,
        rgb_bytes=png.rgb_bytes,
    )


@dataclass(frozen=True, slots=True)
class _DecodedPng:
    width: int
    height: int
    rgb_bytes: bytes


def _decode_png(data: bytes) -> _DecodedPng:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("PNG signature is missing.")
    offset = 8
    width: int | None = None
    height: int | None = None
    bit_depth: int | None = None
    color_type: int | None = None
    idat_chunks: list[bytes] = []
    while offset < len(data):
        chunk_length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_data_start = offset + 8
        chunk_data_end = chunk_data_start + chunk_length
        chunk_data = data[chunk_data_start:chunk_data_end]
        offset = chunk_data_end + 4
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(
                ">IIBB", chunk_data[:10]
            )
        elif chunk_type == b"IDAT":
            idat_chunks.append(chunk_data)
        elif chunk_type == b"IEND":
            break
    if width is None or height is None or bit_depth is None or color_type is None:
        raise ValueError("PNG IHDR chunk is missing.")
    if width <= 0 or height <= 0:
        raise ValueError("PNG dimensions must be positive.")
    if bit_depth != 8:
        raise ValueError("Only 8-bit PNG assets are supported.")
    channel_count = _png_channel_count(color_type)
    scanlines = _unfilter_png_scanlines(
        raw=zlib.decompress(b"".join(idat_chunks)),
        width=width,
        height=height,
        channel_count=channel_count,
    )
    return _DecodedPng(
        width=width,
        height=height,
        rgb_bytes=_png_scanlines_to_rgb(
            scanlines=scanlines,
            color_type=color_type,
            channel_count=channel_count,
        ),
    )


def _png_channel_count(color_type: int) -> int:
    if color_type == 0:
        return 1
    if color_type == 2:
        return 3
    if color_type == 4:
        return 2
    if color_type == 6:
        return 4
    raise ValueError("Only grayscale, RGB, and RGBA PNG assets are supported.")


def _unfilter_png_scanlines(
    *,
    raw: bytes,
    width: int,
    height: int,
    channel_count: int,
) -> tuple[bytes, ...]:
    row_length = width * channel_count
    expected_length = height * (row_length + 1)
    if len(raw) != expected_length:
        raise ValueError("PNG scanline data length is invalid.")
    rows: list[bytes] = []
    previous = bytearray(row_length)
    offset = 0
    for _row_index in range(height):
        filter_type = raw[offset]
        offset += 1
        row = bytearray(raw[offset : offset + row_length])
        offset += row_length
        for index in range(row_length):
            left = row[index - channel_count] if index >= channel_count else 0
            up = previous[index]
            upper_left = (
                previous[index - channel_count] if index >= channel_count else 0
            )
            if filter_type == 0:
                adjustment = 0
            elif filter_type == 1:
                adjustment = left
            elif filter_type == 2:
                adjustment = up
            elif filter_type == 3:
                adjustment = (left + up) // 2
            elif filter_type == 4:
                adjustment = _paeth_predictor(left, up, upper_left)
            else:
                raise ValueError("PNG filter type is unsupported.")
            row[index] = (row[index] + adjustment) & 0xFF
        rows.append(bytes(row))
        previous = row
    return tuple(rows)


def _png_scanlines_to_rgb(
    *,
    scanlines: tuple[bytes, ...],
    color_type: int,
    channel_count: int,
) -> bytes:
    output = bytearray()
    for row in scanlines:
        for index in range(0, len(row), channel_count):
            pixel = row[index : index + channel_count]
            if color_type == 0:
                output.extend((pixel[0], pixel[0], pixel[0]))
            elif color_type == 2:
                output.extend(pixel)
            elif color_type == 4:
                output.extend(_blend_gray_alpha(pixel[0], pixel[1]))
            elif color_type == 6:
                output.extend(
                    _blend_rgb_alpha(pixel[0], pixel[1], pixel[2], pixel[3])
                )
            else:
                raise ValueError("PNG color type is unsupported.")
    return bytes(output)


def _blend_gray_alpha(gray: int, alpha: int) -> tuple[int, int, int]:
    blended = _blend_channel_with_white(gray, alpha)
    return (blended, blended, blended)


def _blend_rgb_alpha(
    red: int,
    green: int,
    blue: int,
    alpha: int,
) -> tuple[int, int, int]:
    return (
        _blend_channel_with_white(red, alpha),
        _blend_channel_with_white(green, alpha),
        _blend_channel_with_white(blue, alpha),
    )


def _blend_channel_with_white(value: int, alpha: int) -> int:
    return (value * alpha + 255 * (255 - alpha) + 127) // 255


def _paeth_predictor(left: int, up: int, upper_left: int) -> int:
    estimate = left + up - upper_left
    distance_left = abs(estimate - left)
    distance_up = abs(estimate - up)
    distance_upper_left = abs(estimate - upper_left)
    if distance_left <= distance_up and distance_left <= distance_upper_left:
        return left
    if distance_up <= distance_upper_left:
        return up
    return upper_left


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


def _pdf_number(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _accreditation_line(accreditation_mark_allowed: bool) -> str:
    if accreditation_mark_allowed:
        return "Accreditation mark: DANAK/ILAC CAL Reg.nr. 647"
    return "Accreditation mark: not applied for this certificate scope."


def _require_certificate_number(value: str) -> None:
    _require_text(value, "Certificate number")
    if _CERTIFICATE_NUMBER_PATTERN.fullmatch(value) is None:
        raise CertificateRenderingError(
            "Certificate number must be safe for artifact filenames."
        )


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise CertificateRenderingError(f"{field_name} is required.")
