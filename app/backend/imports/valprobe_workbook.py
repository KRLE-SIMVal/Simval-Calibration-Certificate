"""Structural inspection for KAYE / ValProbe RT XLSX exports.

This is not the production import parser. It only supports P1 contract
checks against the controlled example workbook.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET


NS_MAIN = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
NS_REL = {
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
}


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


def _read_xml(archive: ZipFile, name: str) -> ET.Element:
    return ET.fromstring(archive.read(name))


def _read_shared_strings(archive: ZipFile) -> list[str]:
    root = _read_xml(archive, "xl/sharedStrings.xml")
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


def _cell_ref(cell: ET.Element) -> str:
    return cell.attrib.get("r", "")


def _cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    value = cell.find("m:v", NS_MAIN)
    if value is None or value.text is None:
        return ""
    if cell.attrib.get("t") == "s":
        return _normalize_text(shared_strings[int(value.text)])
    return _normalize_text(value.text)


def _normalize_text(value: str) -> str:
    return value.replace("\N{DEGREE SIGN}", "deg ")
