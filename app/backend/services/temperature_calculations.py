"""Temperature calculation orchestration services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import sqlite3

from app.backend.audit.events import AuditAction, AuditEvent
from app.backend.auth.permissions import Action
from app.backend.domain.entities import LinkedTemperatureReading, MeasurementWindow
from app.backend.domain.versioning import release_version_blockers
from app.backend.domain.workflow import WorkflowState
from app.backend.persistence.sqlite import (
    RecordNotFoundError,
    SQLiteAuditEventRepository,
    SQLiteCalibrationJobRepository,
    SQLiteConstantSetRepository,
    SQLiteDeviceUnderTestRepository,
    SQLiteLinkedTemperatureReadingRepository,
    SQLiteMeasurementPointSummaryRepository,
    SQLiteMeasurementWindowRepository,
    SQLiteRequiredTemperatureSetpointRepository,
    SQLiteUncertaintyBudgetRepository,
)
from app.backend.services.authentication import resolve_actor_for_action
from app.backend.services.workflow import transition_calibration_job
from app.calculation_engine.common.summary import MeasurementPointSummary
from app.calculation_engine.temperature.results import (
    AutomaticTemperaturePointCalculation,
    TemperatureCalculationError,
    TemperaturePointUncertaintyInput,
    calculate_automatic_temperature_point,
)


class TemperatureCalculationServiceError(ValueError):
    """Raised when a temperature calculation run cannot be controlled."""


@dataclass(frozen=True, slots=True)
class TemperatureCalculationRun:
    summaries: tuple[MeasurementPointSummary, ...]
    calculation_audit_event_id: int
    calculation_audit_event: AuditEvent
    workflow_audit_event_id: int
    workflow_audit_event: AuditEvent


def calculate_temperature_measurement_points_for_session(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    job_id: str,
    uncertainty_inputs: tuple[TemperaturePointUncertaintyInput, ...],
    software_version: str,
    calculation_engine_version: str,
    constant_set_version: str,
    budget_version: str,
    timestamp: datetime,
) -> TemperatureCalculationRun:
    """Calculate temperature points after resolving an authenticated actor."""
    actor = resolve_actor_for_action(
        connection=connection,
        session_id=session_id,
        action=Action.RUN_CALCULATION,
        timestamp=timestamp,
    )
    return calculate_temperature_measurement_points(
        connection=connection,
        job_id=job_id,
        uncertainty_inputs=uncertainty_inputs,
        user_id=actor.user_id,
        software_version=software_version,
        calculation_engine_version=calculation_engine_version,
        constant_set_version=constant_set_version,
        budget_version=budget_version,
        timestamp=timestamp,
    )


def calculate_temperature_measurement_points(
    *,
    connection: sqlite3.Connection,
    job_id: str,
    uncertainty_inputs: tuple[TemperaturePointUncertaintyInput, ...],
    user_id: str,
    software_version: str,
    calculation_engine_version: str,
    constant_set_version: str,
    budget_version: str,
    timestamp: datetime,
) -> TemperatureCalculationRun:
    """Calculate and persist all planned automatic temperature points for a job."""
    _validate_service_inputs(
        job_id=job_id,
        uncertainty_inputs=uncertainty_inputs,
        user_id=user_id,
        software_version=software_version,
        calculation_engine_version=calculation_engine_version,
        constant_set_version=constant_set_version,
        budget_version=budget_version,
        timestamp=timestamp,
    )

    with connection:
        job_repository = SQLiteCalibrationJobRepository(connection, autocommit=False)
        dut_repository = SQLiteDeviceUnderTestRepository(connection, autocommit=False)
        setpoint_repository = SQLiteRequiredTemperatureSetpointRepository(
            connection,
            autocommit=False,
        )
        window_repository = SQLiteMeasurementWindowRepository(
            connection,
            autocommit=False,
        )
        linked_repository = SQLiteLinkedTemperatureReadingRepository(
            connection,
            autocommit=False,
        )
        summary_repository = SQLiteMeasurementPointSummaryRepository(
            connection,
            autocommit=False,
        )
        constant_repository = SQLiteConstantSetRepository(connection, autocommit=False)
        budget_repository = SQLiteUncertaintyBudgetRepository(
            connection,
            autocommit=False,
        )
        audit_repository = SQLiteAuditEventRepository(connection, autocommit=False)

        job = job_repository.get(job_id)
        if job.state is not WorkflowState.WINDOWS_SELECTED:
            raise TemperatureCalculationServiceError(
                "Temperature calculation requires windows_selected state."
            )
        _require_approved_versions(
            constant_repository=constant_repository,
            budget_repository=budget_repository,
            constant_set_version=constant_set_version,
            budget_version=budget_version,
        )

        duts = dut_repository.list_for_job(job_id)
        required_setpoints = setpoint_repository.list_for_job(job_id)
        windows = window_repository.list_for_job(job_id)
        linked_readings = linked_repository.list_for_job(job_id)
        input_by_setpoint = _uncertainty_inputs_by_setpoint(uncertainty_inputs)

        calculations = _calculate_all_windows(
            job_id=job_id,
            duts={dut.id: dut.channel_id for dut in duts},
            required_setpoints=tuple(
                (setpoint.setpoint, setpoint.unit) for setpoint in required_setpoints
            ),
            windows=windows,
            linked_readings=linked_readings,
            input_by_setpoint=input_by_setpoint,
            calculation_engine_version=calculation_engine_version,
            constant_set_version=constant_set_version,
            budget_version=budget_version,
        )
        summaries = tuple(calculation.summary for calculation in calculations)
        for summary in summaries:
            summary_repository.add(summary)

        calculation_audit_event = _calculation_audit_event(
            job_id=job_id,
            calculations=calculations,
            user_id=user_id,
            software_version=software_version,
            calculation_engine_version=calculation_engine_version,
            constant_set_version=constant_set_version,
            budget_version=budget_version,
            timestamp=timestamp,
        )
        calculation_audit_event_id = audit_repository.append(calculation_audit_event)

        transition = transition_calibration_job(
            job_id=job_id,
            current=job.state,
            target=WorkflowState.CALCULATED,
            user_id=user_id,
            software_version=software_version,
            timestamp=timestamp,
        )
        job_repository.update_state(
            job_id=job_id,
            expected_state=job.state,
            new_state=transition.state,
        )
        workflow_audit_event_id = audit_repository.append(transition.audit_event)

    return TemperatureCalculationRun(
        summaries=summaries,
        calculation_audit_event_id=calculation_audit_event_id,
        calculation_audit_event=calculation_audit_event,
        workflow_audit_event_id=workflow_audit_event_id,
        workflow_audit_event=transition.audit_event,
    )


def _calculate_all_windows(
    *,
    job_id: str,
    duts: dict[str, str | None],
    required_setpoints: tuple[tuple[float, str], ...],
    windows: tuple[MeasurementWindow, ...],
    linked_readings: tuple[LinkedTemperatureReading, ...],
    input_by_setpoint: dict[tuple[float, str], TemperaturePointUncertaintyInput],
    calculation_engine_version: str,
    constant_set_version: str,
    budget_version: str,
) -> tuple[AutomaticTemperaturePointCalculation, ...]:
    if not duts:
        raise TemperatureCalculationServiceError(
            "Temperature calculation requires at least one DUT."
        )
    if not required_setpoints:
        raise TemperatureCalculationServiceError(
            "Temperature calculation requires at least one required setpoint."
        )
    missing_inputs = tuple(
        setpoint for setpoint in required_setpoints if setpoint not in input_by_setpoint
    )
    if missing_inputs:
        missing = ", ".join(f"{setpoint:g} {unit}" for setpoint, unit in missing_inputs)
        raise TemperatureCalculationServiceError(
            f"Missing uncertainty inputs for required setpoints: {missing}."
        )

    windows_by_coverage = _windows_by_coverage(windows)
    calculations: list[AutomaticTemperaturePointCalculation] = []
    for dut_id, channel_id in duts.items():
        if channel_id is None:
            raise TemperatureCalculationServiceError(
                f"DUT {dut_id} is missing a channel id for automatic calculation."
            )
        for setpoint, unit in required_setpoints:
            window = windows_by_coverage.get((dut_id, setpoint, unit))
            if window is None:
                raise TemperatureCalculationServiceError(
                    "Temperature calculation requires selected windows for all "
                    f"DUT/setpoint pairs; missing {dut_id}@{setpoint:g} {unit}."
                )
            linked_window_readings = _linked_readings_for_window(
                window,
                linked_readings,
            )
            try:
                calculation = calculate_automatic_temperature_point(
                    point_id=f"{job_id}-{window.id}-summary",
                    job_id=job_id,
                    dut_id=dut_id,
                    measurement_window_id=window.id,
                    reference_values=tuple(
                        linked.reference.value for linked in linked_window_readings
                    ),
                    indication_values=tuple(
                        linked.indication.value for linked in linked_window_readings
                    ),
                    uncertainty_input=input_by_setpoint[(setpoint, unit)],
                    calculation_engine_version=calculation_engine_version,
                    constant_set_version=constant_set_version,
                    budget_version=budget_version,
                )
            except TemperatureCalculationError as exc:
                raise TemperatureCalculationServiceError(str(exc)) from exc
            calculations.append(calculation)
    return tuple(calculations)


def _windows_by_coverage(
    windows: tuple[MeasurementWindow, ...],
) -> dict[tuple[str, float, str], MeasurementWindow]:
    windows_by_coverage: dict[tuple[str, float, str], MeasurementWindow] = {}
    for window in windows:
        key = (window.dut_id, window.setpoint, window.unit)
        if key in windows_by_coverage:
            dut_id, setpoint, unit = key
            raise TemperatureCalculationServiceError(
                "Temperature calculation cannot choose between duplicate selected "
                f"windows for {dut_id}@{setpoint:g} {unit}."
            )
        windows_by_coverage[key] = window
    return windows_by_coverage


def _linked_readings_for_window(
    window: MeasurementWindow,
    linked_readings: tuple[LinkedTemperatureReading, ...],
) -> tuple[LinkedTemperatureReading, ...]:
    selected: list[LinkedTemperatureReading] = []
    for reading in window.readings:
        matches = [
            linked
            for linked in linked_readings
            if linked.timestamp == reading.timestamp
            and linked.dut_channel_id == window.channel_id
            and linked.indication.unit == window.unit
            and linked.reference.unit == window.unit
            and linked.indication.source.uploaded_file_id
            == reading.source.uploaded_file_id
            and linked.indication.source.source_label == reading.source.source_label
            and linked.indication.source.row_number == reading.source.row_number
            and linked.indication.source.column_label == reading.source.column_label
        ]
        if len(matches) != 1:
            raise TemperatureCalculationServiceError(
                "Selected temperature window reading does not have exactly one "
                "linked IRTD reference."
            )
        selected.append(matches[0])
    return tuple(selected)


def _uncertainty_inputs_by_setpoint(
    uncertainty_inputs: tuple[TemperaturePointUncertaintyInput, ...],
) -> dict[tuple[float, str], TemperaturePointUncertaintyInput]:
    inputs_by_setpoint: dict[tuple[float, str], TemperaturePointUncertaintyInput] = {}
    for uncertainty_input in uncertainty_inputs:
        key = (uncertainty_input.setpoint, uncertainty_input.unit)
        if key in inputs_by_setpoint:
            setpoint, unit = key
            raise TemperatureCalculationServiceError(
                f"Duplicate uncertainty inputs for setpoint {setpoint:g} {unit}."
            )
        inputs_by_setpoint[key] = uncertainty_input
    return inputs_by_setpoint


def _require_approved_versions(
    *,
    constant_repository: SQLiteConstantSetRepository,
    budget_repository: SQLiteUncertaintyBudgetRepository,
    constant_set_version: str,
    budget_version: str,
) -> None:
    constant_set = None
    budget = None
    try:
        constant_set = constant_repository.get(constant_set_version)
    except RecordNotFoundError:
        pass
    try:
        budget = budget_repository.get(budget_version)
    except RecordNotFoundError:
        pass
    blockers = release_version_blockers(constant_set, budget)
    if blockers:
        raise TemperatureCalculationServiceError(
            "Temperature calculation requires approved matching constant and budget "
            f"versions; blockers: {', '.join(blockers)}."
        )


def _calculation_audit_event(
    *,
    job_id: str,
    calculations: tuple[AutomaticTemperaturePointCalculation, ...],
    user_id: str,
    software_version: str,
    calculation_engine_version: str,
    constant_set_version: str,
    budget_version: str,
    timestamp: datetime,
) -> AuditEvent:
    return AuditEvent(
        entity_type="calibration_job",
        entity_id=job_id,
        action=AuditAction.CALCULATION_RUN,
        user_id=user_id,
        timestamp=timestamp,
        new_value={
            "summary_ids": [
                calculation.summary.point_id for calculation in calculations
            ],
            "point_count": len(calculations),
            "points": [
                _calculation_to_audit_value(calculation)
                for calculation in calculations
            ],
        },
        software_version=software_version,
        calculation_engine_version=calculation_engine_version,
        constant_set_version=constant_set_version,
        budget_version=budget_version,
    )


def _calculation_to_audit_value(
    calculation: AutomaticTemperaturePointCalculation,
) -> dict[str, object]:
    summary = calculation.summary
    return {
        "point_id": summary.point_id,
        "dut_id": summary.dut_id,
        "measurement_window_id": summary.measurement_window_id,
        "reference": summary.reference,
        "indication": summary.indication,
        "error_of_indication": summary.error_of_indication,
        "calculated_expanded_uncertainty": _decimal_to_text(
            calculation.calculated_expanded_uncertainty
        ),
        "cmc_floor": _decimal_to_text(summary.cmc_floor),
        "reported_expanded_uncertainty": _decimal_to_text(
            summary.reported_expanded_uncertainty
        ),
        "display_error_of_indication": _decimal_to_text(
            summary.display_error_of_indication
        ),
        "combined_standard_uncertainty": calculation.combined_standard_uncertainty,
        "contributions": [
            {
                "name": contribution.name,
                "standard_uncertainty": contribution.standard_uncertainty,
                "sensitivity_coefficient": contribution.sensitivity_coefficient,
                "effective_standard_uncertainty": (
                    contribution.effective_standard_uncertainty
                ),
            }
            for contribution in calculation.contributions
        ],
    }


def _validate_service_inputs(
    *,
    job_id: str,
    uncertainty_inputs: tuple[TemperaturePointUncertaintyInput, ...],
    user_id: str,
    software_version: str,
    calculation_engine_version: str,
    constant_set_version: str,
    budget_version: str,
    timestamp: datetime,
) -> None:
    _require_text(job_id, "Job id")
    if len(uncertainty_inputs) == 0:
        raise TemperatureCalculationServiceError(
            "Temperature calculation requires uncertainty inputs."
        )
    _require_text(user_id, "User id")
    _require_text(software_version, "Software version")
    _require_text(calculation_engine_version, "Calculation engine version")
    _require_text(constant_set_version, "Constant set version")
    _require_text(budget_version, "Budget version")
    _require_timezone_aware(timestamp, "Calculation timestamp")


def _decimal_to_text(value: Decimal) -> str:
    return format(value, "f")


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise TemperatureCalculationServiceError(f"{field_name} is required.")


def _require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise TemperatureCalculationServiceError(f"{field_name} must be timezone-aware.")
