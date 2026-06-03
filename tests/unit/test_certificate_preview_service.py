import sqlite3
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.backend.audit.events import AuditAction
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
    CertificatePreviewServiceError,
    build_certificate_preview_for_session,
)
from app.calculation_engine.common.summary import MeasurementPointSummary


def _connection_with_summary(
    *,
    job_state: WorkflowState = WorkflowState.CALCULATED,
    user_roles: tuple[Role, ...] = (Role.OPERATOR,),
    include_metadata: bool = True,
    include_reference_equipment: bool = True,
    selected_reference_equipment: SelectedReferenceEquipment | None = None,
) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    SQLiteCalibrationJobRepository(connection).add(_job(job_state))
    if include_metadata:
        SQLiteCertificateMetadataRepository(connection).add(_metadata())
    SQLiteUploadedFileRepository(connection).add(_uploaded_file())
    SQLiteDeviceUnderTestRepository(connection).add(_dut())
    if include_reference_equipment:
        SQLiteSelectedReferenceEquipmentRepository(connection).add(
            selected_reference_equipment or _selected_reference_equipment()
        )
    SQLiteMeasurementWindowRepository(connection).add(_window("window-001", -80.0))
    SQLiteMeasurementPointSummaryRepository(connection).add(_summary())
    SQLiteUserAccountRepository(connection).add(_user(user_roles))
    SQLiteUserSessionRepository(connection).add(_session())
    return connection


def test_build_certificate_preview_for_session_consumes_locked_summaries_and_audits():
    connection = _connection_with_summary()

    result = build_certificate_preview_for_session(
        connection=connection,
        session_id="session-001",
        job_id="job-001",
        template_version="template-2026-001",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
    )

    preview = result.preview
    assert preview.generated_by == "user-001"
    assert preview.metadata.client_name == "SIMVal customer"
    assert preview.metadata.purchase_order == "PO-12345"
    assert preview.duts[0].serial_number == "MJT1"
    assert preview.reference_equipment[0].simval_id == "SIM-T-001"
    assert preview.summary_ids == ("point-001",)
    assert preview.rows[0].reference == pytest.approx(-80.0305)
    assert preview.rows[0].display_error_of_indication == Decimal("-0.004")
    assert result.audit_event_id == 1
    assert result.audit_event.action is AuditAction.CERTIFICATE_PREVIEW_GENERATED
    assert result.audit_event.user_id == "user-001"
    assert result.audit_event.new_value == {
        "summary_ids": ["point-001"],
        "dut_ids": ["dut-001"],
        "reference_equipment_ids": ["ref-001"],
        "metadata_recorded_at": "2026-06-01T14:00:00+00:00",
        "row_count": 1,
        "template_version": "template-2026-001",
    }
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    ) == (result.audit_event,)


def test_build_certificate_preview_for_session_rejects_unauthorized_actor():
    connection = _connection_with_summary(user_roles=(Role.READ_ONLY,))

    with pytest.raises(AuthenticationServiceError):
        build_certificate_preview_for_session(
            connection=connection,
            session_id="session-001",
            job_id="job-001",
            template_version="template-2026-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
        )

    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    ) == ()


def test_build_certificate_preview_for_session_rejects_before_calculated_state():
    connection = _connection_with_summary(job_state=WorkflowState.WINDOWS_SELECTED)

    with pytest.raises(CertificatePreviewServiceError):
        build_certificate_preview_for_session(
            connection=connection,
            session_id="session-001",
            job_id="job-001",
            template_version="template-2026-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
        )

    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    ) == ()


def test_build_certificate_preview_for_session_rejects_missing_summaries():
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    SQLiteCalibrationJobRepository(connection).add(_job(WorkflowState.CALCULATED))
    SQLiteUserAccountRepository(connection).add(_user((Role.OPERATOR,)))
    SQLiteUserSessionRepository(connection).add(_session())

    with pytest.raises(CertificatePreviewServiceError):
        build_certificate_preview_for_session(
            connection=connection,
            session_id="session-001",
            job_id="job-001",
            template_version="template-2026-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
        )


