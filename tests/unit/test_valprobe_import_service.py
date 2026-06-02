from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

import pytest

from app.backend.audit.events import AuditAction
from app.backend.domain.entities import (
    CalibrationJob,
    Client,
    Discipline,
    MeasurementMode,
    UploadedFile,
    UploadedFileKind,
)
from app.backend.domain.workflow import WorkflowState
from app.backend.imports.valprobe_workbook import ValProbeWorkbookParseError
from app.backend.persistence.sqlite import (
    SQLiteAuditEventRepository,
    SQLiteCalibrationJobRepository,
    SQLiteParsedReadingRepository,
    SQLiteUploadedFileRepository,
    initialize_schema,
)
from app.backend.services.imports import (
    ImportServiceError,
    record_valprobe_temperature_import,
)


def _connection_with_job() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    SQLiteCalibrationJobRepository(connection).add(_job())
    return connection


def _job() -> CalibrationJob:
    return CalibrationJob(
        id="job-001",
        client=Client(name="SIMVal customer", address="Validated Road 1"),
        discipline=Discipline.TEMPERATURE,
        measurement_mode=MeasurementMode.AUTOMATIC,
        method="ValProbe RT linked XLSX/PDF workflow",
        created_by="operator-001",
        state=WorkflowState.DRAFT,
        created_at=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
    )


def _uploaded_file(file_kind: UploadedFileKind = UploadedFileKind.CALIBRATION_XLSX) -> UploadedFile:
    return UploadedFile(
        id="file-001",
        job_id="job-001",
        original_filename="sanitized-valprobe.xlsx",
        checksum_sha256="a" * 64,
        file_kind=file_kind,
        storage_uri="controlled-local://sanitized-valprobe.xlsx",
        parser_version="valprobe-xlsx-parser-v1",
        uploaded_at=datetime(2026, 6, 1, 14, 5, tzinfo=timezone.utc),
    )


def test_valprobe_import_service_persists_file_readings_and_audit_event(tmp_path):
    connection = _connection_with_job()
    workbook = tmp_path / "sanitized-valprobe.xlsx"
    _write_workbook(
        workbook,
        sheets={
            "Temperature": _temperature_sheet_xml(
                data_rows=[
                    ("2026-04-08T15:45:00+00:00", "-80.036"),
                    ("2026-04-08T15:46:00+00:00", "-80.034"),
                ],
            )
        },
    )

    result = record_valprobe_temperature_import(
        connection=connection,
        workbook_path=workbook,
        uploaded_file=_uploaded_file(),
        user_id="operator-001",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 14, 6, tzinfo=timezone.utc),
    )

    assert result.audit_event_id == 1
    assert result.reading_count == 2
    assert SQLiteUploadedFileRepository(connection).get("file-001") == _uploaded_file()
    assert len(SQLiteParsedReadingRepository(connection).list_for_uploaded_file("file-001")) == 2
    events = SQLiteAuditEventRepository(connection).list_for_entity(
        "uploaded_file",
        "file-001",
    )
    assert len(events) == 1
    assert events[0].action is AuditAction.PARSER_RESULT_RECORDED
    assert events[0].new_value == {
        "parser_version": "valprobe-xlsx-parser-v1",
        "reading_count": 2,
        "warning_count": 0,
    }


def test_valprobe_import_service_rejects_wrong_uploaded_file_kind(tmp_path):
    connection = _connection_with_job()
    workbook = tmp_path / "sanitized-valprobe.xlsx"
    _write_workbook(
        workbook,
        sheets={"Temperature": _temperature_sheet_xml(data_rows=[])},
    )

    with pytest.raises(ImportServiceError):
        record_valprobe_temperature_import(
            connection=connection,
            workbook_path=workbook,
            uploaded_file=_uploaded_file(UploadedFileKind.VERIFICATION_PDF),
            user_id="operator-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 14, 6, tzinfo=timezone.utc),
        )

    assert SQLiteUploadedFileRepository(connection).list_for_job("job-001") == ()
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "uploaded_file",
        "file-001",
    ) == ()


def test_valprobe_import_service_rolls_back_when_parser_fails(tmp_path):
    connection = _connection_with_job()
    workbook = tmp_path / "sanitized-valprobe.xlsx"
    _write_workbook(workbook, sheets={"Messages and Comments": _empty_sheet_xml()})

    with pytest.raises(ValProbeWorkbookParseError):
        record_valprobe_temperature_import(
            connection=connection,
            workbook_path=workbook,
            uploaded_file=_uploaded_file(),
            user_id="operator-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 14, 6, tzinfo=timezone.utc),
        )

    assert SQLiteUploadedFileRepository(connection).list_for_job("job-001") == ()
    assert SQLiteParsedReadingRepository(connection).list_for_uploaded_file("file-001") == ()
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "uploaded_file",
        "file-001",
    ) == ()


def _temperature_sheet_xml(*, data_rows: list[tuple[str, str]]) -> str:
    rows = [
        '<row r="7"><c r="B7" t="inlineStr"><is><t>Sensor1(°C)</t></is></c></row>',
        '<row r="8"><c r="B8" t="inlineStr"><is><t>MJT1-A</t></is></c></row>',
    ]
    for offset, (timestamp, value) in enumerate(data_rows, start=12):
        rows.append(
            f'<row r="{offset}">'
            f'<c r="A{offset}" t="inlineStr"><is><t>{timestamp}</t></is></c>'
            f'<c r="B{offset}"><v>{value}</v></c>'
            "</row>"
        )
    return _worksheet_xml(dimension=f"A7:B{11 + len(data_rows)}", rows=rows)


def _empty_sheet_xml() -> str:
    return _worksheet_xml(dimension="A1:A1", rows=[])


def _worksheet_xml(*, dimension: str, rows: list[str]) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<dimension ref="{dimension}"/><sheetData>'
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
        'Target="xl/workbook.xml"/></Relationships>'
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
        f"<sheets>{sheets}</sheets></workbook>"
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
