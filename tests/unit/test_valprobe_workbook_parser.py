from __future__ import annotations

from datetime import timezone
from pathlib import Path
from zipfile import ZipFile

import pytest

from app.backend.imports.valprobe_workbook import (
    ValProbeWorkbookParseError,
    parse_valprobe_temperature_workbook,
)


def test_valprobe_parser_reads_sanitized_temperature_workbook(tmp_path):
    workbook = tmp_path / "sanitized-valprobe.xlsx"
    _write_workbook(
        workbook,
        sheets={
            "Temperature": _temperature_sheet_xml(
                data_rows=[
                    ("2026-04-08T15:45:00+00:00", "-80.036", "-80.041"),
                    ("2026-04-08T15:46:00+00:00", "-80.034", "-80.040"),
                ],
            ),
            "Messages and Comments": _empty_sheet_xml(),
        },
    )

    parsed = parse_valprobe_temperature_workbook(
        workbook,
        uploaded_file_id="file-001",
        parser_version="valprobe-xlsx-parser-v1",
    )

    assert parsed.sheet_name == "Temperature"
    assert parsed.parser_version == "valprobe-xlsx-parser-v1"
    assert parsed.channels[0].logger_id == "MJT1-A"
    assert parsed.channels[0].sensor_header == "Sensor1(deg C)"
    assert parsed.channels[0].unit == "deg C"
    assert parsed.channels[1].logger_id == "NWU2-A"
    assert len(parsed.readings) == 4
    first = parsed.readings[0]
    assert first.timestamp.tzinfo is not None
    assert first.timestamp.utcoffset() == timezone.utc.utcoffset(first.timestamp)
    assert first.channel_id == "MJT1-A"
    assert first.value == pytest.approx(-80.036)
    assert first.unit == "deg C"
    assert first.source.uploaded_file_id == "file-001"
    assert first.source.source_label == "Temperature"
    assert first.source.row_number == 12
    assert first.source.column_label == "B"
    assert parsed.warnings == ()


def test_valprobe_parser_skips_blank_measurement_cells(tmp_path):
    workbook = tmp_path / "sanitized-valprobe.xlsx"
    _write_workbook(
        workbook,
        sheets={
            "Temperature": _temperature_sheet_xml(
                data_rows=[
                    ("2026-04-08T15:45:00+00:00", "-80.036", ""),
                    ("2026-04-08T15:46:00+00:00", "", "-80.040"),
                ],
            ),
        },
    )

    parsed = parse_valprobe_temperature_workbook(
        workbook,
        uploaded_file_id="file-001",
        parser_version="valprobe-xlsx-parser-v1",
    )

    assert [reading.channel_id for reading in parsed.readings] == ["MJT1-A", "NWU2-A"]
    assert parsed.warnings == ()


def test_valprobe_parser_rejects_missing_temperature_sheet(tmp_path):
    workbook = tmp_path / "sanitized-valprobe.xlsx"
    _write_workbook(workbook, sheets={"Messages and Comments": _empty_sheet_xml()})

    with pytest.raises(ValProbeWorkbookParseError):
        parse_valprobe_temperature_workbook(
            workbook,
            uploaded_file_id="file-001",
            parser_version="valprobe-xlsx-parser-v1",
        )


def test_valprobe_parser_warns_and_skips_nonnumeric_measurement(tmp_path):
    workbook = tmp_path / "sanitized-valprobe.xlsx"
    _write_workbook(
        workbook,
        sheets={
            "Temperature": _temperature_sheet_xml(
                data_rows=[
                    ("2026-04-08T15:45:00+00:00", "not-a-number", "-80.041"),
                ],
            ),
        },
    )

    parsed = parse_valprobe_temperature_workbook(
        workbook,
        uploaded_file_id="file-001",
        parser_version="valprobe-xlsx-parser-v1",
    )

    assert len(parsed.readings) == 1
    assert parsed.readings[0].channel_id == "NWU2-A"
    assert parsed.warnings == (
        "Skipped nonnumeric value at Temperature!B12 for channel MJT1-A.",
    )


def _temperature_sheet_xml(*, data_rows: list[tuple[str, str, str]]) -> str:
    rows = [
        '<row r="7">'
        '<c r="B7" t="inlineStr"><is><t>Sensor1(°C)</t></is></c>'
        '<c r="C7" t="inlineStr"><is><t>Sensor2(°C)</t></is></c>'
        "</row>",
        '<row r="8">'
        '<c r="B8" t="inlineStr"><is><t>MJT1-A</t></is></c>'
        '<c r="C8" t="inlineStr"><is><t>NWU2-A</t></is></c>'
        "</row>",
    ]
    for offset, (timestamp, first, second) in enumerate(data_rows, start=12):
        rows.append(
            f'<row r="{offset}">'
            f'<c r="A{offset}" t="inlineStr"><is><t>{timestamp}</t></is></c>'
            f'<c r="B{offset}"><v>{first}</v></c>'
            f'<c r="C{offset}"><v>{second}</v></c>'
            "</row>"
        )
    dimension = f"A7:C{11 + len(data_rows)}"
    return _worksheet_xml(dimension=dimension, rows=rows)


def _empty_sheet_xml() -> str:
    return _worksheet_xml(dimension="A1:A1", rows=[])


def _worksheet_xml(*, dimension: str, rows: list[str]) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<dimension ref="{dimension}"/>'
        "<sheetData>"
        + "".join(rows)
        + "</sheetData></worksheet>"
    )


def _write_workbook(path: Path, *, sheets: dict[str, str]) -> None:
    sheet_entries = list(sheets.items())
    with ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", _content_types_xml(len(sheet_entries)))
        archive.writestr("_rels/.rels", _root_relationships_xml())
        archive.writestr("xl/workbook.xml", _workbook_xml(sheet_entries))
        archive.writestr("xl/_rels/workbook.xml.rels", _workbook_relationships_xml(sheet_entries))
        for index, (_name, xml) in enumerate(sheet_entries, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", xml)


def _content_types_xml(sheet_count: int) -> str:
    sheet_overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index in range(1, sheet_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        + sheet_overrides
        + "</Types>"
    )


def _root_relationships_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        "</Relationships>"
    )


def _workbook_xml(sheet_entries: list[tuple[str, str]]) -> str:
    sheets = "".join(
        f'<sheet name="{name}" sheetId="{index}" r:id="rId{index}"/>'
        for index, (name, _xml) in enumerate(sheet_entries, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{sheets}</sheets>"
        "</workbook>"
    )


def _workbook_relationships_xml(sheet_entries: list[tuple[str, str]]) -> str:
    relationships = "".join(
        f'<Relationship Id="rId{index}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{index}.xml"/>'
        for index, _entry in enumerate(sheet_entries, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + relationships
        + "</Relationships>"
    )
