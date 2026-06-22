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
from app.backend.domain.entities import Discipline, UploadedFileKind
from app.backend.domain.workflow import WorkflowState
from app.backend.persistence.sqlite import (
    SQLiteAuditEventRepository,
    SQLiteCalibrationJobRepository,
    SQLiteCertificateRecordRepository,
    SQLiteDeviceUnderTestRepository,
    SQLiteLinkedTemperatureReadingRepository,
    SQLiteMeasurementPointSummaryRepository,
    SQLiteMeasurementWindowRepository,
    SQLiteParsedReadingRepository,
    SQLiteRequiredTemperatureSetpointRepository,
    SQLiteUploadedFileRepository,
    SQLiteUserAccountRepository,
    SQLiteUserSessionRepository,
    initialize_schema,
)
from app.backend.services.source_file_uploads import MAX_UPLOAD_SIZE_BYTES


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


def test_api_create_calibration_job_rejects_disabled_pressure_discipline():
    connection = _connection_with_user()
    payload = _job_payload()
    payload["discipline"] = "pressure"

    response = _api_request(
        create_app(connection=connection, clock=_fixed_now),
        "POST",
        "/calibration-jobs",
        headers={"X-Session-Id": "session-001"},
        json=payload,
    )

    assert response.status_code == 409
    assert "not enabled" in response.json()["detail"]
    row = connection.execute("SELECT count(*) AS count FROM calibration_jobs").fetchone()
    assert row["count"] == 0
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    ) == ()


def test_api_create_calibration_job_allows_pressure_when_enabled():
    connection = _connection_with_user()
    payload = _job_payload()
    payload["discipline"] = "pressure"

    response = _api_request(
        create_app(
            connection=connection,
            clock=_fixed_now,
            enabled_disciplines=frozenset({Discipline.TEMPERATURE, Discipline.PRESSURE}),
        ),
        "POST",
        "/calibration-jobs",
        headers={"X-Session-Id": "session-001"},
        json=payload,
    )

    assert response.status_code == 200
    assert SQLiteCalibrationJobRepository(connection).get("job-001").discipline is (
        Discipline.PRESSURE
    )


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
        allow_provisional_valprobe_parser=True,
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
    job_events = SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    )
    assert [event.action for event in job_events][-2:] == [
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


def test_api_upload_other_csv_stores_controlled_raw_evidence_without_parser(tmp_path):
    connection = _connection_with_user_and_job()
    app = create_app(
        connection=connection,
        clock=_fixed_now,
        artifact_directory=tmp_path / "artifacts",
        id_factory=lambda: "pressure-raw-001",
    )

    response = _api_request(
        app,
        "POST",
        (
            "/calibration-jobs/job-001/files?"
            "original_filename=pressure-readings.csv&"
            "file_kind=other&"
            "software_version=app-0.1.0"
        ),
        headers={
            "X-Session-Id": "session-001",
            "Content-Type": "text/csv",
        },
        content=b"timestamp,reference,indication\n2026-06-01T14:20:00Z,10.000,10.004\n",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["uploaded_file_id"] == "file-pressure-raw-001"
    assert payload["file_kind"] == "other"
    assert payload["parser_status"] == "not_run"
    assert payload["parser_audit_event_id"] is None
    assert payload["reading_count"] == 0
    assert payload["warning_count"] == 0
    uploaded = SQLiteUploadedFileRepository(connection).get("file-pressure-raw-001")
    assert uploaded.original_filename == "pressure-readings.csv"
    assert uploaded.file_kind is UploadedFileKind.OTHER
    assert (
        tmp_path
        / "artifacts"
        / "uploads"
        / "job-001"
        / "file-pressure-raw-001-pressure-readings.csv"
    ).exists()


def test_api_upload_calibration_xlsx_stores_only_when_provisional_parser_disabled(
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
    assert payload["parser_status"] == "stored_only"
    assert payload["reading_count"] == 0
    assert payload["warning_count"] == 1
    assert "provisional" in payload["warnings"][0]
    assert SQLiteParsedReadingRepository(connection).list_for_uploaded_file(
        "file-001"
    ) == ()


def test_api_upload_rejects_calibration_xlsx_with_wrong_extension(tmp_path):
    connection = _connection_with_user_and_job()
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
            "original_filename=calibration.csv&"
            "file_kind=calibration_xlsx&"
            "software_version=app-0.1.0"
        ),
        headers={
            "X-Session-Id": "session-001",
            "Content-Type": "application/octet-stream",
        },
        content=b"not an xlsx",
    )

    assert response.status_code == 409
    assert ".xlsx" in response.json()["detail"]
    assert SQLiteUploadedFileRepository(connection).list_for_job("job-001") == ()


def test_api_upload_rejects_malformed_calibration_xlsx_before_persistence(tmp_path):
    connection = _connection_with_user_and_job()
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
            "original_filename=calibration.xlsx&"
            "file_kind=calibration_xlsx&"
            "software_version=app-0.1.0"
        ),
        headers={
            "X-Session-Id": "session-001",
            "Content-Type": "application/octet-stream",
        },
        content=b"not an xlsx",
    )

    assert response.status_code == 409
    assert "valid ZIP archive" in response.json()["detail"]
    assert SQLiteUploadedFileRepository(connection).list_for_job("job-001") == ()


