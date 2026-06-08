import asyncio
import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

import httpx

from app.backend.api.app import create_app
from app.backend.audit.events import AuditAction
from app.backend.auth.permissions import Role
from app.backend.auth.users import UserAccount, UserSession
from app.backend.domain.workflow import WorkflowState
from app.backend.persistence.sqlite import (
    SQLiteAuditEventRepository,
    SQLiteCalibrationJobRepository,
    SQLiteDeviceUnderTestRepository,
    SQLiteParsedReadingRepository,
    SQLiteRequiredTemperatureSetpointRepository,
    SQLiteUploadedFileRepository,
    SQLiteUserAccountRepository,
    SQLiteUserSessionRepository,
    initialize_schema,
)


def test_api_create_calibration_job_records_job_and_audit_event():
    connection = _connection_with_user()

    response = _api_request(
        create_app(connection=connection, clock=_fixed_now),
        "POST",
        "/calibration-jobs",
        headers={"X-Session-Id": "session-001"},
        json=_job_payload(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == "job-001"
    assert payload["created_by"] == "user-001"
    assert payload["state"] == "draft"
    assert payload["audit_event_id"] == 1
    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.DRAFT
    )
    events = SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    )
    assert events[0].action is AuditAction.JOB_CREATED


def test_api_upload_calibration_xlsx_stores_raw_file_and_parser_evidence(tmp_path):
    connection = _connection_with_user_and_job()
    workbook = tmp_path / "sanitized-valprobe.xlsx"
    _write_workbook(
        workbook,
        sheets={
            "Temperature": _temperature_sheet_xml(
                data_rows=[("2026-04-08T15:45:00+00:00", "-80.036")]
            )
        },
    )
    app = create_app(
        connection=connection,
        clock=_fixed_now,
        artifact_directory=tmp_path / "artifacts",
        id_factory=lambda: "001",
    )

    response = _api_request(
        app,
        "POST",
        (
            "/calibration-jobs/job-001/files?"
            "original_filename=sanitized-valprobe.xlsx&"
            "file_kind=calibration_xlsx&"
            "software_version=app-0.1.0"
        ),
        headers={
            "X-Session-Id": "session-001",
            "Content-Type": "application/octet-stream",
        },
        content=workbook.read_bytes(),
    )

    assert response.status_code == 200
    payload = response.json()
    stored_path = tmp_path / "artifacts" / "uploads" / "job-001" / (
        "file-001-sanitized-valprobe.xlsx"
    )
    assert stored_path.read_bytes() == workbook.read_bytes()
    assert payload["uploaded_file_id"] == "file-001"
    assert payload["checksum_sha256"] == hashlib.sha256(
        workbook.read_bytes()
    ).hexdigest()
    assert payload["storage_uri"] == (
        "controlled-local://uploads/job-001/file-001-sanitized-valprobe.xlsx"
    )
    assert payload["parser_status"] == "parsed"
    assert payload["reading_count"] == 1
    assert payload["warning_count"] == 0
    assert SQLiteUploadedFileRepository(connection).get("file-001").storage_uri == (
        "controlled-local://uploads/job-001/file-001-sanitized-valprobe.xlsx"
    )
    assert len(SQLiteParsedReadingRepository(connection).list_for_uploaded_file("file-001")) == 1
    events = SQLiteAuditEventRepository(connection).list_for_entity(
        "uploaded_file",
        "file-001",
    )
    assert [event.action for event in events] == [
        AuditAction.FILE_UPLOADED,
        AuditAction.PARSER_RESULT_RECORDED,
    ]


