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
    MeasurementMode,
    MeasurementReading,
    MeasurementWindow,
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
    SQLiteMeasurementPointSummaryRepository,
    SQLiteMeasurementWindowRepository,
    SQLiteUncertaintyBudgetRepository,
    SQLiteUploadedFileRepository,
    SQLiteUserAccountRepository,
    SQLiteUserSessionRepository,
    initialize_schema,
)
from app.backend.services.authentication import AuthenticationServiceError
from app.backend.services.pressure_calculations import (
    AutomaticPressurePointInput,
    ManualPressurePointInput,
    PressureCalculationServiceError,
    calculate_pressure_measurement_points,
    calculate_pressure_measurement_points_for_session,
)
from app.calculation_engine.pressure.results import (
    PressureKind,
    PressurePointUncertaintyInput,
)


def test_calculate_manual_pressure_point_persists_summary_audit_and_workflow():
    connection = _connection_with_pressure_job(mode=MeasurementMode.MANUAL)

    result = calculate_pressure_measurement_points(
        connection=connection,
        job_id="pressure-job-001",
        manual_points=(_manual_point(),),
        automatic_points=(),
        user_id="operator-001",
        software_version="app-0.1.0",
        calculation_engine_version="calc-engine-0.1.0",
        constant_set_version="constants-pressure-001",
        budget_version="budget-pressure-001",
        timestamp=_timestamp(),
    )

    assert len(result.points) == 1
    point = result.points[0]
    assert point.calculation_type == "manual"
    assert point.pressure_kind is PressureKind.GAUGE
    assert point.calculation.summary.reported_expanded_uncertainty == Decimal("0.0042")
    assert (
        SQLiteMeasurementPointSummaryRepository(connection).get(
            "pressure-point-001"
        )
        == point.calculation.summary
    )
    assert SQLiteCalibrationJobRepository(connection).get("pressure-job-001").state is (
        WorkflowState.CALCULATED
    )
    events = SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "pressure-job-001",
    )
    assert tuple(event.action for event in events) == (
        AuditAction.CALCULATION_RUN,
        AuditAction.WORKFLOW_TRANSITIONED,
    )
    assert events[0].new_value["discipline"] == "pressure"
    assert events[0].new_value["summary_ids"] == ["pressure-point-001"]
    assert events[0].new_value["points"][0]["calculation_type"] == "manual"
    assert events[0].new_value["points"][0]["pressure_kind"] == "gauge"
    assert events[0].new_value["points"][0]["contributions"][0]["name"] == (
        "reference_pressure_mpe"
    )


def test_calculate_automatic_pressure_point_for_session_uses_actor_for_audit():
    connection = _connection_with_pressure_job(mode=MeasurementMode.AUTOMATIC)

    result = calculate_pressure_measurement_points_for_session(
        connection=connection,
        session_id="session-001",
        job_id="pressure-job-001",
        manual_points=(),
        automatic_points=(_automatic_point(),),
        software_version="app-0.1.0",
        calculation_engine_version="calc-engine-0.1.0",
        constant_set_version="constants-pressure-001",
        budget_version="budget-pressure-001",
        timestamp=_timestamp(),
    )

    assert result.calculation_audit_event.user_id == "user-001"
    assert result.workflow_audit_event.user_id == "user-001"
    assert result.points[0].calculation_type == "automatic"
    assert result.points[0].calculation.summary.reference == pytest.approx(100.001)
    assert SQLiteCalibrationJobRepository(connection).get("pressure-job-001").state is (
        WorkflowState.CALCULATED
    )


def test_calculate_pressure_points_rejects_unauthorized_actor_before_writes():
    connection = _connection_with_pressure_job(
        mode=MeasurementMode.AUTOMATIC,
        user_roles=(Role.READ_ONLY,),
    )

    with pytest.raises(AuthenticationServiceError):
        calculate_pressure_measurement_points_for_session(
            connection=connection,
            session_id="session-001",
            job_id="pressure-job-001",
            manual_points=(),
            automatic_points=(
                _automatic_point(reference_values=(100.000,), indication_values=(100.004,)),
            ),
            software_version="app-0.1.0",
            calculation_engine_version="calc-engine-0.1.0",
            constant_set_version="constants-pressure-001",
            budget_version="budget-pressure-001",
            timestamp=_timestamp(),
        )

    assert SQLiteMeasurementPointSummaryRepository(connection).list_for_job(
        "pressure-job-001"
    ) == ()
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "pressure-job-001",
    ) == ()
    assert SQLiteCalibrationJobRepository(connection).get("pressure-job-001").state is (
        WorkflowState.WINDOWS_SELECTED
    )


