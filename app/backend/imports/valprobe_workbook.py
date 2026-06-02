"""Structural inspection for KAYE / ValProbe RT XLSX exports.

This is not the production import parser. It only supports P1 contract
checks against the controlled example workbook.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path
import re
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from app.backend.domain.entities import MeasurementReading, SourceLocation


NS_MAIN = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
NS_REL = {
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
}
NS_PACKAGE_REL = {
    "p": "http://schemas.openxmlformats.org/package/2006/relationships"
}
RELATIONSHIP_ID = (
    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
)
_CELL_REF_PATTERN = re.compile(r"^([A-Z]+)([0-9]+)$")
_EXCEL_EPOCH = datetime(1899, 12, 30, tzinfo=timezone.utc)


@dataclass(frozen=True, slots=True)
class WorkbookStructure:
    sheet_names: tuple[str, ...]
    temperature_range: str
    messages_range: str
    temperature_populated_rows: int
    messages_populated_rows: int
    sensor_headers: tuple[str, ...]
    logger_ids: tuple[str, ...]
    first_numeric_data_row: int


class ValProbeWorkbookParseError(ValueError):
    """Raised when a ValProbe workbook cannot be parsed safely."""


@dataclass(frozen=True, slots=True)
class ParsedValProbeChannel:
    sensor_header: str
    logger_id: str
    unit: str
    column_label: str


@dataclass(frozen=True, slots=True)
class ParsedValProbeWorkbook:
    sheet_name: str
    parser_version: str
    channels: tuple[ParsedValProbeChannel, ...]
    readings: tuple[MeasurementReading, ...]
    warnings: tuple[str, ...]


def inspect_valprobe_workbook(path: Path) -> WorkbookStructure:
    """Inspect the controlled workbook structure without parsing measurements."""
    with ZipFile(path) as archive:
        shared_strings = _read_shared_strings(archive)
        sheet_names = _read_sheet_names(archive)
        temperature = _read_xml(archive, "xl/worksheets/sheet1.xml")
        messages = _read_xml(archive, "xl/worksheets/sheet2.xml")

    temp_rows = _rows(temperature)
    msg_rows = _rows(messages)
    row_7 = _row_by_number(temp_rows, 7)
    row_8 = _row_by_number(temp_rows, 8)

    sensor_headers = tuple(
        _cell_value(cell, shared_strings)
        for cell in row_7
        if _cell_ref(cell) != "A7"
    )
    logger_ids = tuple(
        value
        for value in (_cell_value(cell, shared_strings) for cell in row_8)
        if value
    )

    return WorkbookStructure(
        sheet_names=tuple(sheet_names),
        temperature_range=_dimension_ref(temperature),
        messages_range=_dimension_ref(messages),
        temperature_populated_rows=len(temp_rows),
        messages_populated_rows=len(msg_rows),
        sensor_headers=sensor_headers,
        logger_ids=logger_ids,
        first_numeric_data_row=12,
    )


def parse_valprobe_temperature_workbook(
    path: Path,
    *,
    uploaded_file_id: str,
    parser_version: str,
    default_timezone: tzinfo = timezone.utc,
) -> ParsedValProbeWorkbook:
    """Parse a ValProbe-style temperature XLSX into traceable readings."""
    if uploaded_file_id.strip() == "":
        raise ValProbeWorkbookParseError("uploaded_file_id is required.")
    if parser_version.strip() == "":
        raise ValProbeWorkbookParseError("parser_version is required.")
    with ZipFile(path) as archive:
        shared_strings = _read_shared_strings(archive)
        sheet_paths = _read_sheet_paths(archive)
        try:
            temperature_path = sheet_paths["Temperature"]
        except KeyError as exc:
            raise ValProbeWorkbookParseError(
                "ValProbe workbook must contain a Temperature sheet."
            ) from exc
        temperature = _read_xml(archive, temperature_path)

    rows = {int(row.attrib["r"]): row for row in _rows(temperature)}
    row_7 = _row_cells_by_column(rows, 7)
    row_8 = _row_cells_by_column(rows, 8)
    channels = _parse_channels(row_7=row_7, row_8=row_8, shared_strings=shared_strings)
    if not channels:
        raise ValProbeWorkbookParseError(
            "ValProbe workbook Temperature sheet has no logger channels."
        )

    readings: list[MeasurementReading] = []
    warnings: list[str] = []
    for row_number in sorted(number for number in rows if number >= 12):
        cells = _cells_by_column(rows[row_number])
        timestamp_value = _cell_value(cells.get("A"), shared_strings)
        if timestamp_value == "":
            warnings.append(
                f"Skipped row {row_number} in Temperature because timestamp is missing."
            )
            continue
        try:
            timestamp = _parse_timestamp(timestamp_value, default_timezone)
        except ValueError:
            warnings.append(
                f"Skipped row {row_number} in Temperature because timestamp is invalid."
            )
            continue
        for channel in channels:
            cell = cells.get(channel.column_label)
            raw_value = _cell_value(cell, shared_strings)
            if raw_value == "":
                continue
            try:
                reading_value = float(raw_value)
            except ValueError:
                warnings.append(
                    "Skipped nonnumeric value at "
                    f"Temperature!{channel.column_label}{row_number} "
                    f"for channel {channel.logger_id}."
                )
                continue
            readings.append(
                MeasurementReading(
                    timestamp=timestamp,
                    channel_id=channel.logger_id,
                    value=reading_value,
                    unit=channel.unit,
                    source=SourceLocation(
                        uploaded_file_id=uploaded_file_id,
                        source_label="Temperature",
                        row_number=row_number,
                        column_label=channel.column_label,
                    ),
                )
            )

    return ParsedValProbeWorkbook(
        sheet_name="Temperature",
        parser_version=parser_version,
        channels=channels,
        readings=tuple(readings),
        warnings=tuple(warnings),
    )


def _read_xml(archive: ZipFile, name: str) -> ET.Element:
    return ET.fromstring(archive.read(name))


def _read_shared_strings(archive: ZipFile) -> list[str]:
    try:
        root = _read_xml(archive, "xl/sharedStrings.xml")
    except KeyError:
        return []
    values: list[str] = []
    for item in root.findall("m:si", NS_MAIN):
        texts = [node.text or "" for node in item.findall(".//m:t", NS_MAIN)]
        values.append("".join(texts))
    return values


def _read_sheet_names(archive: ZipFile) -> list[str]:
    root = _read_xml(archive, "xl/workbook.xml")
    return [
        sheet.attrib["name"]
        for sheet in root.findall("m:sheets/m:sheet", NS_MAIN)
    ]


def _read_sheet_paths(archive: ZipFile) -> dict[str, str]:
    workbook = _read_xml(archive, "xl/workbook.xml")
    relationships = _read_xml(archive, "xl/_rels/workbook.xml.rels")
    targets = {
        relationship.attrib["Id"]: relationship.attrib["Target"]
        for relationship in relationships.findall("p:Relationship", NS_PACKAGE_REL)
    }
    sheet_paths: dict[str, str] = {}
    for sheet in workbook.findall("m:sheets/m:sheet", NS_MAIN):
        relationship_id = sheet.attrib[RELATIONSHIP_ID]
        target = targets[relationship_id]
        if target.startswith("/"):
            path = target.lstrip("/")
        else:
            path = f"xl/{target}"
        sheet_paths[sheet.attrib["name"]] = path
    return sheet_paths


def _dimension_ref(root: ET.Element) -> str:
    dimension = root.find("m:dimension", NS_MAIN)
    if dimension is None:
        return ""
    return dimension.attrib["ref"]


def _rows(root: ET.Element) -> list[ET.Element]:
    return root.findall("m:sheetData/m:row", NS_MAIN)


def _row_by_number(rows: list[ET.Element], number: int) -> list[ET.Element]:
    for row in rows:
        if int(row.attrib["r"]) == number:
            return row.findall("m:c", NS_MAIN)
    raise ValueError(f"Workbook row {number} was not found.")


def _row_cells_by_column(
    rows: dict[int, ET.Element],
    number: int,
) -> dict[str, ET.Element]:
    if number not in rows:
        raise ValProbeWorkbookParseError(f"Workbook row {number} was not found.")
    return _cells_by_column(rows[number])


def _cells_by_column(row: ET.Element) -> dict[str, ET.Element]:
    cells: dict[str, ET.Element] = {}
    for cell in row.findall("m:c", NS_MAIN):
        cell_ref = _cell_ref(cell)
        match = _CELL_REF_PATTERN.fullmatch(cell_ref)
        if match is not None:
            cells[match.group(1)] = cell
    return cells


def _cell_ref(cell: ET.Element) -> str:
    return cell.attrib.get("r", "")


def _cell_value(cell: ET.Element | None, shared_strings: list[str]) -> str:
    if cell is None:
        return ""
    if cell.attrib.get("t") == "inlineStr":
        inline_texts = [node.text or "" for node in cell.findall(".//m:t", NS_MAIN)]
        return _normalize_text("".join(inline_texts))
    value = cell.find("m:v", NS_MAIN)
    if value is None or value.text is None:
        return ""
    if cell.attrib.get("t") == "s":
        return _normalize_text(shared_strings[int(value.text)])
    return _normalize_text(value.text)


def _normalize_text(value: str) -> str:
    return value.replace("\N{DEGREE SIGN}", "deg ")


def _parse_channels(
    *,
    row_7: dict[str, ET.Element],
    row_8: dict[str, ET.Element],
    shared_strings: list[str],
) -> tuple[ParsedValProbeChannel, ...]:
    channels: list[ParsedValProbeChannel] = []
    for column_label in sorted(row_8, key=_column_index):
        if column_label == "A":
            continue
        logger_id = _cell_value(row_8.get(column_label), shared_strings)
        if logger_id == "":
            continue
        sensor_header = _cell_value(row_7.get(column_label), shared_strings)
        channels.append(
            ParsedValProbeChannel(
                sensor_header=sensor_header,
                logger_id=logger_id,
                unit=_unit_from_sensor_header(sensor_header),
                column_label=column_label,
            )
        )
    return tuple(channels)


def _unit_from_sensor_header(sensor_header: str) -> str:
    match = re.search(r"\(([^)]+)\)", sensor_header)
    if match is None:
        return "deg C"
    unit = match.group(1).strip()
    if unit == "degC":
        return "deg C"
    return unit


def _parse_timestamp(value: str, default_timezone: tzinfo) -> datetime:
    stripped = value.strip()
    try:
        numeric_value = float(stripped)
    except ValueError:
        parsed = datetime.fromisoformat(stripped.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            parsed = parsed.replace(tzinfo=default_timezone)
        return parsed
    timestamp = _EXCEL_EPOCH + timedelta(days=numeric_value)
    return timestamp.astimezone(default_timezone)


def _column_index(column_label: str) -> int:
    index = 0
    for char in column_label:
        index = index * 26 + (ord(char) - ord("A") + 1)
    return index