def test_api_upload_rejects_declared_oversize_before_read(tmp_path):
    connection = _connection_with_user_and_job()
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
            "original_filename=verification.pdf&"
            "file_kind=verification_pdf&"
            "software_version=app-0.1.0"
        ),
        headers={
            "X-Session-Id": "session-001",
            "Content-Type": "application/octet-stream",
            "Content-Length": str(MAX_UPLOAD_SIZE_BYTES + 1),
        },
        content=b"%PDF-1.4 small fixture",
    )

    assert response.status_code == 413
    assert SQLiteUploadedFileRepository(connection).list_for_job("job-001") == ()


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
        allow_provisional_valprobe_parser=True,
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
        allow_provisional_valprobe_parser=True,
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
    assert payload["dut_ids"] == ["dut-job-001-MJT1-A"]
    assert payload["setpoint_ids"] == ["setpoint-job-001-001"]
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
        allow_provisional_valprobe_parser=True,
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
        allow_provisional_valprobe_parser=True,
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


def test_api_record_manual_irtd_rows_persists_reference_links_and_audit(tmp_path):
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
    generated_ids = iter(("001", "002"))
    app = create_app(
        connection=connection,
        clock=_fixed_now,
        artifact_directory=tmp_path / "artifacts",
        id_factory=lambda: next(generated_ids),
        allow_provisional_valprobe_parser=True,
    )
    calibration_upload = _api_request(
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
    assert calibration_upload.status_code == 200
    verification_upload = _api_request(
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
    assert verification_upload.status_code == 200
    metadata = _api_request(
        app,
        "POST",
        "/certificate-metadata",
        headers={"X-Session-Id": "session-001"},
        json=_metadata_payload(),
    )
    assert metadata.status_code == 200
    assert metadata.json()["workflow_state"] == "metadata_complete"

    reference_selection = _api_request(
        app,
        "POST",
        "/reference-equipment-selections",
        headers={"X-Session-Id": "session-001"},
        json=_reference_equipment_payload(),
    )
    assert reference_selection.status_code == 200
    assert reference_selection.json()["workflow_state"] == "equipment_selected"

    data_entry = _api_request(
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
    assert data_entry.status_code == 200

    response = _api_request(
        app,
        "POST",
        "/calibration-jobs/job-001/verification-irtd-rows",
        headers={"X-Session-Id": "session-001"},
        json={
            "calibration_uploaded_file_id": "file-001",
            "verification_uploaded_file_id": "file-002",
            "rows": [
                ["Time", "IRTD (deg C)", "MJT1-A"],
                ["2026-04-08T15:45:00+00:00", "-80.031", "-80.036"],
                ["2026-04-08T15:46:00+00:00", "-80.030", "-80.034"],
            ],
            "unit": "deg C",
            "software_version": "app-0.1.0",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == "job-001"
    assert payload["calibration_uploaded_file_id"] == "file-001"
    assert payload["verification_uploaded_file_id"] == "file-002"
    assert payload["irtd_reading_count"] == 2
    assert payload["linked_reading_count"] == 2
    assert payload["warnings"] == []
    assert len(SQLiteParsedReadingRepository(connection).list_for_uploaded_file("file-002")) == 2
    linked = SQLiteLinkedTemperatureReadingRepository(connection).list_for_job("job-001")
    assert len(linked) == 2
    assert linked[0].reference.value == -80.031
    assert linked[0].indication.value == -80.036
    verification_events = SQLiteAuditEventRepository(connection).list_for_entity(
        "uploaded_file",
        "file-002",
    )
    assert [event.action for event in verification_events] == [
        AuditAction.FILE_UPLOADED,
        AuditAction.MANUAL_IRTD_TABLE_RECORDED,
    ]
    job_events = SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    )
    assert job_events[-1].action is AuditAction.IMPORT_ALIGNMENT_RECORDED
    assert job_events[-1].new_value["source"] == "manual_irtd_table"


def test_api_record_manual_irtd_rows_rejects_before_data_entered():
    connection = _connection_with_user_and_job()

    response = _api_request(
        create_app(connection=connection, clock=_fixed_now),
        "POST",
        "/calibration-jobs/job-001/verification-irtd-rows",
        headers={"X-Session-Id": "session-001"},
        json={
            "calibration_uploaded_file_id": "file-001",
            "verification_uploaded_file_id": "file-002",
            "rows": [["Time", "IRTD (deg C)"], ["2026-04-08T15:45:00+00:00", "-80.031"]],
            "unit": "deg C",
            "software_version": "app-0.1.0",
        },
    )

    assert response.status_code == 409
    assert "data_entered" in response.json()["detail"]
    assert SQLiteLinkedTemperatureReadingRepository(connection).list_for_job("job-001") == ()


def test_api_select_windows_and_calculate_temperature_from_linked_readings(tmp_path):
    connection = _connection_with_user_and_job(user_roles=(Role.ADMIN,))
    _add_user_session(
        connection,
        user_id="reviewer-001",
        session_id="reviewer-session",
        roles=(Role.TECHNICAL_REVIEWER,),
    )
    _add_user_session(
        connection,
        user_id="qa-001",
        session_id="qa-session",
        roles=(Role.QA_APPROVER,),
    )
    _add_user_session(
        connection,
        user_id="release-001",
        session_id="release-session",
        roles=(Role.QA_APPROVER,),
    )
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
    generated_ids = iter(("001", "002"))
    app = create_app(
        connection=connection,
        clock=_fixed_now,
        artifact_directory=tmp_path / "artifacts",
        id_factory=lambda: next(generated_ids),
        allow_provisional_valprobe_parser=True,
    )
    calibration_upload = _api_request(
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
    assert calibration_upload.status_code == 200
    verification_upload = _api_request(
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
    assert verification_upload.status_code == 200
    metadata = _api_request(
        app,
        "POST",
        "/certificate-metadata",
        headers={"X-Session-Id": "session-001"},
        json=_metadata_payload(),
    )
    assert metadata.status_code == 200
    assert metadata.json()["workflow_state"] == "metadata_complete"

    reference_selection = _api_request(
        app,
        "POST",
        "/reference-equipment-selections",
        headers={"X-Session-Id": "session-001"},
        json=_reference_equipment_payload(),
    )
    assert reference_selection.status_code == 200
    assert reference_selection.json()["workflow_state"] == "equipment_selected"

    data_entry = _api_request(
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
    assert data_entry.status_code == 200
    irtd_rows = _api_request(
        app,
        "POST",
        "/calibration-jobs/job-001/verification-irtd-rows",
        headers={"X-Session-Id": "session-001"},
        json={
            "calibration_uploaded_file_id": "file-001",
            "verification_uploaded_file_id": "file-002",
            "rows": [
                ["Time", "IRTD (deg C)", "MJT1-A"],
                ["2026-04-08T15:45:00+00:00", "-80.031", "-80.036"],
                ["2026-04-08T15:46:00+00:00", "-80.030", "-80.034"],
            ],
            "unit": "deg C",
            "software_version": "app-0.1.0",
        },
    )
    assert irtd_rows.status_code == 200

    selection = _api_request(
        app,
        "POST",
        "/calibration-jobs/job-001/temperature-windows",
        headers={"X-Session-Id": "session-001"},
        json={
            "window_id": "window-001",
            "dut_id": "dut-job-001-MJT1-A",
            "dut_channel_id": "MJT1-A",
            "setpoint": -80.0,
            "unit": "deg C",
            "start_timestamp": "2026-04-08T15:45:00+00:00",
            "end_timestamp": "2026-04-08T15:46:00+00:00",
            "software_version": "app-0.1.0",
        },
    )

    assert selection.status_code == 200
    selection_payload = selection.json()
    assert selection_payload["job_id"] == "job-001"
    assert selection_payload["window_id"] == "window-001"
    assert selection_payload["dut_channel_id"] == "MJT1-A"
    assert selection_payload["reading_count"] == 2
    assert selection_payload["linked_reading_count"] == 2
    assert (
        SQLiteMeasurementWindowRepository(connection)
        .get("window-001")
        .reading_count
        == 2
    )

    completion = _api_request(
        app,
        "POST",
        "/calibration-jobs/job-001/temperature-windows/complete",
        headers={"X-Session-Id": "session-001"},
        json={"software_version": "app-0.1.0"},
    )

    assert completion.status_code == 200
    assert completion.json()["state"] == "windows_selected"
    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.WINDOWS_SELECTED
    )

    constant_set = _api_request(
        app,
        "POST",
        "/constant-sets/approved",
        headers={"X-Session-Id": "session-001"},
        json=_constant_set_payload(),
    )
    budget = _api_request(
        app,
        "POST",
        "/uncertainty-budgets/approved",
        headers={"X-Session-Id": "session-001"},
        json=_budget_payload(),
    )

    assert constant_set.status_code == 200
    assert constant_set.json()["approved_by"] == "user-001"
    assert budget.status_code == 200
    assert budget.json()["approved_by"] == "user-001"

    calculation = _api_request(
        app,
        "POST",
        "/calibration-jobs/job-001/temperature-calculations",
        headers={"X-Session-Id": "session-001"},
        json={
            "uncertainty_inputs": [
                {
                    "setpoint": -80.0,
                    "unit": "deg C",
                    "cmc_floor": "0.010",
                    "reference_expanded_uncertainty": 0.010,
                    "bath_expanded_uncertainty": 0.004,
                    "dut_resolution": 0.010,
                }
            ],
            "software_version": "app-0.1.0",
            "calculation_engine_version": "calc-engine-0.1.0",
            "constant_set_version": "constants-2026-001",
            "budget_version": "budget-temp-001",
        },
    )

    assert calculation.status_code == 200
    calculation_payload = calculation.json()
    assert calculation_payload["state"] == "calculated"
    assert calculation_payload["summary_ids"] == ["job-001-window-001-summary"]
    assert calculation_payload["summaries"][0]["reference"] == -80.0305
    assert calculation_payload["summaries"][0]["indication"] == -80.035
    assert calculation_payload["summaries"][0]["reported_expanded_uncertainty"] == "0.012"
    assert (
        str(
            SQLiteMeasurementPointSummaryRepository(connection)
            .get("job-001-window-001-summary")
            .reported_expanded_uncertainty
        )
        == "0.012"
    )
    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.CALCULATED
    )

    technical_submission = _api_request(
        app,
        "POST",
        "/calibration-jobs/job-001/technical-review-submissions",
        headers={"X-Session-Id": "session-001"},
        json={"software_version": "app-0.1.0"},
    )
    technical_approval = _api_request(
        app,
        "POST",
        "/calibration-jobs/job-001/technical-review-approvals",
        headers={"X-Session-Id": "reviewer-session"},
        json={"software_version": "app-0.1.0"},
    )
    qa_approval = _api_request(
        app,
        "POST",
        "/calibration-jobs/job-001/qa-release-approvals",
        headers={"X-Session-Id": "qa-session"},
        json={"software_version": "app-0.1.0"},
    )

    assert technical_submission.status_code == 200
    assert technical_submission.json()["state"] == "technical_review"
    assert technical_approval.status_code == 200
    assert technical_approval.json()["state"] == "qa_review"
    assert qa_approval.status_code == 200
    assert qa_approval.json()["state"] == "approved"
    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.APPROVED
    )

    preview = _api_request(
        app,
        "POST",
        "/certificate-previews",
        headers={"X-Session-Id": "release-session"},
        json={
            "job_id": "job-001",
            "template_version": "template-2026-001",
            "software_version": "app-0.1.0",
            "accreditation_mark_allowed": True,
        },
    )

    assert preview.status_code == 200
    preview_payload = preview.json()
    assert preview_payload["summary_ids"] == ["job-001-window-001-summary"]
    assert preview_payload["reference_equipment"][0]["equipment_id"] == "ref-001"

    release = _api_request(
        app,
        "POST",
        "/certificate-rendered-releases",
        headers={"X-Session-Id": "release-session"},
        json={
            "job_id": "job-001",
            "certificate_id": "cert-001",
            "certificate_number": "SIMVAL-CAL-0001",
            "artifact_id": "artifact-001",
            "template_version": "template-2026-001",
            "software_version": "app-0.1.0",
            "accreditation_mark_allowed": True,
        },
    )

    assert release.status_code == 200
    release_payload = release.json()
    artifact_path = tmp_path / "artifacts" / "SIMVAL-CAL-0001.pdf"
    assert artifact_path.exists()
    assert release_payload["status"] == "released"
    assert release_payload["artifacts"][0]["filename"] == "SIMVAL-CAL-0001.pdf"
    assert release_payload["artifacts"][0]["checksum_sha256"] == hashlib.sha256(
        artifact_path.read_bytes()
    ).hexdigest()
    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.RELEASED
    )
    assert SQLiteCertificateRecordRepository(connection).get("cert-001").released_by == (
        "release-001"
    )


def test_api_end_to_end_manual_pressure_certificate_uses_persisted_workflow(
    tmp_path,
):
    connection = _connection_with_user(user_roles=(Role.ADMIN,))
    _add_user_session(
        connection,
        user_id="reviewer-001",
        session_id="reviewer-session",
        roles=(Role.TECHNICAL_REVIEWER,),
    )
    _add_user_session(
        connection,
        user_id="qa-001",
        session_id="qa-session",
        roles=(Role.QA_APPROVER,),
    )
    _add_user_session(
        connection,
        user_id="release-001",
        session_id="release-session",
        roles=(Role.QA_APPROVER,),
    )
    app = create_app(
        connection=connection,
        clock=_fixed_now,
        artifact_directory=tmp_path / "artifacts",
        id_factory=lambda: "pressure-raw-001",
        enabled_disciplines=frozenset({Discipline.TEMPERATURE, Discipline.PRESSURE}),
    )

    create_job = _api_request(
        app,
        "POST",
        "/calibration-jobs",
        headers={"X-Session-Id": "session-001"},
        json={
            "job_id": "pressure-job-001",
            "client_name": "SIMVal pressure customer",
            "client_address": "Pressure Road 1",
            "discipline": "pressure",
            "measurement_mode": "manual",
            "method": "SIMVal manual pressure method",
            "software_version": "app-0.1.0",
        },
    )
    assert create_job.status_code == 200

    metadata = _api_request(
        app,
        "POST",
        "/certificate-metadata",
        headers={"X-Session-Id": "session-001"},
        json={
            "job_id": "pressure-job-001",
            "certificate_date": "2026-06-03",
            "calibration_date": "2026-06-01",
            "receipt_date": "2026-05-31",
            "task_number": "TASK-P-2026-001",
            "purchase_order": "PO-P-12345",
            "client_name": "SIMVal pressure customer",
            "client_address": "Pressure Road 1",
            "procedure": "SIMVal SOP-PRESS-001",
            "place": "SIMVal Pressure Laboratory, Lyngby",
            "approved_by_label": "QA User",
            "remarks": "Manual pressure readings transcribed from controlled source.",
            "traceability_statement": "Pressure measurements are metrologically traceable.",
            "uncertainty_statement": "Expanded uncertainty uses k=2.",
            "ambient_conditions": "Room temperature 23 +/- 2 deg C.",
            "temperature_scale": "bar",
            "software_version": "app-0.1.0",
        },
    )
    assert metadata.status_code == 200

    reference_equipment = _api_request(
        app,
        "POST",
        "/reference-equipment-selections",
        headers={"X-Session-Id": "session-001"},
        json={
            "job_id": "pressure-job-001",
            "equipment_id": "ref-pressure-001",
            "simval_id": "SIM-P-001",
            "equipment_type": "Pressure reference",
            "serial_number": "PRESS-REF-001",
            "discipline": "pressure",
            "calibration_certificate_reference": "DANAK-P-12345",
            "calibration_due_date": "2027-04-30",
            "status": "active",
            "range_minimum": 0.0,
            "range_maximum": 20.0,
            "range_unit": "bar",
            "traceability_statement": "Accredited pressure calibration with SI traceability.",
            "software_version": "app-0.1.0",
        },
    )
    assert reference_equipment.status_code == 200

    upload = _api_request(
        app,
        "POST",
        (
            "/calibration-jobs/pressure-job-001/files?"
            "original_filename=pressure-readings.csv&"
            "file_kind=other&"
            "software_version=app-0.1.0"
        ),
        headers={
            "X-Session-Id": "session-001",
            "Content-Type": "text/csv",
        },
        content=(
            b"timestamp,reference,indication\n"
            b"2026-06-01T14:20:00Z,10.000,10.004\n"
            b"2026-06-01T14:21:00Z,10.000,10.006\n"
        ),
    )
    assert upload.status_code == 200
    assert upload.json()["uploaded_file_id"] == "file-pressure-raw-001"

    manual_entry = _api_request(
        app,
        "POST",
        "/calibration-jobs/pressure-job-001/pressure-manual-entry",
        headers={"X-Session-Id": "session-001"},
        json={
            "uploaded_file_id": "file-pressure-raw-001",
            "dut_id": "pressure-dut-001",
            "dut_make": "PressureCo",
            "dut_model": "Gauge",
            "dut_serial_number": "PG-001",
            "dut_channel_id": "PG-001",
            "window_id": "pressure-window-001",
            "setpoint": 10.0,
            "unit": "bar",
            "readings": [
                {
                    "timestamp": "2026-06-01T14:20:00+00:00",
                    "value": 10.004,
                    "source_label": "Pressure",
                    "row_number": 2,
                    "column_label": "indication",
                },
                {
                    "timestamp": "2026-06-01T14:21:00+00:00",
                    "value": 10.006,
                    "source_label": "Pressure",
                    "row_number": 3,
                    "column_label": "indication",
                },
            ],
            "software_version": "app-0.1.0",
        },
    )
    assert manual_entry.status_code == 200
    assert manual_entry.json()["state"] == "windows_selected"

    constant_set = _api_request(
        app,
        "POST",
        "/constant-sets/approved",
        headers={"X-Session-Id": "session-001"},
        json={
            "version": "constants-pressure-001",
            "discipline": "pressure",
            "effective_from": "2026-01-01T00:00:00+00:00",
            "software_version": "app-0.1.0",
        },
    )
    budget = _api_request(
        app,
        "POST",
        "/uncertainty-budgets/approved",
        headers={"X-Session-Id": "session-001"},
        json={
            "version": "budget-pressure-001",
            "budget_type": "pressure",
            "method": "SIMVal manual pressure method",
            "discipline": "pressure",
            "linked_constant_set_version": "constants-pressure-001",
            "software_version": "app-0.1.0",
        },
    )
    assert constant_set.status_code == 200
    assert budget.status_code == 200

    calculation = _api_request(
        app,
        "POST",
        "/calibration-jobs/pressure-job-001/pressure-calculations",
        headers={"X-Session-Id": "session-001"},
        json={
            "manual_points": [
                {
                    "point_id": "pressure-point-001",
                    "dut_id": "pressure-dut-001",
                    "measurement_window_id": "pressure-window-001",
                    "reference_pressure": 10.0,
                    "indication_values": [10.004, 10.006],
                    "setpoint": 10.0,
                    "unit": "bar",
                    "pressure_kind": "gauge",
                    "cmc_floor": "0.001",
                    "reference_expanded_uncertainty": 0.004,
                    "dut_resolution": 0.002,
                }
            ],
            "automatic_points": [],
            "software_version": "app-0.1.0",
            "calculation_engine_version": "calc-engine-0.1.0",
            "constant_set_version": "constants-pressure-001",
            "budget_version": "budget-pressure-001",
        },
    )
    assert calculation.status_code == 200
    assert calculation.json()["summary_ids"] == ["pressure-point-001"]
    assert calculation.json()["summaries"][0]["reported_expanded_uncertainty"] == "0.0042"

    assert _api_request(
        app,
        "POST",
        "/calibration-jobs/pressure-job-001/technical-review-submissions",
        headers={"X-Session-Id": "session-001"},
        json={"software_version": "app-0.1.0"},
    ).status_code == 200
    assert _api_request(
        app,
        "POST",
        "/calibration-jobs/pressure-job-001/technical-review-approvals",
        headers={"X-Session-Id": "reviewer-session"},
        json={"software_version": "app-0.1.0"},
    ).status_code == 200
    assert _api_request(
        app,
        "POST",
        "/calibration-jobs/pressure-job-001/qa-release-approvals",
        headers={"X-Session-Id": "qa-session"},
        json={"software_version": "app-0.1.0"},
    ).status_code == 200

    preview = _api_request(
        app,
        "POST",
        "/certificate-previews",
        headers={"X-Session-Id": "release-session"},
        json={
            "job_id": "pressure-job-001",
            "template_version": "template-pressure-2026-001",
            "software_version": "app-0.1.0",
            "accreditation_mark_allowed": True,
        },
    )
    assert preview.status_code == 200
    assert preview.json()["summary_ids"] == ["pressure-point-001"]
    assert preview.json()["reference_equipment"][0]["equipment_id"] == "ref-pressure-001"

    release = _api_request(
        app,
        "POST",
        "/certificate-rendered-releases",
        headers={"X-Session-Id": "release-session"},
        json={
            "job_id": "pressure-job-001",
            "certificate_id": "pressure-cert-001",
            "certificate_number": "SIMVAL-P-0001",
            "artifact_id": "pressure-artifact-001",
            "template_version": "template-pressure-2026-001",
            "software_version": "app-0.1.0",
            "accreditation_mark_allowed": True,
        },
    )
    assert release.status_code == 200
    assert release.json()["status"] == "released"
    assert (tmp_path / "artifacts" / "SIMVAL-P-0001.pdf").exists()
    assert SQLiteCalibrationJobRepository(connection).get("pressure-job-001").state is (
        WorkflowState.RELEASED
    )


def test_api_end_to_end_temperature_certificate_supports_multiple_duts(tmp_path):
    connection = _connection_with_user_and_job(user_roles=(Role.ADMIN,))
    _add_user_session(
        connection,
        user_id="reviewer-001",
        session_id="reviewer-session",
        roles=(Role.TECHNICAL_REVIEWER,),
    )
    _add_user_session(
        connection,
        user_id="qa-001",
        session_id="qa-session",
        roles=(Role.QA_APPROVER,),
    )
    _add_user_session(
        connection,
        user_id="release-001",
        session_id="release-session",
        roles=(Role.QA_APPROVER,),
    )
    workbook = tmp_path / "sanitized-valprobe.xlsx"
    _write_workbook(
        workbook,
        sheets={
            "Temperature": _temperature_sheet_xml(
                channels=("MJT1-A", "MJT2-A"),
                data_rows=[
                    ("2026-04-08T15:45:00+00:00", "-80.036", "-80.041"),
                    ("2026-04-08T15:46:00+00:00", "-80.034", "-80.039"),
                ],
            )
        },
    )
    generated_ids = iter(("001", "002"))
    app = create_app(
        connection=connection,
        clock=_fixed_now,
        artifact_directory=tmp_path / "artifacts",
        id_factory=lambda: next(generated_ids),
        allow_provisional_valprobe_parser=True,
    )

    calibration_upload = _api_request(
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
    verification_upload = _api_request(
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
    assert calibration_upload.status_code == 200
    assert verification_upload.status_code == 200

    metadata = _api_request(
        app,
        "POST",
        "/certificate-metadata",
        headers={"X-Session-Id": "session-001"},
        json=_metadata_payload(),
    )
    reference_selection = _api_request(
        app,
        "POST",
        "/reference-equipment-selections",
        headers={"X-Session-Id": "session-001"},
        json=_reference_equipment_payload(),
    )
    data_entry = _api_request(
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
    irtd_rows = _api_request(
        app,
        "POST",
        "/calibration-jobs/job-001/verification-irtd-rows",
        headers={"X-Session-Id": "session-001"},
        json={
            "calibration_uploaded_file_id": "file-001",
            "verification_uploaded_file_id": "file-002",
            "rows": [
                ["Time", "IRTD (deg C)", "MJT1-A", "MJT2-A"],
                ["2026-04-08T15:45:00+00:00", "-80.031", "-80.036", "-80.041"],
                ["2026-04-08T15:46:00+00:00", "-80.030", "-80.034", "-80.039"],
            ],
            "unit": "deg C",
            "software_version": "app-0.1.0",
        },
    )
    assert metadata.status_code == 200
    assert reference_selection.status_code == 200
    assert data_entry.status_code == 200
    assert data_entry.json()["dut_ids"] == [
        "dut-job-001-MJT1-A",
        "dut-job-001-MJT2-A",
    ]
    assert irtd_rows.status_code == 200
    assert irtd_rows.json()["linked_reading_count"] == 4

    for window_id, dut_channel_id in (
        ("window-001", "MJT1-A"),
        ("window-002", "MJT2-A"),
    ):
        selection = _api_request(
            app,
            "POST",
            "/calibration-jobs/job-001/temperature-windows",
            headers={"X-Session-Id": "session-001"},
            json={
                "window_id": window_id,
                "dut_id": f"dut-job-001-{dut_channel_id}",
                "dut_channel_id": dut_channel_id,
                "setpoint": -80.0,
                "unit": "deg C",
                "start_timestamp": "2026-04-08T15:45:00+00:00",
                "end_timestamp": "2026-04-08T15:46:00+00:00",
                "software_version": "app-0.1.0",
            },
        )
        assert selection.status_code == 200
        assert selection.json()["linked_reading_count"] == 2

    completion = _api_request(
        app,
        "POST",
        "/calibration-jobs/job-001/temperature-windows/complete",
        headers={"X-Session-Id": "session-001"},
        json={"software_version": "app-0.1.0"},
    )
    constant_set = _api_request(
        app,
        "POST",
        "/constant-sets/approved",
        headers={"X-Session-Id": "session-001"},
        json=_constant_set_payload(),
    )
    budget = _api_request(
        app,
        "POST",
        "/uncertainty-budgets/approved",
        headers={"X-Session-Id": "session-001"},
        json=_budget_payload(),
    )
    assert completion.status_code == 200
    assert constant_set.status_code == 200
    assert budget.status_code == 200

    calculation = _api_request(
        app,
        "POST",
        "/calibration-jobs/job-001/temperature-calculations",
        headers={"X-Session-Id": "session-001"},
        json={
            "uncertainty_inputs": [
                {
                    "setpoint": -80.0,
                    "unit": "deg C",
                    "cmc_floor": "0.010",
                    "reference_expanded_uncertainty": 0.010,
                    "bath_expanded_uncertainty": 0.004,
                    "dut_resolution": 0.010,
                }
            ],
            "software_version": "app-0.1.0",
            "calculation_engine_version": "calc-engine-0.1.0",
            "constant_set_version": "constants-2026-001",
            "budget_version": "budget-temp-001",
        },
    )
    assert calculation.status_code == 200
    assert calculation.json()["summary_ids"] == [
        "job-001-window-001-summary",
        "job-001-window-002-summary",
    ]

    for path_suffix, session_id in (
        ("technical-review-submissions", "session-001"),
        ("technical-review-approvals", "reviewer-session"),
        ("qa-release-approvals", "qa-session"),
    ):
        response = _api_request(
            app,
            "POST",
            f"/calibration-jobs/job-001/{path_suffix}",
            headers={"X-Session-Id": session_id},
            json={"software_version": "app-0.1.0"},
        )
        assert response.status_code == 200

    preview = _api_request(
        app,
        "POST",
        "/certificate-previews",
        headers={"X-Session-Id": "release-session"},
        json={
            "job_id": "job-001",
            "template_version": "template-2026-001",
            "software_version": "app-0.1.0",
            "accreditation_mark_allowed": True,
        },
    )
    release = _api_request(
        app,
        "POST",
        "/certificate-rendered-releases",
        headers={"X-Session-Id": "release-session"},
        json={
            "job_id": "job-001",
            "certificate_id": "cert-multi-001",
            "certificate_number": "SIMVAL-CAL-MULTI-0001",
            "artifact_id": "artifact-multi-001",
            "template_version": "template-2026-001",
            "software_version": "app-0.1.0",
            "accreditation_mark_allowed": True,
        },
    )

    assert preview.status_code == 200
    preview_payload = preview.json()
    assert preview_payload["summary_ids"] == [
        "job-001-window-001-summary",
        "job-001-window-002-summary",
    ]
    assert [row["dut_id"] for row in preview_payload["rows"]] == [
        "dut-job-001-MJT1-A",
        "dut-job-001-MJT2-A",
    ]
    assert release.status_code == 200
    assert release.json()["status"] == "released"
    assert (
        tmp_path / "artifacts" / "SIMVAL-CAL-MULTI-0001.pdf"
    ).exists()


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


def _add_user_session(
    connection: sqlite3.Connection,
    *,
    user_id: str,
    session_id: str,
    roles: tuple[Role, ...],
) -> None:
    SQLiteUserAccountRepository(connection).add(
        UserAccount(
            id=user_id,
            display_name=f"{user_id} User",
            email=f"{user_id}@example.com",
            roles=roles,
            active=True,
            created_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
        )
    )
    SQLiteUserSessionRepository(connection).add(
        UserSession(
            id=session_id,
            user_id=user_id,
            issued_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
            expires_at=datetime(2026, 6, 1, 16, 0, tzinfo=timezone.utc),
        )
    )


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


def _metadata_payload() -> dict:
    return {
        "job_id": "job-001",
        "certificate_date": "2026-06-03",
        "calibration_date": "2026-06-01",
        "receipt_date": "2026-05-31",
        "task_number": "TASK-2026-001",
        "purchase_order": "PO-12345",
        "client_name": "SIMVal customer",
        "client_address": "Validated Road 1, 2800 Lyngby",
        "procedure": "SIMVal SOP-TEMP-001",
        "place": "SIMVal Temperature Laboratory, Lyngby",
        "approved_by_label": "QA User",
        "remarks": "ValProbe RT logger data reviewed.",
        "traceability_statement": "Measurements are metrologically traceable.",
        "uncertainty_statement": "Expanded uncertainty uses k=2.",
        "ambient_conditions": "Room temperature 23 +/- 2 deg C.",
        "temperature_scale": "ITS-90",
        "software_version": "app-0.1.0",
    }


def _reference_equipment_payload() -> dict:
    return {
        "job_id": "job-001",
        "equipment_id": "ref-001",
        "simval_id": "SIM-T-001",
        "equipment_type": "IRTD",
        "serial_number": "IRT-123",
        "discipline": "temperature",
        "calibration_certificate_reference": "DANAK-CAL-12345",
        "calibration_due_date": "2027-04-30",
        "status": "active",
        "range_minimum": -90.0,
        "range_maximum": 140.0,
        "range_unit": "deg C",
        "traceability_statement": "Accredited calibration with SI traceability.",
        "software_version": "app-0.1.0",
    }


def _constant_set_payload() -> dict:
    return {
        "version": "constants-2026-001",
        "discipline": "temperature",
        "effective_from": "2026-01-01T00:00:00+00:00",
        "software_version": "app-0.1.0",
    }


def _budget_payload() -> dict:
    return {
        "version": "budget-temp-001",
        "budget_type": "temperature_logger",
        "method": "ValProbe RT automatic temperature",
        "discipline": "temperature",
        "linked_constant_set_version": "constants-2026-001",
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
