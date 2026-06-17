import sqlite3
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.backend.audit.events import AuditAction
from app.backend.auth.permissions import Role
from app.backend.auth.users import UserAccount, UserSession
from app.backend.domain.entities import (
    CalibrationJob,
    Client,
    DeviceUnderTest,
    Discipline,
    LinkedTemperatureReading,
    MeasurementMode,
    MeasurementReading,
    MeasurementWindow,
    RequiredTemperatureSetpoint,
    SourceLocation,
    UploadedFile,
    UploadedFileKind,
)
from app.backend.domain.versioning import ConstantSet, UncertaintyBudget, VersionStatus
from app.backend.domain.workflow import WorkflowState
from app.backend.persistence.sqlite import (
    SQLiteAuditEventRepository,
    SQLiteCalibrationJobRepository,
    SQLiteConstantSetRepository,
    SQLiteDeviceUnderTestRepository,
    SQLiteLinkedTemperatureReadingRepository,
    SQLiteMeasurementPointSummaryRepository,
    SQLiteMeasurementWindowRepository,
    SQLiteRequiredTemperatureSetpointRepository,
    SQLiteUserAccountRepository,
    SQLiteUserSessionRepository,
    SQLiteUncertaintyBudgetRepository,
    SQLiteUploadedFileRepository,
    initialize_schema,
)
from app.backend.services.authentication import AuthenticationServiceError
from app.backend.services.temperature_calculations import (
    TemperatureCalculationServiceError,
    calculate_temperature_measurement_points,
    calculate_temperature_measurement_points_for_session,
)
from app.calculation_engine.temperature.results import (
    TemperaturePointUncertaintyInput,
    TemperatureTypeAMethod,
)


def _connection_with_calculable_job(
    *,
    include_linked_readings: bool = True,
    user_roles: tuple[Role, ...] = (Role.OPERATOR,),
    user_active: bool = True,
) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    SQLiteCalibrationJobRepository(connection).add(_job())
    file_repository = SQLiteUploadedFileRepository(connection)
    file_repository.add(_calibration_file())
    file_repository.add(_verification_file())
    SQLiteDeviceUnderTestRepository(connection).add(_dut())
    SQLiteRequiredTemperatureSetpointRepository(connection).add_many(
        (_setpoint("setpoint-001", -80.0, 0),)
    )
    if include_linked_readings:
        SQLiteLinkedTemperatureReadingRepository(connection).add_many(
            job_id="job-001",
            linked_readings=_linked_readings(),
        )
    SQLiteMeasurementWindowRepository(connection).add(_window())
    SQLiteConstantSetRepository(connection).add(_constant_set())
    SQLiteUncertaintyBudgetRepository(connection).add(_budget())
    SQLiteUserAccountRepository(connection).add(
        _user(roles=user_roles, active=user_active)
    )
    SQLiteUserSessionRepository(connection).add(_session())
    return connection


def test_calculate_temperature_measurement_points_persists_summary_and_audit():
    connection = _connection_with_calculable_job()

    result = calculate_temperature_measurement_points(
        connection=connection,
        job_id="job-001",
        uncertainty_inputs=(_uncertainty_input(),),
        user_id="operator-001",
        software_version="app-0.1.0",
        calculation_engine_version="calc-engine-0.1.0",
        constant_set_version="constants-2026-001",
        budget_version="budget-temp-001",
        timestamp=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
    )

    assert len(result.summaries) == 1
    summary = result.summaries[0]
    assert summary.point_id == "job-001-window-001-summary"
    assert summary.reference == pytest.approx(-80.0305)
    assert summary.indication == pytest.approx(-80.035)
    assert summary.reported_expanded_uncertainty == Decimal("0.012")
    assert (
        SQLiteMeasurementPointSummaryRepository(connection).get(summary.point_id)
        == summary
    )
    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.CALCULATED
    )
    events = SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    )
    assert tuple(event.action for event in events) == (
        AuditAction.CALCULATION_RUN,
        AuditAction.WORKFLOW_TRANSITIONED,
    )
    assert result.calculation_audit_event_id == 1
    assert result.workflow_audit_event_id == 2
    assert events[0].new_value["summary_ids"] == ["job-001-window-001-summary"]
    assert events[0].new_value["points"][0]["measurement_window_id"] == "window-001"
    assert events[0].new_value["points"][0]["type_a_method"] == (
        "independent_reference_and_dut"
    )
    assert events[0].new_value["points"][0]["contributions"][0]["name"] == (
        "reference_sensor_calibration"
    )


