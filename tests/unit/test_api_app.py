import sqlite3
import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib

import httpx

from app.backend.api.app import create_app
from app.backend.auth.permissions import Role
from app.backend.auth.users import UserAccount, UserSession
from app.backend.certificates.metadata import CertificateMetadata
from app.backend.domain.entities import (
    CalibrationJob,
    Client,
    DeviceUnderTest,
    Discipline,
    MeasurementMode,
    MeasurementReading,
    MeasurementWindow,
    SourceLocation,
    UploadedFile,
    UploadedFileKind,
)
from app.backend.domain.workflow import WorkflowState
from app.backend.persistence.sqlite import (
    SQLiteAuditEventRepository,
    SQLiteCalibrationJobRepository,
    SQLiteCertificateMetadataRepository,
    SQLiteCertificateRecordRepository,
    SQLiteDeviceUnderTestRepository,
    SQLiteMeasurementPointSummaryRepository,
    SQLiteMeasurementWindowRepository,
    SQLiteUploadedFileRepository,
    SQLiteUserAccountRepository,
    SQLiteUserSessionRepository,
    initialize_schema,
)
from app.calculation_engine.common.summary import MeasurementPointSummary


def test_api_health_returns_ok():
    response = _api_request(
        create_app(
            connection=_connection_with_preview_data(),
            clock=_fixed_now,
        ),
        "GET",
        "/health",
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_me_returns_authenticated_actor():
    response = _api_request(
        create_app(
            connection=_connection_with_preview_data(),
            clock=_fixed_now,
        ),
        "GET",
        "/me",
        headers={"X-Session-Id": "session-001"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "user-001",
        "display_name": "Operator User",
        "roles": ["operator"],
    }


def test_api_certificate_metadata_capture_records_metadata_and_audits():
    connection = _connection_with_metadata_capture_data()

    response = _api_request(
        create_app(connection=connection, clock=_fixed_now),
        "POST",
        "/certificate-metadata",
        headers={"X-Session-Id": "session-001"},
        json=_metadata_payload(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == "job-001"
    assert payload["client_name"] == "SIMVal customer"
    assert payload["purchase_order"] == "PO-12345"
    assert payload["recorded_by"] == "user-001"
    assert payload["metadata_audit_event_id"] == 1
    assert payload["workflow_audit_event_id"] == 2
    assert payload["workflow_state"] == "metadata_complete"
    assert SQLiteCertificateMetadataRepository(connection).get(
        "job-001"
    ).recorded_by == "user-001"
    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.METADATA_COMPLETE
    )


def test_api_certificate_metadata_capture_rejects_unauthorized_session():
    connection = _connection_with_metadata_capture_data(user_roles=(Role.READ_ONLY,))

    response = _api_request(
        create_app(connection=connection, clock=_fixed_now),
        "POST",
        "/certificate-metadata",
        headers={"X-Session-Id": "session-001"},
        json=_metadata_payload(),
    )

    assert response.status_code == 403
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    ) == ()
    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.DRAFT
    )


def test_api_certificate_metadata_capture_rejects_wrong_workflow_state():
    connection = _connection_with_metadata_capture_data(
        job_state=WorkflowState.CALCULATED,
    )

    response = _api_request(
        create_app(connection=connection, clock=_fixed_now),
        "POST",
        "/certificate-metadata",
        headers={"X-Session-Id": "session-001"},
        json=_metadata_payload(),
    )

    assert response.status_code == 409
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    ) == ()


