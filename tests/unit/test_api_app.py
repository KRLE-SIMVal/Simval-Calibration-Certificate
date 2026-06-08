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
from app.backend.domain.equipment import (
    EquipmentRange,
    EquipmentStatus,
    ReferenceEquipment,
    SelectedReferenceEquipment,
)
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
    SQLiteCertificateRevisionRepository,
    SQLiteDeviceUnderTestRepository,
    SQLiteMeasurementPointSummaryRepository,
    SQLiteMeasurementWindowRepository,
    SQLiteSelectedReferenceEquipmentRepository,
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


def test_api_readiness_returns_ready_for_database_and_artifact_storage(tmp_path):
    response = _api_request(
        create_app(
            connection=_connection_with_preview_data(),
            clock=_fixed_now,
            artifact_directory=tmp_path,
        ),
        "GET",
        "/readiness",
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "components": [
            {
                "name": "database",
                "status": "ok",
                "detail": "SQLite connection check passed.",
            },
            {
                "name": "artifact_storage",
                "status": "ok",
                "detail": "Artifact storage write/delete probe passed.",
            },
        ],
    }
    assert list(tmp_path.iterdir()) == []


def test_api_readiness_returns_503_when_artifact_storage_is_not_configured():
    response = _api_request(
        create_app(
            connection=_connection_with_preview_data(),
            clock=_fixed_now,
        ),
        "GET",
        "/readiness",
    )

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["components"][1] == {
        "name": "artifact_storage",
        "status": "not_configured",
        "detail": "Artifact storage path is not configured.",
    }


def test_api_readiness_returns_503_when_artifact_storage_directory_is_missing(
    tmp_path,
):
    response = _api_request(
        create_app(
            connection=_connection_with_preview_data(),
            clock=_fixed_now,
            artifact_directory=tmp_path / "missing",
        ),
        "GET",
        "/readiness",
    )

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["components"][1] == {
        "name": "artifact_storage",
        "status": "error",
        "detail": "Artifact storage path is not an existing directory.",
    }


def test_api_serves_browser_workflow_shell():
    response = _api_request(
        create_app(
            connection=_connection_with_preview_data(),
            clock=_fixed_now,
        ),
        "GET",
        "/app",
    )

    assert response.status_code == 200
    assert "SIMVal Calibration Certificate" in response.text
    assert 'id="sourceFile" type="file"' in response.text
    assert 'id="uploadSourceFile"' in response.text
    assert "/calibration-jobs" in response.text
    assert "/certificate-metadata" in response.text
    assert "/certificate-rendered-releases" in response.text
    assert "/design-assets/simval-logo" in response.text