def test_calculate_temperature_measurement_points_for_session_uses_actor_for_audit():
    connection = _connection_with_calculable_job()

    result = calculate_temperature_measurement_points_for_session(
        connection=connection,
        session_id="session-001",
        job_id="job-001",
        uncertainty_inputs=(_uncertainty_input(),),
        software_version="app-0.1.0",
        calculation_engine_version="calc-engine-0.1.0",
        constant_set_version="constants-2026-001",
        budget_version="budget-temp-001",
        timestamp=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
    )

    assert result.calculation_audit_event.user_id == "user-001"
    assert result.workflow_audit_event.user_id == "user-001"
    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.CALCULATED
    )


def test_calculate_temperature_measurement_points_for_session_rejects_unauthorized_actor():
    connection = _connection_with_calculable_job(user_roles=(Role.READ_ONLY,))

    with pytest.raises(AuthenticationServiceError):
        calculate_temperature_measurement_points_for_session(
            connection=connection,
            session_id="session-001",
            job_id="job-001",
            uncertainty_inputs=(_uncertainty_input(),),
            software_version="app-0.1.0",
            calculation_engine_version="calc-engine-0.1.0",
            constant_set_version="constants-2026-001",
            budget_version="budget-temp-001",
            timestamp=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
        )

    assert SQLiteMeasurementPointSummaryRepository(connection).list_for_job("job-001") == ()
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    ) == ()
    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.WINDOWS_SELECTED
    )


def test_calculate_temperature_measurement_points_requires_windows_selected_state():
    connection = _connection_with_calculable_job()
    connection.execute(
        "UPDATE calibration_jobs SET state = ? WHERE id = ?",
        (WorkflowState.DATA_ENTERED.value, "job-001"),
    )
    connection.commit()

    with pytest.raises(TemperatureCalculationServiceError):
        calculate_temperature_measurement_points(
            connection=connection,
            job_id="job-001",
            uncertainty_inputs=(_uncertainty_input(),),
            user_id="operator-001",
            software_version="app-0.1.0",
            calculation_engine_version="calc-engine-0.1.0",
            constant_set_version="constants-2026-001",
            budget_version="budget-temp-001",
            timestamp=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
        )


def test_calculate_temperature_measurement_points_requires_approved_versions():
    connection = _connection_with_calculable_job()

    with pytest.raises(TemperatureCalculationServiceError) as exc_info:
        calculate_temperature_measurement_points(
            connection=connection,
            job_id="job-001",
            uncertainty_inputs=(_uncertainty_input(),),
            user_id="operator-001",
            software_version="app-0.1.0",
            calculation_engine_version="calc-engine-0.1.0",
            constant_set_version="constants-2026-001",
            budget_version="missing-budget",
            timestamp=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
        )

    assert "missing_approved_uncertainty_budget" in str(exc_info.value)
    assert SQLiteMeasurementPointSummaryRepository(connection).list_for_job("job-001") == ()
    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.WINDOWS_SELECTED
    )


def test_calculate_temperature_measurement_points_requires_linked_irtd_reference():
    connection = _connection_with_calculable_job(include_linked_readings=False)

    with pytest.raises(TemperatureCalculationServiceError):
        calculate_temperature_measurement_points(
            connection=connection,
            job_id="job-001",
            uncertainty_inputs=(_uncertainty_input(),),
            user_id="operator-001",
            software_version="app-0.1.0",
            calculation_engine_version="calc-engine-0.1.0",
            constant_set_version="constants-2026-001",
            budget_version="budget-temp-001",
            timestamp=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
        )

    assert SQLiteMeasurementPointSummaryRepository(connection).list_for_job("job-001") == ()
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    ) == ()


