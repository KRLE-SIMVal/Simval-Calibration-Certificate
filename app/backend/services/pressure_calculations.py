"""Pressure calculation orchestration services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import sqlite3

from app.backend.audit.events import AuditAction, AuditEvent
from app.backend.auth.permissions import Action
from app.backend.domain.entities import Discipline, MeasurementMode
from app.backend.domain.versioning import release_version_blockers
from app.backend.domain.workflow import WorkflowState
from app.backend.persistence.sqlite import (
    RecordNotFoundError,
    SQLiteAuditEventRepository,
    SQLiteCalibrationJobRepository,
    SQLiteConstantSetRepository,
    SQLiteDeviceUnderTestRepository,
    SQLiteMeasurementPointSummaryRepository,
    SQLiteMeasurementWindowRepository,
    SQLiteUncertaintyBudgetRepository,
)
from app.backend.services.authentication import resolve_actor_for_action
from app.backend.services.workflow import transition_calibration_job
from app.calculation_engine.pressure.results import (
    PressureCalculationError,
    PressureKind,
    PressurePointCalculation,
    PressurePointUncertaintyInput,
    calculate_automatic_pressure_point,
    calculate_manual_pressure_point,
)


class PressureCalculationServiceError(ValueError):
    """Raised when a pressure calculation run cannot be controlled."""


@dataclass(frozen=True, slots=True)
class ManualPressurePointInput:
    point_id: str
    dut_id: str
    measurement_window_id: str
    pressure_kind: PressureKind
    reference_pressure: float
    indication_values: tuple[float, ...]
    uncertainty_input: PressurePointUncertaintyInput


@dataclass(frozen=True, slots=True)
class AutomaticPressurePointInput:
    point_id: str
    dut_id: str
    measurement_window_id: str
    pressure_kind: PressureKind
    reference_values: tuple[float, ...]
    indication_values: tuple[float, ...]
    uncertainty_input: PressurePointUncertaintyInput


@dataclass(frozen=True, slots=True)
class CalculatedPressurePoint:
    calculation_type: str
    pressure_kind: PressureKind
    calculation: PressurePointCalculation


@dataclass(frozen=True, slots=True)
class PressureCalculationRun:
    points: tuple[CalculatedPressurePoint, ...]
    calculation_audit_event_id: int
    calculation_audit_event: AuditEvent
    workflow_audit_event_id: int
    workflow_audit_event: AuditEvent


def calculate_pressure_measurement_points_for_session(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    job_id: str,
    manual_points: tuple[ManualPressurePointInput, ...],
    automatic_points: tuple[AutomaticPressurePointInput, ...],
    software_version: str,
    calculation_engine_version: str,
    constant_set_version: str,
    budget_version: str,
    timestamp: datetime,
) -> PressureCalculationRun:
    """Calculate pressure points after resolving an authenticated actor."""
    actor = resolve_actor_for_action(
        connection=connection,
        session_id=session_id,
        action=Action.RUN_CALCULATION,
        timestamp=timestamp,
    )
    return calculate_pressure_measurement_points(
        connection=connection,
        job_id=job_id,
        manual_points=manual_points,
        automatic_points=automatic_points,
        user_id=actor.user_id,
        software_version=software_version,
        calculation_engine_version=calculation_engine_version,
        constant_set_version=constant_set_version,
        budget_version=budget_version,
        timestamp=timestamp,
    )


def calculate_pressure_measurement_points(
    *,
    connection: sqlite3.Connection,
    job_id: str,
    manual_points: tuple[ManualPressurePointInput, ...],
    automatic_points: tuple[AutomaticPressurePointInput, ...],
    user_id: str,
    software_version: str,
    calculation_engine_version: str,
    constant_set_version: str,
    budget_version: str,
    timestamp: datetime,
) -> PressureCalculationRun:
    """Calculate, persist, audit, and transition one pressure job."""
    _validate_service_inputs(
        job_id=job_id,
        manual_points=manual_points,
        automatic_points=automatic_points,
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
        window_repository = SQLiteMeasurementWindowRepository(
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
        if job.discipline is not Discipline.PRESSURE:
            raise PressureCalculationServiceError(
                "Pressure calculation requires pressure discipline."
            )
        if job.state is not WorkflowState.WINDOWS_SELECTED:
            raise PressureCalculationServiceError(
                "Pressure calculation requires windows_selected state."
            )
        _require_mode_matches_points(
            job_mode=job.measurement_mode,
            manual_points=manual_points,
            automatic_points=automatic_points,
        )
        _require_approved_pressure_versions(
            constant_repository=constant_repository,
            budget_repository=budget_repository,
            constant_set_version=constant_set_version,
            budget_version=budget_version,
        )

        calculations = _calculate_points(
            job_id=job_id,
            manual_points=manual_points,
            automatic_points=automatic_points,
            dut_repository=dut_repository,
            window_repository=window_repository,
            calculation_engine_version=calculation_engine_version,
            constant_set_version=constant_set_version,
            budget_version=budget_version,
        )
        for calculation in calculations:
            summary_repository.add(calculation.calculation.summary)

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

    return PressureCalculationRun(
        points=calculations,
        calculation_audit_event_id=calculation_audit_event_id,
        calculation_audit_event=calculation_audit_event,
        workflow_audit_event_id=workflow_audit_event_id,
        workflow_audit_event=transition.audit_event,
    )


def _calculate_points(
    *,
    job_id: str,
    manual_points: tuple[ManualPressurePointInput, ...],
    automatic_points: tuple[AutomaticPressurePointInput, ...],
    dut_repository: SQLiteDeviceUnderTestRepository,
    window_repository: SQLiteMeasurementWindowRepository,
    calculation_engine_version: str,
    constant_set_version: str,
    budget_version: str,
) -> tuple[CalculatedPressurePoint, ...]:
    calculations: list[CalculatedPressurePoint] = []
    for point in manual_points:
        _require_point_traceability(
            job_id=job_id,
            dut_id=point.dut_id,
            measurement_window_id=point.measurement_window_id,
            dut_repository=dut_repository,
            window_repository=window_repository,
        )
        try:
            calculation = calculate_manual_pressure_point(
                point_id=point.point_id,
                job_id=job_id,
                dut_id=point.dut_id,
                measurement_window_id=point.measurement_window_id,
                reference_pressure=point.reference_pressure,
                indication_values=point.indication_values,
                uncertainty_input=point.uncertainty_input,
                calculation_engine_version=calculation_engine_version,
                constant_set_version=constant_set_version,
                budget_version=budget_version,
            )
        except PressureCalculationError as exc:
            raise PressureCalculationServiceError(str(exc)) from exc
        calculations.append(
            CalculatedPressurePoint(
                calculation_type="manual",
                pressure_kind=point.pressure_kind,
                calculation=calculation,
            )
        )
    for point in automatic_points:
        _require_point_traceability(
            job_id=job_id,
            dut_id=point.dut_id,
            measurement_window_id=point.measurement_window_id,
            dut_repository=dut_repository,
            window_repository=window_repository,
        )
        try:
            calculation = calculate_automatic_pressure_point(
                point_id=point.point_id,
                job_id=job_id,
                dut_id=point.dut_id,
                measurement_window_id=point.measurement_window_id,
                reference_values=point.reference_values,
                indication_values=point.indication_values,
                uncertainty_input=point.uncertainty_input,
                calculation_engine_version=calculation_engine_version,
                constant_set_version=constant_set_version,
                budget_version=budget_version,
            )
        except PressureCalculationError as exc:
            raise PressureCalculationServiceError(str(exc)) from exc
        calculations.append(
            CalculatedPressurePoint(
                calculation_type="automatic",
                pressure_kind=point.pressure_kind,
                calculation=calculation,
            )
        )
    return tuple(calculations)


def _require_point_traceability(
    *,
    job_id: str,
    dut_id: str,
    measurement_window_id: str,
    dut_repository: SQLiteDeviceUnderTestRepository,
    window_repository: SQLiteMeasurementWindowRepository,
) -> None:
    try:
        dut = dut_repository.get(dut_id)
    except RecordNotFoundError as exc:
        raise PressureCalculationServiceError(
            f"Pressure calculation DUT {dut_id!r} was not found."
        ) from exc
    if dut.job_id != job_id:
        raise PressureCalculationServiceError(
            "Pressure calculation DUT must belong to the selected job."
        )
    try:
        window = window_repository.get(measurement_window_id)
    except RecordNotFoundError as exc:
        raise PressureCalculationServiceError(
            "Pressure calculation requires a selected measurement window."
        ) from exc
    if window.job_id != job_id or window.dut_id != dut_id:
        raise PressureCalculationServiceError(
            "Pressure calculation window must belong to the selected job and DUT."
        )


def _require_mode_matches_points(
    *,
    job_mode: MeasurementMode,
    manual_points: tuple[ManualPressurePointInput, ...],
    automatic_points: tuple[AutomaticPressurePointInput, ...],
) -> None:
    if job_mode is MeasurementMode.MANUAL and automatic_points:
        raise PressureCalculationServiceError(
            "A manual pressure job cannot run automatic pressure points."
        )
    if job_mode is MeasurementMode.AUTOMATIC and manual_points:
        raise PressureCalculationServiceError(
            "An automatic pressure job cannot run manual pressure points."
        )


def _require_approved_pressure_versions(
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
    if constant_set is not None and constant_set.discipline is not Discipline.PRESSURE:
        blockers = (*blockers, "constant_budget_version_mismatch")
    if budget is not None and budget.discipline is not Discipline.PRESSURE:
        blockers = (*blockers, "constant_budget_version_mismatch")
    if blockers:
        raise PressureCalculationServiceError(
            "Pressure calculation requires approved matching pressure constant and "
            f"budget versions; blockers: {', '.join(dict.fromkeys(blockers))}."
        )


def _calculation_audit_event(
    *,
    job_id: str,
    calculations: tuple[CalculatedPressurePoint, ...],
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
            "discipline": Discipline.PRESSURE.value,
            "summary_ids": [
                calculation.calculation.summary.point_id
                for calculation in calculations
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
    calculation: CalculatedPressurePoint,
) -> dict[str, object]:
    summary = calculation.calculation.summary
    return {
        "point_id": summary.point_id,
        "dut_id": summary.dut_id,
        "measurement_window_id": summary.measurement_window_id,
        "calculation_type": calculation.calculation_type,
        "pressure_kind": calculation.pressure_kind.value,
        "reference": summary.reference,
        "indication": summary.indication,
        "error_of_indication": summary.error_of_indication,
        "calculated_expanded_uncertainty": _decimal_to_text(
            calculation.calculation.calculated_expanded_uncertainty
        ),
        "cmc_floor": _decimal_to_text(summary.cmc_floor),
        "reported_expanded_uncertainty": _decimal_to_text(
            summary.reported_expanded_uncertainty
        ),
        "display_error_of_indication": _decimal_to_text(
            summary.display_error_of_indication
        ),
        "combined_standard_uncertainty": (
            calculation.calculation.combined_standard_uncertainty
        ),
        "contributions": [
            {
                "name": contribution.name,
                "standard_uncertainty": contribution.standard_uncertainty,
                "sensitivity_coefficient": contribution.sensitivity_coefficient,
                "effective_standard_uncertainty": (
                    contribution.effective_standard_uncertainty
                ),
            }
            for contribution in calculation.calculation.contributions
        ],
    }


def _validate_service_inputs(
    *,
    job_id: str,
    manual_points: tuple[ManualPressurePointInput, ...],
    automatic_points: tuple[AutomaticPressurePointInput, ...],
    user_id: str,
    software_version: str,
    calculation_engine_version: str,
    constant_set_version: str,
    budget_version: str,
    timestamp: datetime,
) -> None:
    _require_text(job_id, "Job id")
    if len(manual_points) + len(automatic_points) == 0:
        raise PressureCalculationServiceError(
            "Pressure calculation requires at least one point."
        )
    point_ids = [
        point.point_id
        for point in (*manual_points, *automatic_points)
    ]
    if len(point_ids) != len(set(point_ids)):
        raise PressureCalculationServiceError(
            "Pressure calculation point ids must be unique."
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
        raise PressureCalculationServiceError(f"{field_name} is required.")


def _require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise PressureCalculationServiceError(f"{field_name} must be timezone-aware.")
