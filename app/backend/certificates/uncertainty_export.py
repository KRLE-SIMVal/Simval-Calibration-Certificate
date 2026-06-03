"""Deterministic XLSX export for locked uncertainty budget calculation evidence."""

from __future__ import annotations

from decimal import Decimal
import hashlib
from io import BytesIO
from math import isfinite
import re
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from app.backend.certificates.records import ArtifactType
from app.backend.certificates.rendering import RenderedCertificateArtifact
from app.calculation_engine.temperature.results import (
    AutomaticTemperaturePointCalculation,
)


class UncertaintyBudgetExportError(ValueError):
    """Raised when uncertainty budget export evidence cannot be generated."""


_CERTIFICATE_NUMBER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def render_uncertainty_budget_xlsx(
    *,
    certificate_number: str,
    calculation: AutomaticTemperaturePointCalculation,
    coverage_factor: float,
) -> RenderedCertificateArtifact:
    """Render an XLSX budget artifact from an existing calculation result.

    The workbook formats locked calculation output. It does not recalculate
    uncertainty, CMC, rounding, or certificate result values.
    """
    _require_certificate_number(certificate_number)
    if not isinstance(calculation, AutomaticTemperaturePointCalculation):
        raise UncertaintyBudgetExportError("Calculation result is invalid.")
    if not isfinite(coverage_factor) or coverage_factor <= 0:
        raise UncertaintyBudgetExportError("Coverage factor must be finite and > 0.")

    filename = f"{certificate_number}-uncertainty-budget.xlsx"
    content_bytes = _xlsx_bytes(
        _worksheet_rows(certificate_number, calculation, coverage_factor)
    )
    return RenderedCertificateArtifact(
        artifact_type=ArtifactType.XLSX,
        filename=filename,
        content_bytes=content_bytes,
        checksum_sha256=hashlib.sha256(content_bytes).hexdigest(),
    )


def _worksheet_rows(
    certificate_number: str,
    calculation: AutomaticTemperaturePointCalculation,
    coverage_factor: float,
) -> tuple[tuple[object, ...], ...]:
    summary = calculation.summary
    rows: list[tuple[object, ...]] = [
        ("Uncertainty Budget",),
        ("certificate_number", certificate_number),
        ("job_id", summary.job_id),
        ("point_id", summary.point_id),
        ("dut_id", summary.dut_id),
        ("measurement_window_id", summary.measurement_window_id),
        ("calculation_engine_version", summary.calculation_engine_version),
        ("constant_set_version", summary.constant_set_version),
        ("budget_version", summary.budget_version),
        ("coverage_factor", coverage_factor),
        (
            "name",
            "standard_uncertainty",
            "sensitivity_coefficient",
            "effective_standard_uncertainty",
        ),
    ]
    rows.extend(
        (
            contribution.name,
            contribution.standard_uncertainty,
            contribution.sensitivity_coefficient,
            contribution.effective_standard_uncertainty,
        )
        for contribution in calculation.contributions
    )
    rows.extend(
        (
            ("combined_standard_uncertainty", calculation.combined_standard_uncertainty),
            (
                "calculated_expanded_uncertainty",
                calculation.calculated_expanded_uncertainty,
            ),
            ("cmc_floor", summary.cmc_floor),
            ("reported_expanded_uncertainty", summary.reported_expanded_uncertainty),
            ("display_error_of_indication", summary.display_error_of_indication),
        )
    )
    return tuple(rows)


def _xlsx_bytes(rows: tuple[tuple[object, ...], ...]) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as workbook:
        _write_part(workbook, "[Content_Types].xml", _content_types_xml())
        _write_part(workbook, "_rels/.rels", _root_relationships_xml())
        _write_part(workbook, "xl/workbook.xml", _workbook_xml())
        _write_part(workbook, "xl/_rels/workbook.xml.rels", _workbook_relationships_xml())
        _write_part(workbook, "xl/worksheets/sheet1.xml", _worksheet_xml(rows))
    return output.getvalue()


def _write_part(workbook: ZipFile, path: str, content: str) -> None:
    info = ZipInfo(path, date_time=_FIXED_ZIP_TIMESTAMP)
    info.compress_type = ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    workbook.writestr(info, content.encode("utf-8"))


def _content_types_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )


def _root_relationships_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )


def _workbook_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<sheets>"
        '<sheet name="Budget" sheetId="1" r:id="rId1"/>'
        "</sheets>"
        "</workbook>"
    )


def _workbook_relationships_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )


def _worksheet_xml(rows: tuple[tuple[object, ...], ...]) -> str:
    sheet_rows = "".join(
        _worksheet_row(row_index, values)
        for row_index, values in enumerate(rows, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{sheet_rows}</sheetData>"
        "</worksheet>"
    )


def _worksheet_row(row_index: int, values: tuple[object, ...]) -> str:
    cells = "".join(
        _worksheet_cell(row_index=row_index, column_index=column_index, value=value)
        for column_index, value in enumerate(values, start=1)
    )
    return f'<row r="{row_index}">{cells}</row>'


def _worksheet_cell(*, row_index: int, column_index: int, value: object) -> str:
    reference = f"{_column_name(column_index)}{row_index}"
    if isinstance(value, int | float | Decimal):
        return f'<c r="{reference}"><v>{_number_text(value)}</v></c>'
    return (
        f'<c r="{reference}" t="inlineStr">'
        f"<is><t>{escape(str(value))}</t></is>"
        "</c>"
    )


def _column_name(index: int) -> str:
    name = ""
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _number_text(value: int | float | Decimal) -> str:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, int):
        return str(value)
    if not isfinite(value):
        raise UncertaintyBudgetExportError("Workbook numeric values must be finite.")
    return format(value, ".12g")


def _require_certificate_number(value: str) -> None:
    if value.strip() == "":
        raise UncertaintyBudgetExportError("Certificate number is required.")
    if _CERTIFICATE_NUMBER_PATTERN.fullmatch(value) is None:
        raise UncertaintyBudgetExportError(
            "Certificate number must be safe for artifact filenames."
        )