def test_calculate_temperature_measurement_points_rejects_duplicate_windows():
    connection = _connection_with_calculable_job()
    SQLiteMeasurementWindowRepository(connection).add(
        _window(window_id="window-002", row_offset=10)
    )

    with pytest.raises(TemperatureCalculationServiceError) as exc_info:
        calculate_temperature_measurement_points(
            connection=connection,
            job_id="job-001",
            uncertainty_inputs=(_uncertainty_input(),),
            user_id="operator-001",
            software_version="app-0.1.0",
            calculation_engine_version="calc-engine-0.1.0",
            constant_set_version="constants-2026-001",
            budget_version="budget-temp-001",
            timestamp=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
        )

    assert "duplicate selected windows" in str(exc_info.value)
    assert SQLiteMeasurementPointSummaryRepository(connection).list_for_job("job-001") == ()


def test_calculate_temperature_measurement_points_requires_uncertainty_input_for_setpoint():
    connection = _connection_with_calculable_job()

    with pytest.raises(TemperatureCalculationServiceError) as exc_info:
        calculate_temperature_measurement_points(
            connection=connection,
            job_id="job-001",
            uncertainty_inputs=(
                TemperaturePointUncertaintyInput(
                    setpoint=0.0,
                    unit="deg C",
                    cmc_floor=Decimal("0.010"),
                    reference_expanded_uncertainty=0.010,
                ),
            ),
            user_id="operator-001",
            software_version="app-0.1.0",
            calculation_engine_version="calc-engine-0.1.0",
            constant_set_version="constants-2026-001",
            budget_version="budget-temp-001",
            timestamp=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
        )

    assert "-80 deg C" in str(exc_info.value)
    assert SQLiteMeasurementPointSummaryRepository(connection).list_for_job("job-001") == ()


def test_calculate_temperature_measurement_points_audits_paired_type_a_method():
    connection = _connection_with_calculable_job()

    result = calculate_temperature_measurement_points(
        connection=connection,
        job_id="job-001",
        uncertainty_inputs=(
            _uncertainty_input(
                type_a_method=TemperatureTypeAMethod.PAIRED_ERROR_DIFFERENCES
            ),
        ),
        user_id="operator-001",
        software_version="app-0.1.0",
        calculation_engine_version="calc-engine-0.1.0",
        constant_set_version="constants-2026-001",
        budget_version="budget-temp-001",
        timestamp=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
    )

    point = result.calculation_audit_event.new_value["points"][0]
    assert point["type_a_method"] == "paired_error_differences"
    assert [
        contribution["name"] for contribution in point["contributions"]
    ] == [
        "reference_sensor_calibration",
        "paired_error_repeatability",
        "bath_or_thermostat",
        "dut_resolution",
    ]


def _job() -> CalibrationJob:
    return CalibrationJob(
        id="job-001",
        client=Client(name="SIMVal customer", address="Validated Road 1"),
        discipline=Discipline.TEMPERATURE,
        measurement_mode=MeasurementMode.AUTOMATIC,
        method="ValProbe RT linked XLSX/PDF workflow",
        created_by="operator-001",
        state=WorkflowState.WINDOWS_SELECTED,
        created_at=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
    )


def _calibration_file() -> UploadedFile:
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