def test_api_certificate_preview_returns_locked_rows_and_audit_id():
    connection = _connection_with_preview_data()

    response = _api_request(
        create_app(connection=connection, clock=_fixed_now),
        "POST",
        "/certificate-previews",
        headers={"X-Session-Id": "session-001"},
        json={
            "job_id": "job-001",
            "template_version": "template-2026-001",
            "software_version": "app-0.1.0",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == "job-001"
    assert payload["generated_by"] == "user-001"
    assert payload["summary_ids"] == ["point-001"]
    assert payload["rows"][0]["display_error_of_indication"] == "-0.004"
    assert payload["rows"][0]["reported_expanded_uncertainty"] == "0.012"
    assert payload["audit_event_id"] == 1
    assert len(
        SQLiteAuditEventRepository(connection).list_for_entity(
            "calibration_job",
            "job-001",
        )
    ) == 1


def test_api_certificate_release_returns_release_evidence_after_preview():
    connection = _connection_with_preview_data(
        job_state=WorkflowState.APPROVED,
        user_roles=(Role.QA_APPROVER,),
    )
    preview_response = _api_request(
        create_app(connection=connection, clock=_fixed_now),
        "POST",
        "/certificate-previews",
        headers={"X-Session-Id": "session-001"},
        json={
            "job_id": "job-001",
            "template_version": "template-2026-001",
            "software_version": "app-0.1.0",
        },
    )
    assert preview_response.status_code == 200

    response = _api_request(
        create_app(connection=connection, clock=_fixed_now),
        "POST",
        "/certificate-releases",
        headers={"X-Session-Id": "session-001"},
        json={
            "job_id": "job-001",
            "certificate_id": "cert-001",
            "certificate_number": "SIMVAL-CAL-0001",
            "artifact_id": "artifact-001",
            "artifact_type": "pdf",
            "filename": "SIMVAL-CAL-0001.pdf",
            "checksum_sha256": "b" * 64,
            "storage_uri": "controlled-local://SIMVAL-CAL-0001.pdf",
            "template_version": "template-2026-001",
            "software_version": "app-0.1.0",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["certificate_id"] == "cert-001"
    assert payload["status"] == "released"
    assert payload["calculation_summary_ids"] == ["point-001"]
    assert payload["artifacts"][0]["checksum_sha256"] == "b" * 64
    assert payload["export_audit_event_id"] == 2
    assert payload["release_audit_event_id"] == 3
    assert payload["workflow_audit_event_id"] == 4
    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.RELEASED
    )
    assert SQLiteCertificateRecordRepository(connection).get("cert-001").status.value == (
        "released"
    )


def test_api_certificate_release_rejects_missing_preview():
    connection = _connection_with_preview_data(
        job_state=WorkflowState.APPROVED,
        user_roles=(Role.QA_APPROVER,),
    )

    response = _api_request(
        create_app(connection=connection, clock=_fixed_now),
        "POST",
        "/certificate-releases",
        headers={"X-Session-Id": "session-001"},
        json={
            "job_id": "job-001",
            "certificate_id": "cert-001",
            "certificate_number": "SIMVAL-CAL-0001",
            "artifact_id": "artifact-001",
            "artifact_type": "pdf",
            "filename": "SIMVAL-CAL-0001.pdf",
            "checksum_sha256": "b" * 64,
            "storage_uri": "controlled-local://SIMVAL-CAL-0001.pdf",
            "template_version": "template-2026-001",
            "software_version": "app-0.1.0",
        },
    )

    assert response.status_code == 409
    assert SQLiteCertificateRecordRepository(connection).list_for_job("job-001") == ()


def test_api_certificate_rendered_release_generates_pdf_and_release_evidence(tmp_path):
    connection = _connection_with_preview_data(
        job_state=WorkflowState.APPROVED,
        user_roles=(Role.QA_APPROVER,),
    )
    app = create_app(
        connection=connection,
        clock=_fixed_now,
        artifact_directory=tmp_path,
    )
    preview_response = _api_request(
        app,
        "POST",
        "/certificate-previews",
        headers={"X-Session-Id": "session-001"},
        json={
            "job_id": "job-001",
            "template_version": "template-2026-001",
            "software_version": "app-0.1.0",
        },
    )
    assert preview_response.status_code == 200

    response = _api_request(
        app,
        "POST",
        "/certificate-rendered-releases",
        headers={"X-Session-Id": "session-001"},
        json={
            "job_id": "job-001",
            "certificate_id": "cert-001",
            "certificate_number": "SIMVAL-CAL-0001",
            "artifact_id": "artifact-001",
            "template_version": "template-2026-001",
            "software_version": "app-0.1.0",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    artifact_path = tmp_path / "SIMVAL-CAL-0001.pdf"
    assert artifact_path.exists()
    assert payload["certificate_id"] == "cert-001"
    assert payload["status"] == "released"
    assert payload["artifacts"][0]["filename"] == "SIMVAL-CAL-0001.pdf"
    assert payload["artifacts"][0]["checksum_sha256"] == hashlib.sha256(
        artifact_path.read_bytes()
    ).hexdigest()
    assert payload["artifacts"][0]["storage_uri"] == (
        "controlled-local://SIMVAL-CAL-0001.pdf"
    )
    assert payload["export_audit_event_id"] == 2
    assert payload["release_audit_event_id"] == 3
    assert payload["workflow_audit_event_id"] == 4
    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.RELEASED
    )


def test_api_certificate_rendered_release_rejects_missing_storage_configuration():
    connection = _connection_with_preview_data(
        job_state=WorkflowState.APPROVED,
        user_roles=(Role.QA_APPROVER,),
    )
    app = create_app(connection=connection, clock=_fixed_now)
    preview_response = _api_request(
        app,
        "POST",
        "/certificate-previews",
        headers={"X-Session-Id": "session-001"},
        json={
            "job_id": "job-001",
            "template_version": "template-2026-001",
            "software_version": "app-0.1.0",
        },
    )
    assert preview_response.status_code == 200

    response = _api_request(
        app,
        "POST",
        "/certificate-rendered-releases",
        headers={"X-Session-Id": "session-001"},
        json={
            "job_id": "job-001",
            "certificate_id": "cert-001",
            "certificate_number": "SIMVAL-CAL-0001",
            "artifact_id": "artifact-001",
            "template_version": "template-2026-001",
            "software_version": "app-0.1.0",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Artifact storage path is not configured."
    assert SQLiteCertificateRecordRepository(connection).list_for_job("job-001") == ()


def test_api_certificate_rendered_release_rejects_unauthorized_session_before_file_write(
    tmp_path,
):
    connection = _connection_with_preview_data(
        job_state=WorkflowState.APPROVED,
        user_roles=(Role.OPERATOR,),
    )
    app = create_app(
        connection=connection,
        clock=_fixed_now,
        artifact_directory=tmp_path,
    )
    preview_response = _api_request(
        app,
        "POST",
        "/certificate-previews",
        headers={"X-Session-Id": "session-001"},
        json={
            "job_id": "job-001",
            "template_version": "template-2026-001",
            "software_version": "app-0.1.0",
        },
    )
    assert preview_response.status_code == 200

    response = _api_request(
        app,
        "POST",
        "/certificate-rendered-releases",
        headers={"X-Session-Id": "session-001"},
        json={
            "job_id": "job-001",
            "certificate_id": "cert-001",
            "certificate_number": "SIMVAL-CAL-0001",
            "artifact_id": "artifact-001",
            "template_version": "template-2026-001",
            "software_version": "app-0.1.0",
        },
    )

    assert response.status_code == 403
    assert not (tmp_path / "SIMVAL-CAL-0001.pdf").exists()
    assert SQLiteCertificateRecordRepository(connection).list_for_job("job-001") == ()


def test_api_certificate_preview_rejects_unauthorized_session_before_audit():
    connection = _connection_with_preview_data(user_roles=(Role.READ_ONLY,))

    response = _api_request(
        create_app(connection=connection, clock=_fixed_now),
        "POST",
        "/certificate-previews",
        headers={"X-Session-Id": "session-001"},
        json={
            "job_id": "job-001",
            "template_version": "template-2026-001",
            "software_version": "app-0.1.0",
        },
    )

    assert response.status_code == 403
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    ) == ()


def test_api_certificate_preview_rejects_unknown_session_before_audit():
    connection = _connection_with_preview_data()

    response = _api_request(
        create_app(connection=connection, clock=_fixed_now),
        "POST",
        "/certificate-previews",
        headers={"X-Session-Id": "missing-session"},
        json={
            "job_id": "job-001",
            "template_version": "template-2026-001",
            "software_version": "app-0.1.0",
        },
    )

    assert response.status_code == 401
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    ) == ()


def test_api_certificate_preview_returns_conflict_for_wrong_workflow_state():
    connection = _connection_with_preview_data(job_state=WorkflowState.WINDOWS_SELECTED)

    response = _api_request(
        create_app(connection=connection, clock=_fixed_now),
        "POST",
        "/certificate-previews",
        headers={"X-Session-Id": "session-001"},
        json={
            "job_id": "job-001",
            "template_version": "template-2026-001",
            "software_version": "app-0.1.0",
        },
    )

    assert response.status_code == 409


def _api_request(app, method: str, url: str, **kwargs) -> httpx.Response:
    return asyncio.run(_async_api_request(app, method, url, **kwargs))


async def _async_api_request(app, method: str, url: str, **kwargs) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.request(method, url, **kwargs)


def _connection_with_preview_data(
    *,
    job_state: WorkflowState = WorkflowState.CALCULATED,
    user_roles: tuple[Role, ...] = (Role.OPERATOR,),
) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    initialize_schema(connection)
    SQLiteCalibrationJobRepository(connection).add(_job(job_state))
    SQLiteCertificateMetadataRepository(connection).add(_metadata())
    SQLiteUploadedFileRepository(connection).add(_uploaded_file())
    SQLiteDeviceUnderTestRepository(connection).add(_dut())
    SQLiteMeasurementWindowRepository(connection).add(_window())
    SQLiteMeasurementPointSummaryRepository(connection).add(_summary())
    SQLiteUserAccountRepository(connection).add(_user(user_roles))
    SQLiteUserSessionRepository(connection).add(_session())
    return connection


def _connection_with_metadata_capture_data(
    *,
    job_state: WorkflowState = WorkflowState.DRAFT,
    user_roles: tuple[Role, ...] = (Role.OPERATOR,),
) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    initialize_schema(connection)
    SQLiteCalibrationJobRepository(connection).add(_job(job_state))
    SQLiteUserAccountRepository(connection).add(_user(user_roles))
    SQLiteUserSessionRepository(connection).add(_session())
    return connection


def _fixed_now() -> datetime:
    return datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc)


def _job(state: WorkflowState) -> CalibrationJob:
    return CalibrationJob(
        id="job-001",
        client=Client(name="SIMVal customer", address="Validated Road 1"),
        discipline=Discipline.TEMPERATURE,
        measurement_mode=MeasurementMode.AUTOMATIC,
        method="ValProbe RT linked XLSX/PDF workflow",
        created_by="operator-001",
        state=state,
        created_at=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
    )


def _metadata() -> CertificateMetadata:
    return CertificateMetadata(
        job_id="job-001",
        certificate_date=date(2026, 6, 3),
        calibration_date=date(2026, 6, 1),
        receipt_date=date(2026, 5, 31),
        task_number="TASK-2026-001",
        purchase_order="PO-12345",
        client_name="SIMVal customer",
        client_address="Validated Road 1, 2800 Lyngby",
        procedure="SIMVal SOP-TEMP-001",
        place="SIMVal Temperature Laboratory, Lyngby",
        approved_by_label="QA User",
        remarks="Aflæsning af logger data via ValProbe RT.",
        traceability_statement="Measurements are metrologically traceable.",
        uncertainty_statement="Expanded uncertainty uses k=2.",
        ambient_conditions="Room temperature 23 +/- 2 deg C.",
        temperature_scale="ITS-90",
        recorded_by="operator-001",
        recorded_at=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
    )


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
        "remarks": "Aflæsning af logger data via ValProbe RT.",
        "traceability_statement": "Measurements are metrologically traceable.",
        "uncertainty_statement": "Expanded uncertainty uses k=2.",
        "ambient_conditions": "Room temperature 23 +/- 2 deg C.",
        "temperature_scale": "ITS-90",
        "software_version": "app-0.1.0",
    }


def _uploaded_file() -> UploadedFile:
    return UploadedFile(
        id="file-001",
        job_id="job-001",
        original_filename="sanitized-valprobe.xlsx",
        checksum_sha256="a" * 64,
        file_kind=UploadedFileKind.CALIBRATION_XLSX,
        storage_uri="controlled-local://sanitized-valprobe.xlsx",
        parser_version="valprobe-xlsx-parser-v1",
        uploaded_at=datetime(2026, 6, 1, 14, 5, tzinfo=timezone.utc),
    )


def _dut() -> DeviceUnderTest:
    return DeviceUnderTest(
        id="dut-001",
        job_id="job-001",
        make="Kaye",
        model="ValProbe RT",
        serial_number="MJT1",
        channel_id="MJT1-A",
    )


def _window() -> MeasurementWindow:
    return MeasurementWindow(
        id="window-001",
        job_id="job-001",
        dut_id="dut-001",
        setpoint=-80.0,
        unit="deg C",
        selected_by="operator-001",
        selected_at=datetime(2026, 6, 1, 14, 20, tzinfo=timezone.utc),
        readings=(
            MeasurementReading(
                timestamp=datetime(2026, 4, 8, 15, 45, tzinfo=timezone.utc),
                channel_id="MJT1-A",
                value=-80.036,
                unit="deg C",
                source=SourceLocation(
                    uploaded_file_id="file-001",
                    source_label="Temperature",
                    row_number=12,
                    column_label="B",
                ),
            ),
        ),
    )


def _summary() -> MeasurementPointSummary:
    return MeasurementPointSummary(
        point_id="point-001",
        job_id="job-001",
        dut_id="dut-001",
        measurement_window_id="window-001",
        reference=-80.0305,
        indication=-80.035,
        unit="deg C",
        error_of_indication=-0.0045,
        calculated_expanded_uncertainty=Decimal("0.0124231"),
        cmc_floor=Decimal("0.010"),
        reported_expanded_uncertainty=Decimal("0.012"),
        display_error_of_indication=Decimal("-0.004"),
        calculation_engine_version="calc-engine-0.1.0",
        constant_set_version="constants-2026-001",
        budget_version="budget-temp-001",
    )


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