def test_calculate_pressure_points_requires_pressure_discipline():
    connection = _connection_with_pressure_job(mode=MeasurementMode.MANUAL)
    connection.execute(
        "UPDATE calibration_jobs SET discipline = ? WHERE id = ?",
        (Discipline.TEMPERATURE.value, "pressure-job-001"),
    )
    connection.commit()

    with pytest.raises(PressureCalculationServiceError) as exc_info:
        calculate_pressure_measurement_points(
            connection=connection,
            job_id="pressure-job-001",
            manual_points=(_manual_point(),),
            automatic_points=(),
            user_id="operator-001",
            software_version="app-0.1.0",
            calculation_engine_version="calc-engine-0.1.0",
            constant_set_version="constants-pressure-001",
            budget_version="budget-pressure-001",
            timestamp=_timestamp(),
        )

    assert "requires pressure discipline" in str(exc_info.value)
    assert SQLiteMeasurementPointSummaryRepository(connection).list_for_job(
        "pressure-job-001"
    ) == ()


def test_calculate_pressure_points_requires_matching_job_mode():
    connection = _connection_with_pressure_job(mode=MeasurementMode.MANUAL)

    with pytest.raises(PressureCalculationServiceError) as exc_info:
        calculate_pressure_measurement_points(
            connection=connection,
            job_id="pressure-job-001",
            manual_points=(),
            automatic_points=(_automatic_point(),),
            user_id="operator-001",
            software_version="app-0.1.0",
            calculation_engine_version="calc-engine-0.1.0",
            constant_set_version="constants-pressure-001",
            budget_version="budget-pressure-001",
            timestamp=_timestamp(),
        )

    assert "manual pressure job cannot run automatic pressure points" in str(
        exc_info.value
    )
    assert SQLiteMeasurementPointSummaryRepository(connection).list_for_job(
        "pressure-job-001"
    ) == ()


def test_calculate_pressure_points_requires_approved_pressure_versions():
    connection = _connection_with_pressure_job(mode=MeasurementMode.MANUAL)

    with pytest.raises(PressureCalculationServiceError) as exc_info:
        calculate_pressure_measurement_points(
            connection=connection,
            job_id="pressure-job-001",
            manual_points=(_manual_point(),),
            automatic_points=(),
            user_id="operator-001",
            software_version="app-0.1.0",
            calculation_engine_version="calc-engine-0.1.0",
            constant_set_version="constants-pressure-001",
            budget_version="missing-budget",
            timestamp=_timestamp(),
        )

    assert "missing_approved_uncertainty_budget" in str(exc_info.value)
    assert SQLiteMeasurementPointSummaryRepository(connection).list_for_job(
        "pressure-job-001"
    ) == ()


def test_calculate_pressure_points_requires_window_belonging_to_job_and_dut():
    connection = _connection_with_pressure_job(mode=MeasurementMode.MANUAL)

    with pytest.raises(PressureCalculationServiceError) as exc_info:
        calculate_pressure_measurement_points(
            connection=connection,
            job_id="pressure-job-001",
            manual_points=(
                _manual_point(measurement_window_id="missing-window"),
            ),
            automatic_points=(),
            user_id="operator-001",
            software_version="app-0.1.0",
            calculation_engine_version="calc-engine-0.1.0",
            constant_set_version="constants-pressure-001",
            budget_version="budget-pressure-001",
            timestamp=_timestamp(),
        )

    assert "selected measurement window" in str(exc_info.value)
    assert SQLiteMeasurementPointSummaryRepository(connection).list_for_job(
        "pressure-job-001"
    ) == ()


def _connection_with_pressure_job(
    *,
    mode: MeasurementMode,
    user_roles: tuple[Role, ...] = (Role.OPERATOR,),
) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    SQLiteCalibrationJobRepository(connection).add(_job(mode))
    SQLiteUploadedFileRepository(connection).add(_pressure_file())
    SQLiteDeviceUnderTestRepository(connection).add(_dut())
    SQLiteMeasurementWindowRepository(connection).add(
        _window("pressure-window-001", setpoint=10.0, values=(10.004, 10.006))
    )
    SQLiteMeasurementWindowRepository(connection).add(
        _window(
            "pressure-auto-window-001",
            setpoint=100.0,
            values=(100.004, 100.006, 100.005),
        )
    )
    SQLiteConstantSetRepository(connection).add(_constant_set())
    SQLiteUncertaintyBudgetRepository(connection).add(_budget())
    SQLiteUserAccountRepository(connection).add(_user(user_roles))
    SQLiteUserSessionRepository(connection).add(_session())
    return connection


