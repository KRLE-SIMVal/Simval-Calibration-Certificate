"""Measurement-window selection services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import sqlite3

from app.backend.audit.events import AuditAction, AuditEvent
from app.backend.domain.entities import (
    CalibrationJob,
    LinkedTemperatureReading,
    MeasurementWindow,
)
from app.backend.domain.workflow import WorkflowState
from app.backend.persistence.sqlite import (
    SQLiteAuditEventRepository,
    SQLiteCalibrationJobRepository,
    SQLiteDeviceUnderTestRepository,
    SQLiteLinkedTemperatureReadingRepository,
    SQLiteMeasurementWindowRepository,
    SQLiteRequiredTemperatureSetpointRepository,
)
from app.backend.services.workflow import transition_calibration_job


class MeasurementWindowSelectionError(ValueError):
    """Raised when a selected measurement window is incomplete or unsafe."""


@dataclass(frozen=True, slots=True)
class TemperatureMeasurementWindowSelection:
    window: MeasurementWindow
    linked_readings: tuple[LinkedTemperatureReading, ...]
    audit_event_id: int
    audit_event: AuditEvent


@dataclass(frozen=True, slots=True)
class TemperatureWindowCompletion:
    job: CalibrationJob
    audit_event_id: int
    audit_event: AuditEvent


def select_temperature_window_from_linked_readings(
    *,
    connection: sqlite3.Connection,
    window_id: str,
    job_id: str,
    dut_id: str,
    dut_channel_id: str,
    setpoint: float,
    unit: str,
    start_timestamp: datetime,
    end_timestamp: datetime,
    selected_by: str,
    software_version: str,
    timestamp: datetime,
) -> TemperatureMeasurementWindowSelection:
    """Persist a manual timestamp window from linked logger/IRTD readings."""
    _validate_selection_inputs(
        window_id=window_id,
        job_id=job_id,
        dut_id=dut_id,
        dut_channel_id=dut_channel_id,
        unit=unit,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        selected_by=selected_by,
        software_version=software_version,
        timestamp=timestamp,
    )

    with connection:
        job_repository = SQLiteCalibrationJobRepository(connection, autocommit=False)
        dut_repository = SQLiteDeviceUnderTestRepository(connection, autocommit=False)
        linked_repository = SQLiteLinkedTemperatureReadingRepository(
            connection,
            autocommit=False,
        )
        window_repository = SQLiteMeasurementWindowRepository(
            connection,
            autocommit=False,
        )
        audit_repository = SQLiteAuditEventRepository(connection, autocommit=False)

        job = job_repository.get(job_id)
        if job.state not in {WorkflowState.DATA_ENTERED, WorkflowState.WINDOWS_SELECTED}:
            raise MeasurementWindowSelectionError(
                "Temperature window selection requires data_entered or windows_selected state."
            )

        dut = dut_repository.get(dut_id)
        if dut.job_id != job_id:
            raise MeasurementWindowSelectionError(
                "Temperature window DUT must belong to the selected job."
            )
        if dut.channel_id != dut_channel_id:
            raise MeasurementWindowSelectionError(
                "Temperature window DUT channel must match the selected channel."
            )

        linked_readings = _select_linked_readings(
            linked_repository.list_for_job(job_id),
            dut_channel_id=dut_channel_id,
            unit=unit,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
        )
        if len(linked_readings) == 0:
            raise MeasurementWindowSelectionError(
                "Temperature window selection contains no linked readings."
            )

        window = MeasurementWindow(
            id=window_id,
            job_id=job_id,
            dut_id=dut_id,
            setpoint=setpoint,
            unit=unit,
            selected_by=selected_by,
            selected_at=timestamp,
            readings=tuple(link.indication for link in linked_readings),
        )
        audit_event = _selection_audit_event(
            window=window,
            dut_channel_id=dut_channel_id,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            linked_reading_count=len(linked_readings),
            selected_by=selected_by,
            software_version=software_version,
            timestamp=timestamp,
        )
        window_repository.add(window)
        audit_event_id = audit_repository.append(audit_event)

    return TemperatureMeasurementWindowSelection(
        window=window,
        linked_readings=linked_readings,
        audit_event_id=audit_event_id,
        audit_event=audit_event,
    )


def complete_temperature_window_selection(
    *,
    connection: sqlite3.Connection,
    job_id: str,
    user_id: str,
    software_version: str,
    timestamp: datetime,
) -> TemperatureWindowCompletion:
    """Move a job to windows_selected after each DUT has a selected window."""
    _require_text(job_id, "Job id")
    _require_text(user_id, "User id")
    _require_text(software_version, "Software version")
    _require_timezone_aware(timestamp, "Window completion timestamp")

    with connection:
        job_repository = SQLiteCalibrationJobRepository(connection, autocommit=False)
        dut_repository = SQLiteDeviceUnderTestRepository(connection, autocommit=False)
        window_repository = SQLiteMeasurementWindowRepository(
            connection,
            autocommit=False,
        )
        setpoint_repository = SQLiteRequiredTemperatureSetpointRepository(
            connection,
            autocommit=False,
        )
        audit_repository = SQLiteAuditEventRepository(connection, autocommit=False)

        job = job_repository.get(job_id)
        if job.state is not WorkflowState.DATA_ENTERED:
            raise MeasurementWindowSelectionError(
                "Temperature window completion requires data_entered state."
            )

        dut_ids = tuple(dut.id for dut in dut_repository.list_for_job(job_id))
        if len(dut_ids) == 0:
            raise MeasurementWindowSelectionError(
                "Temperature window completion requires at least one DUT."
            )

        required_setpoints = setpoint_repository.list_for_job(job_id)
        if len(required_setpoints) == 0:
            raise MeasurementWindowSelectionError(
                "Temperature window completion requires at least one required setpoint."
            )

        selected_windows = window_repository.list_for_job(job_id)
        selected_coverage = {
            (window.dut_id, window.setpoint, window.unit) for window in selected_windows
        }
        missing_coverage = tuple(
            (
                dut_id,
                required_setpoint.setpoint,
                required_setpoint.unit,
            )
            for dut_id in dut_ids
            for required_setpoint in required_setpoints
            if (
                dut_id,
                required_setpoint.setpoint,
                required_setpoint.unit,
            )
            not in selected_coverage
        )
        if missing_coverage:
            missing = ", ".join(
                f"{dut_id}@{setpoint:g} {unit}"
                for dut_id, setpoint, unit in missing_coverage
            )
            raise MeasurementWindowSelectionError(
                f"Missing selected measurement windows for required setpoints: {missing}."
            )

        transition = transition_calibration_job(
            job_id=job.id,
            current=job.state,
            target=WorkflowState.WINDOWS_SELECTED,
            user_id=user_id,
            software_version=software_version,
            timestamp=timestamp,
        )
        updated_job = job_repository.update_state(
            job_id=job.id,
            expected_state=job.state,
            new_state=transition.state,
        )
        audit_event_id = audit_repository.append(transition.audit_event)

    return TemperatureWindowCompletion(
        job=updated_job,
        audit_event_id=audit_event_id,
        audit_event=transition.audit_event,
    )


def _select_linked_readings(
    linked_readings: tuple[LinkedTemperatureReading, ...],
    *,
    dut_channel_id: str,
    unit: str,
    start_timestamp: datetime,
    end_timestamp: datetime,
) -> tuple[LinkedTemperatureReading, ...]:
    selected = [
        linked_reading
        for linked_reading in linked_readings
        if linked_reading.dut_channel_id == dut_channel_id
        and start_timestamp <= linked_reading.timestamp <= end_timestamp
        and linked_reading.indication.unit == unit
        and linked_reading.reference.unit == unit
    ]
    return tuple(sorted(selected, key=lambda linked_reading: linked_reading.timestamp))


def _selection_audit_event(
    *,
    window: MeasurementWindow,
    dut_channel_id: str,
    start_timestamp: datetime,
    end_timestamp: datetime,
    linked_reading_count: int,
    selected_by: str,
    software_version: str,
    timestamp: datetime,
) -> AuditEvent:
    return AuditEvent(
        entity_type="measurement_window",
        entity_id=window.id,
        action=AuditAction.MEASUREMENT_WINDOW_CHANGED,
        user_id=selected_by,
        timestamp=timestamp,
        new_value={
            "job_id": window.job_id,
            "dut_id": window.dut_id,
            "dut_channel_id": dut_channel_id,
            "setpoint": window.setpoint,
            "unit": window.unit,
            "start_timestamp": start_timestamp.isoformat(),
            "end_timestamp": end_timestamp.isoformat(),
            "linked_reading_count": linked_reading_count,
        },
        software_version=software_version,
    )


def _validate_selection_inputs(
    *,
    window_id: str,
    job_id: str,
    dut_id: str,
    dut_channel_id: str,
    unit: str,
    start_timestamp: datetime,
    end_timestamp: datetime,
    selected_by: str,
    software_version: str,
    timestamp: datetime,
) -> None:
    _require_text(window_id, "Window id")
    _require_text(job_id, "Job id")
    _require_text(dut_id, "DUT id")
    _require_text(dut_channel_id, "DUT channel id")
    _require_text(unit, "Window unit")
    _require_text(selected_by, "Selected by")
    _require_text(software_version, "Software version")
    _require_timezone_aware(start_timestamp, "Window start timestamp")
    _require_timezone_aware(end_timestamp, "Window end timestamp")
    _require_timezone_aware(timestamp, "Window selection timestamp")
    if end_timestamp < start_timestamp:
        raise MeasurementWindowSelectionError(
            "Window end timestamp must be at or after start timestamp."
        )


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise MeasurementWindowSelectionError(f"{field_name} is required.")


def _require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise MeasurementWindowSelectionError(f"{field_name} must be timezone-aware.")