def test_api_workflow_contract_lists_regulated_frontend_steps():
    response = _api_request(
        create_app(
            connection=_connection_with_preview_data(),
            clock=_fixed_now,
        ),
        "GET",
        "/app/workflow",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "p6_browser_workflow"
    assert "populated manually" in payload["equipment_library_policy"]
    assert [step["step_id"] for step in payload["steps"]] == [
        "session",
        "job",
        "import_data",
        "metadata",
        "reference_equipment",
        "preview",
        "release",
        "history_revision",
    ]
    action_paths = [
        action["path"]
        for step in payload["steps"]
        for action in step["actions"]
    ]
    assert "/calibration-jobs" in action_paths
    assert "/calibration-jobs/job-001/files" in action_paths
    assert "/calibration-jobs/job-001/imports" in action_paths
    assert "/calibration-jobs/job-001/temperature-data-entry" in action_paths
    assert "/calibration-jobs/job-001/verification-irtd-rows" in action_paths
    assert "/calibration-jobs/job-001/temperature-windows" in action_paths
    assert "/calibration-jobs/job-001/temperature-windows/complete" in action_paths
    assert "/calibration-jobs/job-001/temperature-calculations" in action_paths
    assert "/calibration-jobs/job-001/technical-review-submissions" in action_paths
    assert "/calibration-jobs/job-001/technical-review-approvals" in action_paths
    assert "/calibration-jobs/job-001/qa-release-approvals" in action_paths
    assert "/certificate-metadata" in action_paths
    assert "/reference-equipment-selections" in action_paths
    assert "/certificate-previews" in action_paths
    assert "/certificate-rendered-releases" in action_paths
    assert "/certificate-history/job-001" in action_paths


def test_api_serves_controlled_simval_logo_asset():
    response = _api_request(
        create_app(
            connection=_connection_with_preview_data(),
            clock=_fixed_now,
        ),
        "GET",
        "/design-assets/simval-logo",
    )

    assert response.status_code == 200
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")


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


def test_api_reference_equipment_selection_records_selection_and_audits():
    connection = _connection_with_reference_selection_data()

    response = _api_request(
        create_app(connection=connection, clock=_fixed_now),
        "POST",
        "/reference-equipment-selections",
        headers={"X-Session-Id": "session-001"},
        json=_reference_equipment_selection_payload(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == "job-001"
    assert payload["equipment_id"] == "ref-001"
    assert payload["simval_id"] == "SIM-T-001"
    assert payload["selection_audit_event_id"] == 1
    assert payload["workflow_audit_event_id"] == 2
    assert payload["workflow_state"] == "equipment_selected"
    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.EQUIPMENT_SELECTED
    )
    assert SQLiteSelectedReferenceEquipmentRepository(connection).list_for_job(
        "job-001"
    )[0].selected_by == "user-001"


def test_api_reference_equipment_selection_rejects_unauthorized_session():
    connection = _connection_with_reference_selection_data(
        user_roles=(Role.READ_ONLY,)
    )

    response = _api_request(
        create_app(connection=connection, clock=_fixed_now),
        "POST",
        "/reference-equipment-selections",
        headers={"X-Session-Id": "session-001"},
        json=_reference_equipment_selection_payload(),
    )

    assert response.status_code == 403
    assert SQLiteSelectedReferenceEquipmentRepository(connection).list_for_job(
        "job-001"
    ) == ()
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    ) == ()


def test_api_reference_equipment_selection_rejects_wrong_workflow_state():
    connection = _connection_with_reference_selection_data(
        job_state=WorkflowState.DRAFT
    )

    response = _api_request(
        create_app(connection=connection, clock=_fixed_now),
        "POST",
        "/reference-equipment-selections",
        headers={"X-Session-Id": "session-001"},
        json=_reference_equipment_selection_payload(),
    )

    assert response.status_code == 409
    assert SQLiteSelectedReferenceEquipmentRepository(connection).list_for_job(
        "job-001"
    ) == ()
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
            "accreditation_mark_allowed": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == "job-001"
    assert payload["generated_by"] == "user-001"
    assert payload["accreditation_mark_allowed"] is True
    assert payload["summary_ids"] == ["point-001"]
    assert payload["reference_equipment"][0]["simval_id"] == "SIM-T-001"
    assert payload["reference_equipment"][0]["serial_number"] == "IRT-123"
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
            "accreditation_mark_allowed": True,
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
            "accreditation_mark_allowed": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["certificate_id"] == "cert-001"
    assert payload["status"] == "released"
    assert payload["accreditation_mark_allowed"] is True
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
            "accreditation_mark_allowed": True,
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
            "accreditation_mark_allowed": True,
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
            "accreditation_mark_allowed": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    artifact_path = tmp_path / "SIMVAL-CAL-0001.pdf"
    assert artifact_path.exists()
    assert payload["certificate_id"] == "cert-001"
    assert payload["status"] == "released"
    assert payload["accreditation_mark_allowed"] is True
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
            "accreditation_mark_allowed": True,
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
            "accreditation_mark_allowed": True,
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
            "accreditation_mark_allowed": True,
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
            "accreditation_mark_allowed": True,
        },
    )

    assert response.status_code == 403
    assert not (tmp_path / "SIMVAL-CAL-0001.pdf").exists()
    assert SQLiteCertificateRecordRepository(connection).list_for_job("job-001") == ()