def _job(mode: MeasurementMode) -> CalibrationJob:
    return CalibrationJob(
        id="pressure-job-001",
        client=Client(name="SIMVal customer", address="Validated Road 1"),
        discipline=Discipline.PRESSURE,
        measurement_mode=mode,
        method="SIMVal pressure method",
        created_by="operator-001",
        state=WorkflowState.WINDOWS_SELECTED,
        created_at=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
    )


def _pressure_file() -> UploadedFile:
    return UploadedFile(
        id="pressure-file-001",
        job_id="pressure-job-001",
        original_filename="pressure-readings.csv",
        checksum_sha256="c" * 64,
        file_kind=UploadedFileKind.OTHER,
        storage_uri="controlled-local://pressure-readings.csv",
        parser_version="manual-pressure-entry-v1",
        uploaded_at=datetime(2026, 6, 1, 14, 5, tzinfo=timezone.utc),
    )


def _dut() -> DeviceUnderTest:
    return DeviceUnderTest(
        id="pressure-dut-001",
        job_id="pressure-job-001",
        make="PressureCo",
        model="Gauge",
        serial_number="PG-001",
        channel_id="PG-001",
    )


def _window(
    window_id: str,
    *,
    setpoint: float,
    values: tuple[float, ...],
) -> MeasurementWindow:
    return MeasurementWindow(
        id=window_id,
        job_id="pressure-job-001",
        dut_id="pressure-dut-001",
        setpoint=setpoint,
        unit="bar",
        selected_by="operator-001",
        selected_at=datetime(2026, 6, 1, 14, 20, tzinfo=timezone.utc),
        readings=tuple(
            MeasurementReading(
                timestamp=datetime(
                    2026,
                    6,
                    1,
                    14,
                    20 + index,
                    tzinfo=timezone.utc,
                ),
                channel_id="PG-001",
                value=value,
                unit="bar",
                source=SourceLocation(
                    uploaded_file_id="pressure-file-001",
                    source_label="Pressure",
                    row_number=index + 1,
                    column_label="indication",
                ),
            )
            for index, value in enumerate(values)
        ),
    )


def _constant_set() -> ConstantSet:
    return ConstantSet(
        version="constants-pressure-001",
        discipline=Discipline.PRESSURE,
        status=VersionStatus.APPROVED,
        effective_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        approved_by="qa-001",
        approved_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )


def _budget() -> UncertaintyBudget:
    return UncertaintyBudget(
        version="budget-pressure-001",
        budget_type="pressure",
        method="SIMVal pressure method",
        discipline=Discipline.PRESSURE,
        status=VersionStatus.APPROVED,
        linked_constant_set_version="constants-pressure-001",
        approved_by="qa-001",
        approved_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
    )


def _manual_point(**overrides) -> ManualPressurePointInput:
    values = {
        "point_id": "pressure-point-001",
        "dut_id": "pressure-dut-001",
        "measurement_window_id": "pressure-window-001",
        "pressure_kind": PressureKind.GAUGE,
        "reference_pressure": 10.0,
        "indication_values": (10.004, 10.006),
        "uncertainty_input": _uncertainty_input(setpoint=10.0),
    }
    values.update(overrides)
    return ManualPressurePointInput(**values)


def _automatic_point(**overrides) -> AutomaticPressurePointInput:
    values = {
        "point_id": "pressure-auto-point-001",
        "dut_id": "pressure-dut-001",
        "measurement_window_id": "pressure-auto-window-001",
        "pressure_kind": PressureKind.GAUGE,
        "reference_values": (100.000, 100.002, 100.001),
        "indication_values": (100.004, 100.006, 100.005),
        "uncertainty_input": _uncertainty_input(setpoint=100.0),
    }
    values.update(overrides)
    return AutomaticPressurePointInput(**values)


def _uncertainty_input(*, setpoint: float) -> PressurePointUncertaintyInput:
    return PressurePointUncertaintyInput(
        setpoint=setpoint,
        unit="bar",
        pressure_kind=PressureKind.GAUGE,
        cmc_floor=Decimal("0.001"),
        reference_expanded_uncertainty=0.004,
        dut_resolution=0.002,
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


def _timestamp() -> datetime:
    return datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc)
