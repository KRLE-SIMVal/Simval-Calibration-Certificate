"""Automatic pressure source-import services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sqlite3

from app.backend.audit.events import AuditAction, AuditEvent
from app.backend.auth.permissions import Action
from app.backend.domain.entities import (
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
from app.backend.imports.pressure_csv import (
    ParsedPressureCsv,
    PressureCsvParseError,
    parse_pressure_csv,
)
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


class PressureAutomaticEntryServiceError(ValueError):
    """Raised when automatic pressure import cannot become controlled data."""


@dataclass(frozen=True, slots=True)
class AutomaticPressureEntry:
    job_id: str
    state: WorkflowState
    dut_id: str
    window_id: str
    parser_version: str
    reference_values: tuple[float, ...]
    indication_values: tuple[float, ...]
    reference_reading_count: int
    indication_reading_count: int
    warnings: tuple[str, ...]
    parser_audit_event_id: int
    parser_audit_event: AuditEvent
    job_parser_audit_event_id: int
    job_parser_audit_event: AuditEvent
    data_entry_audit_event_id: int
    data_entry_audit_event: AuditEvent
    data_entry_workflow_audit_event_id: int
    data_entry_workflow_audit_event: AuditEvent
    alignment_audit_event_id: int
    alignment_audit_event: AuditEvent
    window_audit_event_id: int
    window_audit_event: AuditEvent
    window_workflow_audit_event_id: int
    window_workflow_audit_event: AuditEvent


def record_automatic_pressure_entry_for_session(
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
    parser_version: str,
    artifact_directory: Path,
    software_version: str,
    timestamp: datetime,
) -> AutomaticPressureEntry:
    """Parse uploaded pressure CSV evidence and record automatic readings."""
    actor = resolve_actor_for_action(
        connection=connection,
        session_id=session_id,
        action=Action.UPLOAD_IMPORT_FILE,
        timestamp=timestamp,
    )
    return record_automatic_pressure_entry(
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
        parser_version=parser_version,
        artifact_directory=artifact_directory,
        recorded_by=actor.user_id,
        software_version=software_version,
        timestamp=timestamp,
    )


def record_automatic_pressure_entry(
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
    parser_version: str,
    artifact_directory: Path,
    recorded_by: str,
    software_version: str,
    timestamp: datetime,
) -> AutomaticPressureEntry:
    """Create pressure DUT/window evidence from an automatic pressure CSV import."""
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
        parser_version=parser_version,
        recorded_by=recorded_by,
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
            raise PressureAutomaticEntryServiceError(
                "Automatic pressure entry requires pressure discipline."
            )
        if job.measurement_mode is not MeasurementMode.AUTOMATIC:
            raise PressureAutomaticEntryServiceError(
                "Automatic pressure entry requires automatic pressure mode."
            )
        if job.state is not WorkflowState.EQUIPMENT_SELECTED:
            raise PressureAutomaticEntryServiceError(
                "Automatic pressure entry requires equipment_selected state."
            )
        try:
            uploaded_file = uploaded_file_repository.get(uploaded_file_id)
        except RecordNotFoundError as exc:
            raise PressureAutomaticEntryServiceError(
                "Automatic pressure entry uploaded evidence file was not found."
            ) from exc
        if uploaded_file.job_id != job_id:
            raise PressureAutomaticEntryServiceError(
                "Automatic pressure entry evidence file must belong to the selected job."
            )
        if uploaded_file.file_kind is not UploadedFileKind.OTHER:
            raise PressureAutomaticEntryServiceError(
                "Automatic pressure entry requires an uploaded OTHER CSV source file."
            )
        if not uploaded_file.original_filename.lower().endswith(".csv"):
            raise PressureAutomaticEntryServiceError(
                "Automatic pressure entry requires a CSV source file."
            )
        if dut_repository.list_for_job(job_id):
            raise PressureAutomaticEntryServiceError(
                "DUT records already exist for this pressure job."
            )
        if window_repository.list_for_job(job_id):
            raise PressureAutomaticEntryServiceError(
                "Measurement windows already exist for this pressure job."
            )

        parsed = _parse_uploaded_pressure_csv(
            uploaded_file=uploaded_file,
            artifact_directory=artifact_directory,
            parser_version=parser_version,
        )
        _require_csv_units_match(parsed=parsed, unit=unit)

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
            selected_by=recorded_by,
            selected_at=timestamp,
            readings=tuple(
                MeasurementReading(
                    timestamp=reading.timestamp,
                    channel_id=dut_channel_id,
                    value=reading.indication_value,
                    unit=unit,
                    source=SourceLocation(
                        uploaded_file_id=uploaded_file.id,
                        source_label=parsed.schema_name,
                        row_number=reading.row_number,
                        column_label="indication",
                    ),
                )
                for reading in parsed.readings
            ),
        )
        dut_repository.add(dut)

        parser_event = _parser_audit_event(
            uploaded_file=uploaded_file,
            parsed=parsed,
            user_id=recorded_by,
            software_version=software_version,
            timestamp=timestamp,
        )
        parser_audit_event_id = audit_repository.append(parser_event)
        job_parser_event = _job_parser_audit_event(
            uploaded_file=uploaded_file,
            parsed=parsed,
            user_id=recorded_by,
            software_version=software_version,
            timestamp=timestamp,
        )
        job_parser_audit_event_id = audit_repository.append(job_parser_event)

        data_entry_event = _data_entry_audit_event(
            job_id=job_id,
            uploaded_file_id=uploaded_file.id,
            dut=dut,
            parsed=parsed,
            user_id=recorded_by,
            software_version=software_version,
            timestamp=timestamp,
        )
        data_entry_audit_event_id = audit_repository.append(data_entry_event)
        data_entry_transition = transition_calibration_job(
            job_id=job_id,
            current=job.state,
            target=WorkflowState.DATA_ENTERED,
            user_id=recorded_by,
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

        alignment_event = _alignment_audit_event(
            window=window,
            uploaded_file_id=uploaded_file.id,
            parsed=parsed,
            user_id=recorded_by,
            software_version=software_version,
            timestamp=timestamp,
        )
        alignment_audit_event_id = audit_repository.append(alignment_event)
        window_repository.add(window)
        window_event = _window_audit_event(
            window=window,
            user_id=recorded_by,
            software_version=software_version,
            timestamp=timestamp,
        )
        window_audit_event_id = audit_repository.append(window_event)
        window_transition = transition_calibration_job(
            job_id=job_id,
            current=WorkflowState.DATA_ENTERED,
            target=WorkflowState.WINDOWS_SELECTED,
            user_id=recorded_by,
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

    return AutomaticPressureEntry(
        job_id=job_id,
        state=updated_job.state,
        dut_id=dut.id,
        window_id=window.id,
        parser_version=parsed.parser_version,
        reference_values=tuple(reading.reference_value for reading in parsed.readings),
        indication_values=tuple(reading.indication_value for reading in parsed.readings),
        reference_reading_count=len(parsed.readings),
        indication_reading_count=window.reading_count,
        warnings=parsed.warnings,
        parser_audit_event_id=parser_audit_event_id,
        parser_audit_event=parser_event,
        job_parser_audit_event_id=job_parser_audit_event_id,
        job_parser_audit_event=job_parser_event,
        data_entry_audit_event_id=data_entry_audit_event_id,
        data_entry_audit_event=data_entry_event,
        data_entry_workflow_audit_event_id=data_entry_workflow_audit_event_id,
        data_entry_workflow_audit_event=data_entry_transition.audit_event,
        alignment_audit_event_id=alignment_audit_event_id,
        alignment_audit_event=alignment_event,
        window_audit_event_id=window_audit_event_id,
        window_audit_event=window_event,
        window_workflow_audit_event_id=window_workflow_audit_event_id,
        window_workflow_audit_event=window_transition.audit_event,
    )


def _parse_uploaded_pressure_csv(
    *,
    uploaded_file: UploadedFile,
    artifact_directory: Path,
    parser_version: str,
) -> ParsedPressureCsv:
    path = _controlled_local_upload_path(
        uploaded_file=uploaded_file,
        artifact_directory=artifact_directory,
    )
    try:
        content_bytes = path.read_bytes()
    except OSError as exc:
        raise PressureAutomaticEntryServiceError(
            "Automatic pressure CSV source file could not be read."
        ) from exc
    try:
        return parse_pressure_csv(
            content_bytes,
            parser_version=parser_version,
        )
    except PressureCsvParseError as exc:
        raise PressureAutomaticEntryServiceError(str(exc)) from exc


def _controlled_local_upload_path(
    *,
    uploaded_file: UploadedFile,
    artifact_directory: Path,
) -> Path:
    prefix = "controlled-local://"
    if not uploaded_file.storage_uri.startswith(prefix):
        raise PressureAutomaticEntryServiceError(
            "Automatic pressure CSV must use controlled local storage."
        )
    relative = uploaded_file.storage_uri[len(prefix) :]
    if relative.strip() == "":
        raise PressureAutomaticEntryServiceError(
            "Automatic pressure CSV storage URI is incomplete."
        )
    base = artifact_directory.resolve()
    candidate = (base / relative).resolve()
    if base != candidate and base not in candidate.parents:
        raise PressureAutomaticEntryServiceError(
            "Automatic pressure CSV path must stay within artifact storage."
        )
    return candidate


def _parser_audit_event(
    *,
    uploaded_file: UploadedFile,
    parsed: ParsedPressureCsv,
    user_id: str,
    software_version: str,
    timestamp: datetime,
) -> AuditEvent:
    return AuditEvent(
        entity_type="uploaded_file",
        entity_id=uploaded_file.id,
        action=AuditAction.PARSER_RESULT_RECORDED,
        user_id=user_id,
        timestamp=timestamp,
        new_value=_parser_value(uploaded_file=uploaded_file, parsed=parsed),
        software_version=software_version,
    )


def _job_parser_audit_event(
    *,
    uploaded_file: UploadedFile,
    parsed: ParsedPressureCsv,
    user_id: str,
    software_version: str,
    timestamp: datetime,
) -> AuditEvent:
    return AuditEvent(
        entity_type="calibration_job",
        entity_id=uploaded_file.job_id,
        action=AuditAction.PARSER_RESULT_RECORDED,
        user_id=user_id,
        timestamp=timestamp,
        new_value=_parser_value(uploaded_file=uploaded_file, parsed=parsed),
        software_version=software_version,
    )


def _parser_value(
    *,
    uploaded_file: UploadedFile,
    parsed: ParsedPressureCsv,
) -> dict[str, object]:
    return {
        "uploaded_file_id": uploaded_file.id,
        "parser_status": "parsed",
        "parser_version": parsed.parser_version,
        "schema_name": parsed.schema_name,
        "reading_count": len(parsed.readings) * 2,
        "warning_count": len(parsed.warnings),
    }


def _data_entry_audit_event(
    *,
    job_id: str,
    uploaded_file_id: str,
    dut: DeviceUnderTest,
    parsed: ParsedPressureCsv,
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
            "measurement_mode": MeasurementMode.AUTOMATIC.value,
            "uploaded_file_id": uploaded_file_id,
            "parser_version": parsed.parser_version,
            "schema_name": parsed.schema_name,
            "dut_ids": [dut.id],
            "channels": [dut.channel_id],
            "reference_reading_count": len(parsed.readings),
            "indication_reading_count": len(parsed.readings),
        },
        software_version=software_version,
    )


def _alignment_audit_event(
    *,
    window: MeasurementWindow,
    uploaded_file_id: str,
    parsed: ParsedPressureCsv,
    user_id: str,
    software_version: str,
    timestamp: datetime,
) -> AuditEvent:
    return AuditEvent(
        entity_type="measurement_window",
        entity_id=window.id,
        action=AuditAction.IMPORT_ALIGNMENT_RECORDED,
        user_id=user_id,
        timestamp=timestamp,
        new_value={
            "job_id": window.job_id,
            "dut_id": window.dut_id,
            "uploaded_file_id": uploaded_file_id,
            "parser_version": parsed.parser_version,
            "schema_name": parsed.schema_name,
            "reference_reading_count": len(parsed.readings),
            "indication_reading_count": window.reading_count,
            "readings": [
                {
                    "timestamp": reading.timestamp.isoformat(),
                    "reference_value": reading.reference_value,
                    "indication_value": reading.indication_value,
                    "unit": window.unit,
                    "source_label": parsed.schema_name,
                    "row_number": reading.row_number,
                    "reference_column_label": "reference",
                    "indication_column_label": "indication",
                }
                for reading in parsed.readings
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


def _require_csv_units_match(*, parsed: ParsedPressureCsv, unit: str) -> None:
    csv_units = {reading.unit for reading in parsed.readings if reading.unit is not None}
    if len(csv_units) > 1:
        raise PressureAutomaticEntryServiceError(
            "Automatic pressure CSV must use one pressure unit."
        )
    if csv_units and next(iter(csv_units)) != unit:
        raise PressureAutomaticEntryServiceError(
            "Automatic pressure CSV unit must match the requested pressure unit."
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
    parser_version: str,
    recorded_by: str,
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
    _require_text(parser_version, "Parser version")
    _require_text(recorded_by, "Recorded by")
    _require_text(software_version, "Software version")
    _require_timezone_aware(timestamp, "Automatic pressure entry timestamp")


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise PressureAutomaticEntryServiceError(f"{field_name} is required.")


def _require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise PressureAutomaticEntryServiceError(
            f"{field_name} must be timezone-aware."
        )
