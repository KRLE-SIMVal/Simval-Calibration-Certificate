import sqlite3
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.backend.audit.events import AuditAction, AuditEvent
from app.backend.auth.permissions import Role
from app.backend.auth.users import UserAccount, UserSession
from app.backend.certificates.metadata import CertificateMetadata
from app.backend.certificates.records import ArtifactType, CertificateStatus
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
    SQLiteDeviceUnderTestRepository,
    SQLiteMeasurementPointSummaryRepository,
    SQLiteMeasurementWindowRepository,
    SQLiteSelectedReferenceEquipmentRepository,
    SQLiteUploadedFileRepository,
    SQLiteUserAccountRepository,
    SQLiteUserSessionRepository,
    initialize_schema,
)
from app.backend.services.authentication import AuthenticationServiceError
from app.backend.services.certificates import (
    CertificateReleaseServiceError,
    build_certificate_preview_for_session,
    release_certificate_for_session,
)
from app.calculation_engine.common.summary import MeasurementPointSummary


def test_release_certificate_for_session_requires_preview_and_records_release():
    connection = _connection_with_release_data()
    build_certificate_preview_for_session(
        connection=connection,
        session_id="qa-session",
        job_id="job-001",
        template_version="template-2026-001",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 15, 20, tzinfo=timezone.utc),
    )

    result = release_certificate_for_session(
        connection=connection,
        session_id="qa-session",
        job_id="job-001",
        certificate_id="cert-001",
        certificate_number="SIMVAL-CAL-0001",
        artifact_id="artifact-001",
        artifact_type=ArtifactType.PDF,
        filename="SIMVAL-CAL-0001.pdf",
        checksum_sha256="b" * 64,
        storage_uri="controlled-local://SIMVAL-CAL-0001.pdf",
        template_version="template-2026-001",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
    )

    assert result.certificate.status is CertificateStatus.RELEASED
    assert result.certificate.released_by == "qa-001"
    assert result.certificate.calculation_summary_ids == ("point-001",)
    assert result.certificate.primary_artifact.generated_by == "qa-001"
    assert result.accreditation_mark_allowed is True
    assert result.export_audit_event.action is AuditAction.EXPORT_ARTIFACT_GENERATED
    assert result.release_audit_event.action is AuditAction.CERTIFICATE_RELEASED
    assert result.release_audit_event.new_value["accreditation_mark_allowed"] is True
    assert result.workflow_audit_event.action is AuditAction.WORKFLOW_TRANSITIONED
    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.RELEASED
    )
    assert SQLiteCertificateRecordRepository(connection).get("cert-001") == (
        result.certificate
    )
    audit_events = SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    )
    assert [event.action for event in audit_events] == [
        AuditAction.CERTIFICATE_PREVIEW_GENERATED,
        AuditAction.EXPORT_ARTIFACT_GENERATED,
        AuditAction.CERTIFICATE_RELEASED,
        AuditAction.WORKFLOW_TRANSITIONED,
    ]


def test_release_certificate_for_session_rejects_missing_matching_preview():
    connection = _connection_with_release_data()

    with pytest.raises(CertificateReleaseServiceError):
        release_certificate_for_session(
            connection=connection,
            session_id="qa-session",
            job_id="job-001",
            certificate_id="cert-001",
            certificate_number="SIMVAL-CAL-0001",
            artifact_id="artifact-001",
            artifact_type=ArtifactType.PDF,
            filename="SIMVAL-CAL-0001.pdf",
            checksum_sha256="b" * 64,
            storage_uri="controlled-local://SIMVAL-CAL-0001.pdf",
            template_version="template-2026-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
        )

    assert SQLiteCertificateRecordRepository(connection).list_for_job("job-001") == ()
    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.APPROVED
    )
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    ) == ()


def test_release_certificate_for_session_rejects_mismatched_preview_template():
    connection = _connection_with_release_data()
    build_certificate_preview_for_session(
        connection=connection,
        session_id="qa-session",
        job_id="job-001",
        template_version="template-2026-OLD",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 15, 20, tzinfo=timezone.utc),
    )

    with pytest.raises(CertificateReleaseServiceError):
        release_certificate_for_session(
            connection=connection,
            session_id="qa-session",
            job_id="job-001",
            certificate_id="cert-001",
            certificate_number="SIMVAL-CAL-0001",
            artifact_id="artifact-001",
            artifact_type=ArtifactType.PDF,
            filename="SIMVAL-CAL-0001.pdf",
            checksum_sha256="b" * 64,
            storage_uri="controlled-local://SIMVAL-CAL-0001.pdf",
            template_version="template-2026-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
        )

    assert SQLiteCertificateRecordRepository(connection).list_for_job("job-001") == ()
    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.APPROVED
    )