def _verification_file() -> UploadedFile:
    return UploadedFile(
        id="file-002",
        job_id="job-001",
        original_filename="sanitized-verification.pdf",
        checksum_sha256="b" * 64,
        file_kind=UploadedFileKind.VERIFICATION_PDF,
        storage_uri="controlled-local://sanitized-verification.pdf",
        parser_version="verification-irtd-table-parser-v1",
        uploaded_at=datetime(2026, 6, 1, 14, 7, tzinfo=timezone.utc),
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


def _setpoint(
    setpoint_id: str,
    setpoint: float,
    sequence_index: int,
) -> RequiredTemperatureSetpoint:
    return RequiredTemperatureSetpoint(
        id=setpoint_id,
        job_id="job-001",
        setpoint=setpoint,
        unit="deg C",
        sequence_index=sequence_index,
        created_by="operator-001",
        created_at=datetime(2026, 6, 1, 14, 15, tzinfo=timezone.utc),
    )


def _linked_readings() -> tuple[LinkedTemperatureReading, ...]:
    return (
        _linked_reading(
            datetime(2026, 4, 8, 15, 45, tzinfo=timezone.utc),
            -80.036,
            -80.031,
            12,
            2,
        ),
        _linked_reading(
            datetime(2026, 4, 8, 15, 46, tzinfo=timezone.utc),
            -80.034,
            -80.030,
            13,
            3,
        ),
    )


def _linked_reading(
    timestamp: datetime,
    indication_value: float,
    reference_value: float,
    indication_row: int,
    reference_row: int,
) -> LinkedTemperatureReading:
    return LinkedTemperatureReading(
        timestamp=timestamp,
        dut_channel_id="MJT1-A",
        indication=MeasurementReading(
            timestamp=timestamp,
            channel_id="MJT1-A",
            value=indication_value,
            unit="deg C",
            source=SourceLocation(
                uploaded_file_id="file-001",
                source_label="Temperature",
                row_number=indication_row,
                column_label="B",
            ),
        ),
        reference=MeasurementReading(
            timestamp=timestamp,
            channel_id="IRTD",
            value=reference_value,
            unit="deg C",
            source=SourceLocation(
                uploaded_file_id="file-002",
                source_label="Verification IRTD",
                row_number=reference_row,
                column_label="IRTD (deg C)",
            ),
        ),
    )


def _window(window_id: str = "window-001", row_offset: int = 0) -> MeasurementWindow:
    return MeasurementWindow(
        id=window_id,
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
                    row_number=12 + row_offset,
                    column_label="B",
                ),
            ),
            MeasurementReading(
                timestamp=datetime(2026, 4, 8, 15, 46, tzinfo=timezone.utc),
                channel_id="MJT1-A",
                value=-80.034,
                unit="deg C",
                source=SourceLocation(
                    uploaded_file_id="file-001",
                    source_label="Temperature",
                    row_number=13 + row_offset,
                    column_label="B",
                ),
            ),
        ),
    )


def _constant_set() -> ConstantSet:
    return ConstantSet(
        version="constants-2026-001",
        discipline=Discipline.TEMPERATURE,
        status=VersionStatus.APPROVED,
        effective_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        approved_by="qa-001",
        approved_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )


def _budget() -> UncertaintyBudget:
    return UncertaintyBudget(
        version="budget-temp-001",
        budget_type="temperature_logger",
        method="ValProbe RT automatic temperature",
        discipline=Discipline.TEMPERATURE,
        status=VersionStatus.APPROVED,
        linked_constant_set_version="constants-2026-001",
        approved_by="qa-001",
        approved_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
    )


def _uncertainty_input(
    *,
    type_a_method: TemperatureTypeAMethod = (
        TemperatureTypeAMethod.INDEPENDENT_REFERENCE_AND_DUT
    ),
) -> TemperaturePointUncertaintyInput:
    return TemperaturePointUncertaintyInput(
        setpoint=-80.0,
        unit="deg C",
        cmc_floor=Decimal("0.010"),
        reference_expanded_uncertainty=0.010,
        bath_expanded_uncertainty=0.004,
        dut_resolution=0.010,
        type_a_method=type_a_method,
    )


def _user(
    *,
    roles: tuple[Role, ...],
    active: bool,
) -> UserAccount:
    return UserAccount(
        id="user-001",
        display_name="Operator User",
        email="operator@example.com",
        roles=roles,
        active=active,
        created_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
    )


def _session() -> UserSession:
    return UserSession(
        id="session-001",
        user_id="user-001",
        issued_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 1, 16, 0, tzinfo=timezone.utc),
    )