def test_build_certificate_preview_for_session_rejects_missing_metadata():
    connection = _connection_with_summary(include_metadata=False)

    with pytest.raises(CertificatePreviewServiceError) as exc_info:
        build_certificate_preview_for_session(
            connection=connection,
            session_id="session-001",
            job_id="job-001",
            template_version="template-2026-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
        )

    assert "metadata" in str(exc_info.value).lower()
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    ) == ()


def test_build_certificate_preview_for_session_rejects_missing_reference_equipment():
    connection = _connection_with_summary(include_reference_equipment=False)

    with pytest.raises(CertificatePreviewServiceError) as exc_info:
        build_certificate_preview_for_session(
            connection=connection,
            session_id="session-001",
            job_id="job-001",
            template_version="template-2026-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
        )

    assert "reference equipment" in str(exc_info.value).lower()
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    ) == ()


def test_build_certificate_preview_for_session_rejects_overdue_reference_equipment():
    connection = _connection_with_summary(
        selected_reference_equipment=_selected_reference_equipment(
            calibration_due_date=date(2026, 5, 31)
        )
    )

    with pytest.raises(CertificatePreviewServiceError) as exc_info:
        build_certificate_preview_for_session(
            connection=connection,
            session_id="session-001",
            job_id="job-001",
            template_version="template-2026-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
        )

    assert "equipment_overdue" in str(exc_info.value)
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    ) == ()


def test_build_certificate_preview_for_session_rejects_out_of_range_reference_equipment():
    connection = _connection_with_summary(
        selected_reference_equipment=_selected_reference_equipment(
            range_minimum=0.0,
            range_maximum=140.0,
        )
    )

    with pytest.raises(CertificatePreviewServiceError) as exc_info:
        build_certificate_preview_for_session(
            connection=connection,
            session_id="session-001",
            job_id="job-001",
            template_version="template-2026-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
        )

    assert "equipment_out_of_range" in str(exc_info.value)
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    ) == ()


def test_build_certificate_preview_for_session_rejects_mismatched_versions():
    connection = _connection_with_summary()
    SQLiteMeasurementWindowRepository(connection).add(_window("window-002", 0.0))
    SQLiteMeasurementPointSummaryRepository(connection).add(
        _summary(
            point_id="point-002",
            measurement_window_id="window-002",
            constant_set_version="constants-2026-002",
        )
    )

    with pytest.raises(CertificatePreviewServiceError) as exc_info:
        build_certificate_preview_for_session(
            connection=connection,
            session_id="session-001",
            job_id="job-001",
            template_version="template-2026-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
        )

    assert "constant set version" in str(exc_info.value)
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    ) == ()


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


def _selected_reference_equipment(
    *,
    calibration_due_date: date = date(2027, 4, 30),
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
            calibration_due_date=calibration_due_date,
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


def _window(window_id: str, setpoint: float) -> MeasurementWindow:
    return MeasurementWindow(
        id=window_id,
        job_id="job-001",
        dut_id="dut-001",
        setpoint=setpoint,
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


def _summary(
    *,
    point_id: str = "point-001",
    measurement_window_id: str = "window-001",
    constant_set_version: str = "constants-2026-001",
) -> MeasurementPointSummary:
    return MeasurementPointSummary(
        point_id=point_id,
        job_id="job-001",
        dut_id="dut-001",
        measurement_window_id=measurement_window_id,
        reference=-80.0305,
        indication=-80.035,
        unit="deg C",
        error_of_indication=-0.0045,
        calculated_expanded_uncertainty=Decimal("0.0124231"),
        cmc_floor=Decimal("0.010"),
        reported_expanded_uncertainty=Decimal("0.012"),
        display_error_of_indication=Decimal("-0.004"),
        calculation_engine_version="calc-engine-0.1.0",
        constant_set_version=constant_set_version,
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