def test_release_certificate_for_session_rejects_mismatched_accreditation_scope():
    connection = _connection_with_release_data()
    build_certificate_preview_for_session(
        connection=connection,
        session_id="qa-session",
        job_id="job-001",
        template_version="template-2026-001",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 15, 20, tzinfo=timezone.utc),
        accreditation_mark_allowed=False,
    )

    with pytest.raises(CertificateReleaseServiceError):
        release_certificate_for_session(
            connection=connection,
            session_id="qa-session",
            job_id="job-001",
            certificate_id="cert-001",
            certificate_number="SIMVAL-CAL-0001",
            artifact_id="artifact-001",
            artifact_type=ArtifactType.PDF,
            filename="SIMVAL-CAL-0001.pdf",
            checksum_sha256="b" * 64,
            storage_uri="controlled-local://SIMVAL-CAL-0001.pdf",
            template_version="template-2026-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
            accreditation_mark_allowed=True,
        )

    assert SQLiteCertificateRecordRepository(connection).list_for_job("job-001") == ()
    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.APPROVED
    )


def test_release_certificate_for_session_rechecks_reference_equipment_suitability():
    connection = _connection_with_release_data(
        selected_reference=_selected_reference(range_minimum=0.0, range_maximum=140.0)
    )
    SQLiteAuditEventRepository(connection).append(
        AuditEvent(
            entity_type="calibration_job",
            entity_id="job-001",
            action=AuditAction.CERTIFICATE_PREVIEW_GENERATED,
            user_id="qa-001",
            timestamp=datetime(2026, 6, 1, 15, 20, tzinfo=timezone.utc),
            new_value={
                "summary_ids": ["point-001"],
                "dut_ids": ["dut-001"],
                "reference_equipment_ids": ["ref-001"],
                "metadata_recorded_at": "2026-06-01T14:00:00+00:00",
                "row_count": 1,
                "template_version": "template-2026-001",
            },
            software_version="app-0.1.0",
            calculation_engine_version="calc-engine-0.1.0",
            constant_set_version="constants-2026-001",
            budget_version="budget-temp-001",
        )
    )

    with pytest.raises(CertificateReleaseServiceError) as exc_info:
        release_certificate_for_session(
            connection=connection,
            session_id="qa-session",
            job_id="job-001",
            certificate_id="cert-001",
            certificate_number="SIMVAL-CAL-0001",
            artifact_id="artifact-001",
            artifact_type=ArtifactType.PDF,
            filename="SIMVAL-CAL-0001.pdf",
            checksum_sha256="b" * 64,
            storage_uri="controlled-local://SIMVAL-CAL-0001.pdf",
            template_version="template-2026-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
        )

    assert "equipment_out_of_range" in str(exc_info.value)
    assert SQLiteCertificateRecordRepository(connection).list_for_job("job-001") == ()


def test_release_certificate_for_session_rejects_before_approved_state():
    connection = _connection_with_release_data(job_state=WorkflowState.CALCULATED)
    build_certificate_preview_for_session(
        connection=connection,
        session_id="qa-session",
        job_id="job-001",
        template_version="template-2026-001",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 15, 20, tzinfo=timezone.utc),
    )

    with pytest.raises(CertificateReleaseServiceError):
        release_certificate_for_session(
            connection=connection,
            session_id="qa-session",
            job_id="job-001",
            certificate_id="cert-001",
            certificate_number="SIMVAL-CAL-0001",
            artifact_id="artifact-001",
            artifact_type=ArtifactType.PDF,
            filename="SIMVAL-CAL-0001.pdf",
            checksum_sha256="b" * 64,
            storage_uri="controlled-local://SIMVAL-CAL-0001.pdf",
            template_version="template-2026-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
        )

    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.CALCULATED
    )