def test_api_certificate_revision_records_revision_and_workflow():
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
            "accreditation_mark_allowed": True,
        },
    )
    assert preview_response.status_code == 200
    release_response = _api_request(
        app,
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
            "accreditation_mark_allowed": True,
        },
    )
    assert release_response.status_code == 200

    response = _api_request(
        app,
        "POST",
        "/certificate-revisions",
        headers={"X-Session-Id": "session-001"},
        json={
            "certificate_id": "cert-001",
            "revision_id": "rev-001",
            "reason": "Corrected customer address after QA approval.",
            "software_version": "app-0.1.0",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["revision_id"] == "rev-001"
    assert payload["original_certificate_id"] == "cert-001"
    assert payload["original_certificate_number"] == "SIMVAL-CAL-0001"
    assert payload["revision_audit_event_id"] == 5
    assert payload["workflow_audit_event_id"] == 6
    assert payload["workflow_state"] == "revised"
    assert SQLiteCertificateRevisionRepository(connection).get("rev-001").reason == (
        "Corrected customer address after QA approval."
    )
    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.REVISED
    )


def test_api_certificate_history_returns_artifacts_and_revisions():
    connection = _connection_with_preview_data(
        job_state=WorkflowState.APPROVED,
        user_roles=(Role.QA_APPROVER,),
    )
    app = create_app(connection=connection, clock=_fixed_now)
    assert _api_request(
        app,
        "POST",
        "/certificate-previews",
        headers={"X-Session-Id": "session-001"},
        json={
            "job_id": "job-001",
            "template_version": "template-2026-001",
            "software_version": "app-0.1.0",
            "accreditation_mark_allowed": True,
        },
    ).status_code == 200
    assert _api_request(
        app,
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
            "accreditation_mark_allowed": True,
        },
    ).status_code == 200
    assert _api_request(
        app,
        "POST",
        "/certificate-revisions",
        headers={"X-Session-Id": "session-001"},
        json={
            "certificate_id": "cert-001",
            "revision_id": "rev-001",
            "reason": "Corrected customer address after QA approval.",
            "software_version": "app-0.1.0",
        },
    ).status_code == 200

    response = _api_request(
        app,
        "GET",
        "/certificate-history/job-001",
        headers={"X-Session-Id": "session-001"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == "job-001"
    assert payload["entries"][0]["certificate_id"] == "cert-001"
    assert payload["entries"][0]["artifacts"][0]["storage_uri"] == (
        "controlled-local://SIMVAL-CAL-0001.pdf"
    )
    assert payload["entries"][0]["artifacts"][0]["checksum_sha256"] == "b" * 64
    assert payload["entries"][0]["revisions"][0]["revision_id"] == "rev-001"
    assert payload["entries"][0]["revisions"][0]["reason"] == (
        "Corrected customer address after QA approval."
    )


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
            "accreditation_mark_allowed": True,
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
            "accreditation_mark_allowed": True,
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
            "accreditation_mark_allowed": True,
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
    SQLiteSelectedReferenceEquipmentRepository(connection).add(_selected_reference())
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


def _connection_with_reference_selection_data(
    *,
    job_state: WorkflowState = WorkflowState.METADATA_COMPLETE,
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


def _reference_equipment_selection_payload() -> dict:
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


def _selected_reference() -> SelectedReferenceEquipment:
    return SelectedReferenceEquipment(
        job_id="job-001",
        equipment=ReferenceEquipment(
            id="ref-001",
            simval_id="SIM-T-001",
            equipment_type="IRTD",
            serial_number="IRT-123",
            discipline=Discipline.TEMPERATURE,
            calibration_certificate_reference="DANAK-CAL-12345",
            calibration_due_date=date(2027, 4, 30),
            status=EquipmentStatus.ACTIVE,
            usable_range=EquipmentRange(minimum=-90.0, maximum=140.0, unit="deg C"),
            traceability_statement="Accredited calibration with SI traceability.",
        ),
        selected_by="operator-001",
        selected_at=datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
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