def test_api_upload_verification_pdf_stores_raw_file_without_parser(tmp_path):
    connection = _connection_with_user_and_job()
    app = create_app(
        connection=connection,
        clock=_fixed_now,
        artifact_directory=tmp_path / "artifacts",
        id_factory=lambda: "002",
    )

    response = _api_request(
        app,
        "POST",
        (
            "/calibration-jobs/job-001/files?"
            "original_filename=verification.pdf&"
            "file_kind=verification_pdf&"
            "software_version=app-0.1.0"
        ),
        headers={
            "X-Session-Id": "session-001",
            "Content-Type": "application/octet-stream",
        },
        content=b"%PDF-1.4 controlled verification fixture",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["uploaded_file_id"] == "file-002"
    assert payload["parser_status"] == "stored_only"
    assert payload["parser_audit_event_id"] is None
    assert payload["reading_count"] == 0
    assert payload["warning_count"] == 1
    assert "deferred" in payload["warnings"][0]
    assert (tmp_path / "artifacts" / "uploads" / "job-001" / "file-002-verification.pdf").exists()


def test_api_import_review_returns_uploaded_file_and_parser_evidence(tmp_path):
    connection = _connection_with_user_and_job()
    workbook = tmp_path / "sanitized-valprobe.xlsx"
    _write_workbook(
        workbook,
        sheets={
            "Temperature": _temperature_sheet_xml(
                data_rows=[("2026-04-08T15:45:00+00:00", "-80.036")]
            )
        },
    )
    app = create_app(
        connection=connection,
        clock=_fixed_now,
        artifact_directory=tmp_path / "artifacts",
        id_factory=lambda: "001",
    )
    upload_response = _api_request(
        app,
        "POST",
        (
            "/calibration-jobs/job-001/files?"
            "original_filename=sanitized-valprobe.xlsx&"
            "file_kind=calibration_xlsx&"
            "software_version=app-0.1.0"
        ),
        headers={
            "X-Session-Id": "session-001",
            "Content-Type": "application/octet-stream",
        },
        content=workbook.read_bytes(),
    )
    assert upload_response.status_code == 200

    response = _api_request(
        app,
        "GET",
        "/calibration-jobs/job-001/imports",
        headers={"X-Session-Id": "session-001"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == "job-001"
    assert payload["reviewed_by"] == "user-001"
    assert len(payload["files"]) == 1
    file_review = payload["files"][0]
    assert file_review["uploaded_file_id"] == "file-001"
    assert file_review["original_filename"] == "sanitized-valprobe.xlsx"
    assert file_review["file_kind"] == "calibration_xlsx"
    assert file_review["parser_status"] == "parsed"
    assert file_review["reading_count"] == 1
    assert file_review["warning_count"] == 0
    assert file_review["uploaded_by"] == "user-001"
    assert file_review["size_bytes"] == len(workbook.read_bytes())


def test_api_import_review_rejects_read_only_user(tmp_path):
    connection = _connection_with_user_and_job()
    SQLiteUserAccountRepository(connection).update_roles(
        user_id="user-001",
        roles=(Role.READ_ONLY,),
    )

    response = _api_request(
        create_app(connection=connection, clock=_fixed_now),
        "GET",
        "/calibration-jobs/job-001/imports",
        headers={"X-Session-Id": "session-001"},
    )

    assert response.status_code == 403


def test_api_prepare_temperature_data_entry_creates_duts_setpoints_and_state(
    tmp_path,
):
    connection = _connection_with_user_and_job()
    workbook = tmp_path / "sanitized-valprobe.xlsx"
    _write_workbook(
        workbook,
        sheets={
            "Temperature": _temperature_sheet_xml(
                data_rows=[
                    ("2026-04-08T15:45:00+00:00", "-80.036"),
                    ("2026-04-08T15:46:00+00:00", "-80.034"),
                ]
            )
        },
    )
    app = create_app(
        connection=connection,
        clock=_fixed_now,
        artifact_directory=tmp_path / "artifacts",
        id_factory=lambda: "001",
    )
    upload_response = _api_request(
        app,
        "POST",
        (
            "/calibration-jobs/job-001/files?"
            "original_filename=sanitized-valprobe.xlsx&"
            "file_kind=calibration_xlsx&"
            "software_version=app-0.1.0"
        ),
        headers={
            "X-Session-Id": "session-001",
            "Content-Type": "application/octet-stream",
        },
        content=workbook.read_bytes(),
    )
    assert upload_response.status_code == 200
    connection.execute(
        "UPDATE calibration_jobs SET state = ? WHERE id = ?",
        (WorkflowState.EQUIPMENT_SELECTED.value, "job-001"),
    )
    connection.commit()

    response = _api_request(
        app,
        "POST",
        "/calibration-jobs/job-001/temperature-data-entry",
        headers={"X-Session-Id": "session-001"},
        json={
            "calibration_uploaded_file_id": "file-001",
            "setpoints": [-80.0],
            "unit": "deg C",
            "software_version": "app-0.1.0",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == "job-001"
    assert payload["state"] == "data_entered"
    assert payload["dut_ids"] == ["dut-MJT1-A"]
    assert payload["setpoint_ids"] == ["setpoint-001"]
    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.DATA_ENTERED
    )
    assert SQLiteDeviceUnderTestRepository(connection).list_for_job("job-001")[
        0
    ].channel_id == "MJT1-A"
    assert SQLiteRequiredTemperatureSetpointRepository(connection).list_for_job(
        "job-001"
    )[0].setpoint == -80.0
    events = SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    )
    assert [event.action for event in events][-2:] == [
        AuditAction.DATA_ENTRY_RECORDED,
        AuditAction.WORKFLOW_TRANSITIONED,
    ]


def test_api_prepare_temperature_data_entry_rejects_before_equipment_selected(
    tmp_path,
):
    connection = _connection_with_user_and_job()
    workbook = tmp_path / "sanitized-valprobe.xlsx"
    _write_workbook(
        workbook,
        sheets={
            "Temperature": _temperature_sheet_xml(
                data_rows=[("2026-04-08T15:45:00+00:00", "-80.036")]
            )
        },
    )
    app = create_app(
        connection=connection,
        clock=_fixed_now,
        artifact_directory=tmp_path / "artifacts",
        id_factory=lambda: "001",
    )
    upload_response = _api_request(
        app,
        "POST",
        (
            "/calibration-jobs/job-001/files?"
            "original_filename=sanitized-valprobe.xlsx&"
            "file_kind=calibration_xlsx&"
            "software_version=app-0.1.0"
        ),
        headers={
            "X-Session-Id": "session-001",
            "Content-Type": "application/octet-stream",
        },
        content=workbook.read_bytes(),
    )
    assert upload_response.status_code == 200

    response = _api_request(
        app,
        "POST",
        "/calibration-jobs/job-001/temperature-data-entry",
        headers={"X-Session-Id": "session-001"},
        json={
            "calibration_uploaded_file_id": "file-001",
            "setpoints": [-80.0],
            "unit": "deg C",
            "software_version": "app-0.1.0",
        },
    )

    assert response.status_code == 409
    assert "equipment_selected" in response.json()["detail"]
    assert SQLiteDeviceUnderTestRepository(connection).list_for_job("job-001") == ()
    assert SQLiteRequiredTemperatureSetpointRepository(connection).list_for_job(
        "job-001"
    ) == ()


def test_api_prepare_temperature_data_entry_rejects_duplicate_generated_dut_ids(
    tmp_path,
):
    connection = _connection_with_user_and_job()
    workbook = tmp_path / "sanitized-valprobe.xlsx"
    _write_workbook(
        workbook,
        sheets={
            "Temperature": _temperature_sheet_xml(
                channels=("MJT1 A", "MJT1_A"),
                data_rows=[("2026-04-08T15:45:00+00:00", "-80.036", "-80.034")],
            )
        },
    )
    app = create_app(
        connection=connection,
        clock=_fixed_now,
        artifact_directory=tmp_path / "artifacts",
        id_factory=lambda: "001",
    )
    upload_response = _api_request(
        app,
        "POST",
        (
            "/calibration-jobs/job-001/files?"
            "original_filename=sanitized-valprobe.xlsx&"
            "file_kind=calibration_xlsx&"
            "software_version=app-0.1.0"
        ),
        headers={
            "X-Session-Id": "session-001",
            "Content-Type": "application/octet-stream",
        },
        content=workbook.read_bytes(),
    )
    assert upload_response.status_code == 200
    connection.execute(
        "UPDATE calibration_jobs SET state = ? WHERE id = ?",
        (WorkflowState.EQUIPMENT_SELECTED.value, "job-001"),
    )
    connection.commit()

    response = _api_request(
        app,
        "POST",
        "/calibration-jobs/job-001/temperature-data-entry",
        headers={"X-Session-Id": "session-001"},
        json={
            "calibration_uploaded_file_id": "file-001",
            "setpoints": [-80.0],
            "unit": "deg C",
            "software_version": "app-0.1.0",
        },
    )

    assert response.status_code == 409
    assert "unique controlled DUT IDs" in response.json()["detail"]
    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.EQUIPMENT_SELECTED
    )
    assert SQLiteDeviceUnderTestRepository(connection).list_for_job("job-001") == ()
    assert SQLiteRequiredTemperatureSetpointRepository(connection).list_for_job(
        "job-001"
    ) == ()


def test_api_upload_rejects_missing_artifact_storage_before_file_write():
    connection = _connection_with_user_and_job()

    response = _api_request(
        create_app(connection=connection, clock=_fixed_now, id_factory=lambda: "001"),
        "POST",
        (
            "/calibration-jobs/job-001/files?"
            "original_filename=sanitized-valprobe.xlsx&"
            "file_kind=calibration_xlsx&"
            "software_version=app-0.1.0"
        ),
        headers={
            "X-Session-Id": "session-001",
            "Content-Type": "application/octet-stream",
        },
        content=b"content",
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Artifact storage path is not configured."
    assert SQLiteUploadedFileRepository(connection).list_for_job("job-001") == ()


def test_api_upload_rejects_read_only_user_before_file_write(tmp_path):
    connection = _connection_with_user_and_job()
    SQLiteUserAccountRepository(connection).update_roles(
        user_id="user-001",
        roles=(Role.READ_ONLY,),
    )

    response = _api_request(
        create_app(
            connection=connection,
            clock=_fixed_now,
            artifact_directory=tmp_path,
            id_factory=lambda: "001",
        ),
        "POST",
        (
            "/calibration-jobs/job-001/files?"
            "original_filename=sanitized-valprobe.xlsx&"
            "file_kind=calibration_xlsx&"
            "software_version=app-0.1.0"
        ),
        headers={
            "X-Session-Id": "session-001",
            "Content-Type": "application/octet-stream",
        },
        content=b"content",
    )

    assert response.status_code == 403
    assert list(tmp_path.iterdir()) == []
    assert SQLiteUploadedFileRepository(connection).list_for_job("job-001") == ()


def _api_request(app, method: str, url: str, **kwargs) -> httpx.Response:
    return asyncio.run(_async_api_request(app, method, url, **kwargs))


async def _async_api_request(app, method: str, url: str, **kwargs) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.request(method, url, **kwargs)


def _connection_with_user(
    *,
    user_roles: tuple[Role, ...] = (Role.OPERATOR,),
) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    initialize_schema(connection)
    SQLiteUserAccountRepository(connection).add(_user(user_roles))
    SQLiteUserSessionRepository(connection).add(_session())
    return connection


def _connection_with_user_and_job(
    *,
    user_roles: tuple[Role, ...] = (Role.OPERATOR,),
) -> sqlite3.Connection:
    connection = _connection_with_user(user_roles=user_roles)
    response = _api_request(
        create_app(connection=connection, clock=_fixed_now),
        "POST",
        "/calibration-jobs",
        headers={"X-Session-Id": "session-001"},
        json=_job_payload(),
    )
    assert response.status_code == 200
    return connection


def _fixed_now() -> datetime:
    return datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc)


def _job_payload() -> dict:
    return {
        "job_id": "job-001",
        "client_name": "SIMVal customer",
        "client_address": "Validated Road 1",
        "discipline": "temperature",
        "measurement_mode": "automatic",
        "method": "ValProbe RT linked XLSX/PDF workflow",
        "software_version": "app-0.1.0",
    }


def _user(roles: tuple[Role, ...]) -> UserAccount:
    return UserAccount(
        id="user-001",
        display_name="Operator User",
        email="operator@example.com",
        roles=roles,
        active=True,
        created_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
    )


def _session() -> UserSession:
    return UserSession(
        id="session-001",
        user_id="user-001",
        issued_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 1, 16, 0, tzinfo=timezone.utc),
    )


def _temperature_sheet_xml(
    *,
    data_rows: list[tuple[str, ...]],
    channels: tuple[str, ...] = ("MJT1-A",),
) -> str:
    header_cells = "".join(
        f'<c r="{_column_label(index + 2)}7" t="inlineStr">'
        f"<is><t>Sensor{index + 1}(deg C)</t></is></c>"
        for index, _channel in enumerate(channels)
    )
    channel_cells = "".join(
        f'<c r="{_column_label(index + 2)}8" t="inlineStr">'
        f"<is><t>{channel}</t></is></c>"
        for index, channel in enumerate(channels)
    )
    rows = [
        f'<row r="7">{header_cells}</row>',
        f'<row r="8">{channel_cells}</row>',
    ]
    for offset, row in enumerate(data_rows, start=12):
        timestamp = row[0]
        values = row[1:]
        if len(values) != len(channels):
            raise ValueError("Temperature fixture row must match channel count.")
        measurement_cells = "".join(
            f'<c r="{_column_label(index + 2)}{offset}"><v>{value}</v></c>'
            for index, value in enumerate(values)
        )
        rows.append(
            f'<row r="{offset}">'
            f'<c r="A{offset}" t="inlineStr"><is><t>{timestamp}</t></is></c>'
            f"{measurement_cells}"
            "</row>"
        )
    last_column = _column_label(len(channels) + 1)
    return _worksheet_xml(dimension=f"A7:{last_column}{11 + len(data_rows)}", rows=rows)


def _column_label(index: int) -> str:
    if index < 1:
        raise ValueError("Column index must be positive.")
    label = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        label = chr(ord("A") + remainder) + label
    return label


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
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            _workbook_relationships_xml(sheet_entries),
        )
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