def test_release_certificate_for_session_rejects_unauthorized_actor_before_audit():
    connection = _connection_with_release_data(actor_roles=(Role.OPERATOR,))
    build_certificate_preview_for_session(
        connection=connection,
        session_id="qa-session",
        job_id="job-001",
        template_version="template-2026-001",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 15, 20, tzinfo=timezone.utc),
    )

    with pytest.raises(AuthenticationServiceError):
        release_certificate_for_session(
            connection=connection,
            session_id="qa-session",
            job_id="job-001",
            certificate_id="cert-001",
            certificate_number="SIMVAL-CAL-0001",
            artifact_id="artifact-001",
            artifact_type=ArtifactType.PDF,
            filename="SIMVAL-CAL-0001.pdf",
            checksum_sha256="b" * 64,
            storage_uri="controlled-local://SIMVAL-CAL-0001.pdf",
            template_version="template-2026-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
        )

    assert SQLiteCertificateRecordRepository(connection).list_for_job("job-001") == ()
    audit_events = SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    )
    assert [event.action for event in audit_events] == [
        AuditAction.CERTIFICATE_PREVIEW_GENERATED
    ]


def test_release_certificate_for_session_rejects_same_user_qa_approval_and_release():
    connection = _connection_with_release_data()
    SQLiteAuditEventRepository(connection).append(
        AuditEvent(
            entity_type="calibration_job",
            entity_id="job-001",
            action=AuditAction.WORKFLOW_TRANSITIONED,
            user_id="qa-001",
            timestamp=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
            previous_value={"state": "qa_review"},
            new_value={"state": "approved"},
            software_version="app-0.1.0",
        )
    )
    build_certificate_preview_for_session(
        connection=connection,
        session_id="qa-session",
        job_id="job-001",
        template_version="template-2026-001",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 15, 20, tzinfo=timezone.utc),
    )

    with pytest.raises(CertificateReleaseServiceError) as exc_info:
        release_certificate_for_session(
            connection=connection,
            session_id="qa-session",
            job_id="job-001",
            certificate_id="cert-001",
            certificate_number="SIMVAL-CAL-0001",
            artifact_id="artifact-001",
            artifact_type=ArtifactType.PDF,
            filename="SIMVAL-CAL-0001.pdf",
            checksum_sha256="b" * 64,
            storage_uri="controlled-local://SIMVAL-CAL-0001.pdf",
            template_version="template-2026-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
        )

    assert "reviewer_independence_violation" in str(exc_info.value)
    assert SQLiteCertificateRecordRepository(connection).list_for_job("job-001") == ()
    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.APPROVED
    )


def _connection_with_release_data(
    *,
    job_state: WorkflowState = WorkflowState.APPROVED,
    actor_roles: tuple[Role, ...] = (Role.QA_APPROVER,),
    selected_reference: SelectedReferenceEquipment | None = None,
) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    SQLiteCalibrationJobRepository(connection).add(_job(job_state))
    SQLiteCertificateMetadataRepository(connection).add(_metadata())
    SQLiteUploadedFileRepository(connection).add(_uploaded_file())
    SQLiteDeviceUnderTestRepository(connection).add(_dut())
    SQLiteSelectedReferenceEquipmentRepository(connection).add(
        selected_reference or _selected_reference()
    )
    SQLiteMeasurementWindowRepository(connection).add(_window())
    SQLiteMeasurementPointSummaryRepository(connection).add(_summary())
    SQLiteUserAccountRepository(connection).add(_qa_user(actor_roles))
    SQLiteUserSessionRepository(connection).add(_qa_session())
    return connection


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


def _selected_reference(
    *,
    range_minimum: float = -90.0,
    range_maximum: float = 140.0,
) -> SelectedReferenceEquipment:
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
            usable_range=EquipmentRange(
                minimum=range_minimum,
                maximum=range_maximum,
                unit="deg C",
            ),
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


def _qa_user(roles: tuple[Role, ...]) -> UserAccount:
    return UserAccount(
        id="qa-001",
        display_name="QA User",
        email="qa@example.com",
        roles=roles,
        created_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
    )


def _qa_session() -> UserSession:
    return UserSession(
        id="qa-session",
        user_id="qa-001",
        issued_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 1, 16, 0, tzinfo=timezone.utc),
    )
