"""Manual pressure data-entry services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import sqlite3

from app.backend.audit.events import AuditAction, AuditEvent
from app.backend.auth.permissions import Action
from app.backend.domain.entities import (
    DeviceUnderTest,
    Discipline,
    MeasurementReading,
    MeasurementWindow,
    SourceLocation,
)
from app.backend.domain.workflow import WorkflowState
from app.backend.persistence.sqlite import (
    RecordNotFoundError,
    SQLiteAuditEventRepository,
    SQLiteCalibrationJobRepository,
    SQLiteDeviceUnderTestRepository,
    SQLiteMeasurementWindowRepository,
    SQLiteUploadedFileRepository,
)
from app.backend.services.authentication import resolve_actor_for_action
from app.backend.services.workflow import transition_calibration_job


class PressureManualEntryServiceError(ValueError):
    """Raised when manual pressure data entry cannot be controlled."""


@dataclass(frozen=True, slots=True)
class ManualPressureReadingInput:
    timestamp: datetime
    value: float
    source_label: str
    row_number: int | None = None
    column_label: str | None = None


@dataclass(frozen=True, slots=True)
class ManualPressureEntry:
    job_id: str
    state: WorkflowState
    dut_id: str
    window_id: str
    reading_count: int
    data_entry_audit_event_id: int
    data_entry_audit_event: AuditEvent
    data_entry_workflow_audit_event_id: int
    data_entry_workflow_audit_event: AuditEvent
    manual_reading_audit_event_id: int
    manual_reading_audit_event: AuditEvent
    window_audit_event_id: int
    window_audit_event: AuditEvent
    window_workflow_audit_event_id: int
    window_workflow_audit_event: AuditEvent


def record_manual_pressure_entry_for_session(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    job_id: str,
    uploaded_file_id: str,
    dut_id: str,
    dut_make: str,
    dut_model: str,
    dut_serial_number: str,
    dut_channel_id: str,
    window_id: str,
    setpoint: float,
    unit: str,
    readings: tuple[ManualPressureReadingInput, ...],
    software_version: str,
    timestamp: datetime,
) -> ManualPressureEntry:
    """Record manual pressure readings after resolving an authenticated actor."""
    actor = resolve_actor_for_action(
        connection=connection,
        session_id=session_id,
        action=Action.ENTER_MANUAL_READINGS,
        timestamp=timestamp,
    )
    return record_manual_pressure_entry(
        connection=connection,
        job_id=job_id,
        uploaded_file_id=uploaded_file_id,
        dut_id=dut_id,
        dut_make=dut_make,
        dut_model=dut_model,
        dut_serial_number=dut_serial_number,
        dut_channel_id=dut_channel_id,
        window_id=window_id,
        setpoint=setpoint,
        unit=unit,
        readings=readings,
        entered_by=actor.user_id,
        software_version=software_version,
        timestamp=timestamp,
    )


def record_manual_pressure_entry(
    *,
    connection: sqlite3.Connection,
    job_id: str,
    uploaded_file_id: str,
    dut_id: str,
    dut_make: str,
    dut_model: str,
    dut_serial_number: str,
    dut_channel_id: str,
    window_id: str,
    setpoint: float,
    unit: str,
    readings: tuple[ManualPressureReadingInput, ...],
    entered_by: str,
    software_version: str,
    timestamp: datetime,
) -> ManualPressureEntry:
    """Create pressure DUT/window evidence from manual transcription."""
    _validate_inputs(
        job_id=job_id,
        uploaded_file_id=uploaded_file_id,
        dut_id=dut_id,
        dut_make=dut_make,
        dut_model=dut_model,
        dut_serial_number=dut_serial_number,
        dut_channel_id=dut_channel_id,
        window_id=window_id,
        unit=unit,
        readings=readings,
        entered_by=entered_by,
        software_version=software_version,
        timestamp=timestamp,
    )

    with connection:
        job_repository = SQLiteCalibrationJobRepository(connection, autocommit=False)
        uploaded_file_repository = SQLiteUploadedFileRepository(
            connection,
            autocommit=False,
        )
        dut_repository = SQLiteDeviceUnderTestRepository(connection, autocommit=False)
        window_repository = SQLiteMeasurementWindowRepository(
            connection,
            autocommit=False,
        )
        audit_repository = SQLiteAuditEventRepository(connection, autocommit=False)

        job = job_repository.get(job_id)
        if job.discipline is not Discipline.PRESSURE:
            raise PressureManualEntryServiceError(
                "Manual pressure entry requires pressure discipline."
            )
        if job.state is not WorkflowState.EQUIPMENT_SELECTED:
            raise PressureManualEntryServiceError(
                "Manual pressure entry requires equipment_selected state."
            )
        try:
            uploaded_file = uploaded_file_repository.get(uploaded_file_id)
        except RecordNotFoundError as exc:
            raise PressureManualEntryServiceError(
                "Manual pressure entry uploaded evidence file was not found."
            ) from exc
        if uploaded_file.job_id != job_id:
            raise PressureManualEntryServiceError(
                "Manual pressure entry evidence file must belong to the selected job."
            )
        if dut_repository.list_for_job(job_id):
            raise PressureManualEntryServiceError(
                "DUT records already exist for this pressure job."
            )
        if window_repository.list_for_job(job_id):
            raise PressureManualEntryServiceError(
                "Measurement windows already exist for this pressure job."
            )

        dut = DeviceUnderTest(
            id=dut_id,
            job_id=job_id,
            make=dut_make,
            model=dut_model,
            serial_number=dut_serial_number,
            channel_id=dut_channel_id,
        )
        window = MeasurementWindow(
            id=window_id,
            job_id=job_id,
            dut_id=dut.id,
            setpoint=setpoint,
            unit=unit,
            selected_by=entered_by,
            selected_at=timestamp,
            readings=tuple(
                MeasurementReading(
                    timestamp=reading.timestamp,
                    channel_id=dut_channel_id,
                    value=reading.value,
                    unit=unit,
                    source=SourceLocation(
                        uploaded_file_id=uploaded_file.id,
                        source_label=reading.source_label,
                        row_number=reading.row_number,
                        column_label=reading.column_label,
                    ),
                )
                for reading in readings
            ),
        )

        dut_repository.add(dut)
        data_entry_event = _data_entry_audit_event(
            job_id=job_id,
            uploaded_file_id=uploaded_file.id,
            dut=dut,
            user_id=entered_by,
            software_version=software_version,
            timestamp=timestamp,
        )
        data_entry_audit_event_id = audit_repository.append(data_entry_event)
        data_entry_transition = transition_calibration_job(
            job_id=job_id,
            current=job.state,
            target=WorkflowState.DATA_ENTERED,
            user_id=entered_by,
            software_version=software_version,
            timestamp=timestamp,
        )
        job_repository.update_state(
            job_id=job_id,
            expected_state=job.state,
            new_state=data_entry_transition.state,
        )
        data_entry_workflow_audit_event_id = audit_repository.append(
            data_entry_transition.audit_event
        )

        manual_reading_event = _manual_reading_audit_event(
            window=window,
            uploaded_file_id=uploaded_file.id,
            user_id=entered_by,
            software_version=software_version,
            timestamp=timestamp,
        )
        manual_reading_audit_event_id = audit_repository.append(manual_reading_event)
        window_repository.add(window)
        window_event = _window_audit_event(
            window=window,
            user_id=entered_by,
            software_version=software_version,
            timestamp=timestamp,
        )
        window_audit_event_id = audit_repository.append(window_event)

        window_transition = transition_calibration_job(
            job_id=job_id,
            current=WorkflowState.DATA_ENTERED,
            target=WorkflowState.WINDOWS_SELECTED,
            user_id=entered_by,
            software_version=software_version,
            timestamp=timestamp,
        )
        updated_job = job_repository.update_state(
            job_id=job_id,
            expected_state=WorkflowState.DATA_ENTERED,
            new_state=window_transition.state,
        )
        window_workflow_audit_event_id = audit_repository.append(
            window_transition.audit_event
        )

    return ManualPressureEntry(
        job_id=job_id,
        state=updated_job.state,
        dut_id=dut.id,
        window_id=window.id,
        reading_count=window.reading_count,
        data_entry_audit_event_id=data_entry_audit_event_id,
        data_entry_audit_event=data_entry_event,
        data_entry_workflow_audit_event_id=data_entry_workflow_audit_event_id,
        data_entry_workflow_audit_event=data_entry_transition.audit_event,
        manual_reading_audit_event_id=manual_reading_audit_event_id,
        manual_reading_audit_event=manual_reading_event,
        window_audit_event_id=window_audit_event_id,
        window_audit_event=window_event,
        window_workflow_audit_event_id=window_workflow_audit_event_id,
        window_workflow_audit_event=window_transition.audit_event,
    )


def _data_entry_audit_event(
    *,
    job_id: str,
    uploaded_file_id: str,
    dut: DeviceUnderTest,
    user_id: str,
    software_version: str,
    timestamp: datetime,
) -> AuditEvent:
    return AuditEvent(
        entity_type="calibration_job",
        entity_id=job_id,
        action=AuditAction.DATA_ENTRY_RECORDED,
        user_id=user_id,
        timestamp=timestamp,
        new_value={
            "discipline": Discipline.PRESSURE.value,
            "uploaded_file_id": uploaded_file_id,
            "dut_ids": [dut.id],
            "channels": [dut.channel_id],
        },
        software_version=software_version,
    )


def _manual_reading_audit_event(
    *,
    window: MeasurementWindow,
    uploaded_file_id: str,
    user_id: str,
    software_version: str,
    timestamp: datetime,
) -> AuditEvent:
    return AuditEvent(
        entity_type="measurement_window",
        entity_id=window.id,
        action=AuditAction.MANUAL_READING_CHANGED,
        user_id=user_id,
        timestamp=timestamp,
        new_value={
            "job_id": window.job_id,
            "dut_id": window.dut_id,
            "uploaded_file_id": uploaded_file_id,
            "reading_count": window.reading_count,
            "readings": [
                {
                    "timestamp": reading.timestamp.isoformat(),
                    "value": reading.value,
                    "unit": reading.unit,
                    "source_label": reading.source.source_label,
                    "row_number": reading.source.row_number,
                    "column_label": reading.source.column_label,
                }
                for reading in window.readings
            ],
        },
        software_version=software_version,
    )


def _window_audit_event(
    *,
    window: MeasurementWindow,
    user_id: str,
    software_version: str,
    timestamp: datetime,
) -> AuditEvent:
    return AuditEvent(
        entity_type="measurement_window",
        entity_id=window.id,
        action=AuditAction.MEASUREMENT_WINDOW_CHANGED,
        user_id=user_id,
        timestamp=timestamp,
        new_value={
            "job_id": window.job_id,
            "dut_id": window.dut_id,
            "setpoint": window.setpoint,
            "unit": window.unit,
            "start_timestamp": window.start_timestamp.isoformat(),
            "end_timestamp": window.end_timestamp.isoformat(),
            "reading_count": window.reading_count,
        },
        software_version=software_version,
    )


def _validate_inputs(
    *,
    job_id: str,
    uploaded_file_id: str,
    dut_id: str,
    dut_make: str,
    dut_model: str,
    dut_serial_number: str,
    dut_channel_id: str,
    window_id: str,
    unit: str,
    readings: tuple[ManualPressureReadingInput, ...],
    entered_by: str,
    software_version: str,
    timestamp: datetime,
) -> None:
    _require_text(job_id, "Job id")
    _require_text(uploaded_file_id, "Uploaded file id")
    _require_text(dut_id, "DUT id")
    _require_text(dut_make, "DUT make")
    _require_text(dut_model, "DUT model")
    _require_text(dut_serial_number, "DUT serial number")
    _require_text(dut_channel_id, "DUT channel id")
    _require_text(window_id, "Window id")
    _require_text(unit, "Pressure unit")
    _require_text(entered_by, "Entered by")
    _require_text(software_version, "Software version")
    _require_timezone_aware(timestamp, "Manual pressure entry timestamp")
    if len(readings) == 0:
        raise PressureManualEntryServiceError(
            "Manual pressure entry requires at least one reading."
        )
    for reading in readings:
        _require_timezone_aware(reading.timestamp, "Manual pressure reading timestamp")
        _require_text(reading.source_label, "Manual pressure reading source label")


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise PressureManualEntryServiceError(f"{field_name} is required.")


def _require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise PressureManualEntryServiceError(f"{field_name} must be timezone-aware.")
