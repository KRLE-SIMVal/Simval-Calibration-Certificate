"""Data-entry preparation services after source-file import."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
import sqlite3

from app.backend.audit.events import AuditAction, AuditEvent
from app.backend.auth.permissions import Action
from app.backend.domain.entities import (
    DeviceUnderTest,
    RequiredTemperatureSetpoint,
    UploadedFileKind,
)
from app.backend.domain.workflow import WorkflowState
from app.backend.persistence.sqlite import (
    RecordNotFoundError,
    SQLiteAuditEventRepository,
    SQLiteCalibrationJobRepository,
    SQLiteDeviceUnderTestRepository,
    SQLiteParsedReadingRepository,
    SQLiteRequiredTemperatureSetpointRepository,
    SQLiteUploadedFileRepository,
)
from app.backend.services.authentication import resolve_actor_for_action
from app.backend.services.workflow import transition_calibration_job


class DataEntryServiceError(ValueError):
    """Raised when imported data cannot become controlled job data."""


@dataclass(frozen=True, slots=True)
class TemperatureDataEntryPreparation:
    job_id: str
    state: WorkflowState
    dut_ids: tuple[str, ...]
    setpoint_ids: tuple[str, ...]
    data_entry_audit_event_id: int
    data_entry_audit_event: AuditEvent
    workflow_audit_event_id: int
    workflow_audit_event: AuditEvent


def prepare_temperature_data_entry_for_session(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    job_id: str,
    calibration_uploaded_file_id: str,
    setpoints: tuple[float, ...],
    unit: str,
    software_version: str,
    timestamp: datetime,
) -> TemperatureDataEntryPreparation:
    """Create DUTs/setpoint plan from parsed import and move to data_entered."""
    actor = resolve_actor_for_action(
        connection=connection,
        session_id=session_id,
        action=Action.UPLOAD_IMPORT_FILE,
        timestamp=timestamp,
    )
    _require_text(job_id, "Job id")
    _require_text(calibration_uploaded_file_id, "Calibration uploaded file id")
    _require_text(unit, "Temperature unit")
    _require_text(software_version, "Software version")
    _require_timezone_aware(timestamp, "Data-entry timestamp")
    if len(setpoints) == 0:
        raise DataEntryServiceError("At least one required setpoint is required.")

    with connection:
        job_repository = SQLiteCalibrationJobRepository(connection, autocommit=False)
        uploaded_file_repository = SQLiteUploadedFileRepository(
            connection,
            autocommit=False,
        )
        parsed_reading_repository = SQLiteParsedReadingRepository(
            connection,
            autocommit=False,
        )
        dut_repository = SQLiteDeviceUnderTestRepository(connection, autocommit=False)
        setpoint_repository = SQLiteRequiredTemperatureSetpointRepository(
            connection,
            autocommit=False,
        )
        audit_repository = SQLiteAuditEventRepository(connection, autocommit=False)

        job = job_repository.get(job_id)
        if job.state is not WorkflowState.EQUIPMENT_SELECTED:
            raise DataEntryServiceError(
                "Temperature data entry requires equipment_selected state."
            )
        try:
            uploaded_file = uploaded_file_repository.get(calibration_uploaded_file_id)
        except RecordNotFoundError as exc:
            raise DataEntryServiceError("Calibration uploaded file was not found.") from exc
        if uploaded_file.job_id != job_id:
            raise DataEntryServiceError(
                "Calibration uploaded file must belong to the selected job."
            )
        if uploaded_file.file_kind is not UploadedFileKind.CALIBRATION_XLSX:
            raise DataEntryServiceError("Temperature data entry requires calibration XLSX.")

        readings = parsed_reading_repository.list_for_uploaded_file(uploaded_file.id)
        if len(readings) == 0:
            raise DataEntryServiceError(
                "Temperature data entry requires parsed calibration readings."
            )
        channels = tuple(sorted({reading.channel_id for reading in readings}))
        if len(channels) == 0:
            raise DataEntryServiceError(
                "Temperature data entry requires at least one logger channel."
            )
        safe_channel_ids = tuple(_safe_id(channel) for channel in channels)
        if len(set(safe_channel_ids)) != len(safe_channel_ids):
            raise DataEntryServiceError(
                "Logger channel IDs must produce unique controlled DUT IDs."
            )
        if dut_repository.list_for_job(job_id):
            raise DataEntryServiceError("DUT records already exist for this job.")
        if setpoint_repository.list_for_job(job_id):
            raise DataEntryServiceError(
                "Required temperature setpoints already exist for this job."
            )

        duts = tuple(
            DeviceUnderTest(
                id=f"dut-{safe_channel_id}",
                job_id=job_id,
                make="Kaye",
                model="ValProbe RT",
                serial_number=channel,
                channel_id=channel,
            )
            for channel, safe_channel_id in zip(channels, safe_channel_ids, strict=True)
        )
        for dut in duts:
            dut_repository.add(dut)

        planned_setpoints = tuple(
            RequiredTemperatureSetpoint(
                id=f"setpoint-{index + 1:03d}",
                job_id=job_id,
                setpoint=setpoint,
                unit=unit,
                sequence_index=index,
                created_by=actor.user_id,
                created_at=timestamp,
            )
            for index, setpoint in enumerate(setpoints)
        )
        setpoint_repository.add_many(planned_setpoints)

        data_entry_audit_event = AuditEvent(
            entity_type="calibration_job",
            entity_id=job_id,
            action=AuditAction.DATA_ENTRY_RECORDED,
            user_id=actor.user_id,
            timestamp=timestamp,
            new_value={
                "calibration_uploaded_file_id": uploaded_file.id,
                "dut_ids": [dut.id for dut in duts],
                "channels": list(channels),
                "setpoints": [
                    {"setpoint": setpoint.setpoint, "unit": setpoint.unit}
                    for setpoint in planned_setpoints
                ],
            },
            software_version=software_version,
        )
        data_entry_audit_event_id = audit_repository.append(data_entry_audit_event)

        transition = transition_calibration_job(
            job_id=job_id,
            current=job.state,
            target=WorkflowState.DATA_ENTERED,
            user_id=actor.user_id,
            software_version=software_version,
            timestamp=timestamp,
        )
        updated_job = job_repository.update_state(
            job_id=job_id,
            expected_state=job.state,
            new_state=transition.state,
        )
        workflow_audit_event_id = audit_repository.append(transition.audit_event)

    return TemperatureDataEntryPreparation(
        job_id=job_id,
        state=updated_job.state,
        dut_ids=tuple(dut.id for dut in duts),
        setpoint_ids=tuple(setpoint.id for setpoint in planned_setpoints),
        data_entry_audit_event_id=data_entry_audit_event_id,
        data_entry_audit_event=data_entry_audit_event,
        workflow_audit_event_id=workflow_audit_event_id,
        workflow_audit_event=transition.audit_event,
    )


def _safe_id(value: str) -> str:
    candidate = re.sub(r"[^A-Za-z0-9._-]", "_", value).strip("._")
    if candidate == "":
        raise DataEntryServiceError("Channel id cannot produce a safe DUT id.")
    return candidate


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise DataEntryServiceError(f"{field_name} is required.")


def _require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise DataEntryServiceError(f"{field_name} must be timezone-aware.")
