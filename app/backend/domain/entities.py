"""Core immutable domain entities for the P1 calibration foundation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from math import isfinite
import re

from app.backend.domain.workflow import WorkflowState


class DomainValidationError(ValueError):
    """Raised when a domain object would be incomplete or non-traceable."""


class Discipline(StrEnum):
    TEMPERATURE = "temperature"
    PRESSURE = "pressure"


class MeasurementMode(StrEnum):
    MANUAL = "manual"
    AUTOMATIC = "automatic"


class UploadedFileKind(StrEnum):
    CALIBRATION_XLSX = "calibration_xlsx"
    VERIFICATION_PDF = "verification_pdf"
    CERTIFICATE_REFERENCE_PDF = "certificate_reference_pdf"
    OTHER = "other"


_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise DomainValidationError(f"{field_name} is required.")


def _require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise DomainValidationError(f"{field_name} must be timezone-aware.")


def _require_instance(value: object, expected_type: type, field_name: str) -> None:
    if not isinstance(value, expected_type):
        raise DomainValidationError(f"{field_name} is invalid.")


@dataclass(frozen=True, slots=True)
class Client:
    name: str
    address: str

    def __post_init__(self) -> None:
        _require_text(self.name, "Client name")
        _require_text(self.address, "Client address")


@dataclass(frozen=True, slots=True)
class CalibrationJob:
    id: str
    client: Client
    discipline: Discipline
    measurement_mode: MeasurementMode
    method: str
    created_by: str
    state: WorkflowState = WorkflowState.DRAFT
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        _require_text(self.id, "Calibration job id")
        _require_instance(self.discipline, Discipline, "Calibration job discipline")
        _require_instance(
            self.measurement_mode,
            MeasurementMode,
            "Calibration job measurement mode",
        )
        _require_instance(self.state, WorkflowState, "Calibration job state")
        _require_text(self.method, "Calibration method")
        _require_text(self.created_by, "Created by user id")
        _require_timezone_aware(self.created_at, "Calibration job created_at")


@dataclass(frozen=True, slots=True)
class UploadedFile:
    id: str
    job_id: str
    original_filename: str
    checksum_sha256: str
    file_kind: UploadedFileKind
    storage_uri: str
    parser_version: str | None = None
    uploaded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        _require_text(self.id, "Uploaded file id")
        _require_text(self.job_id, "Uploaded file job id")
        _require_text(self.original_filename, "Uploaded file original filename")
        _require_text(self.storage_uri, "Uploaded file storage URI")
        _require_instance(self.file_kind, UploadedFileKind, "Uploaded file kind")
        if not _SHA256_PATTERN.fullmatch(self.checksum_sha256):
            raise DomainValidationError("Uploaded file checksum must be a SHA-256 hex digest.")
        if self.parser_version is not None:
            _require_text(self.parser_version, "Uploaded file parser version")
        _require_timezone_aware(self.uploaded_at, "Uploaded file uploaded_at")
        object.__setattr__(self, "checksum_sha256", self.checksum_sha256.lower())


@dataclass(frozen=True, slots=True)
class DeviceUnderTest:
    id: str
    job_id: str
    make: str
    model: str
    serial_number: str
    channel_id: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.id, "DUT id")
        _require_text(self.job_id, "DUT job id")
        _require_text(self.make, "DUT make")
        _require_text(self.model, "DUT model")
        _require_text(self.serial_number, "DUT serial number")
        if self.channel_id is not None:
            _require_text(self.channel_id, "DUT channel id")

    @property
    def identity_key(self) -> tuple[str, str, str | None]:
        return (self.job_id, self.serial_number, self.channel_id)


@dataclass(frozen=True, slots=True)
class SourceLocation:
    uploaded_file_id: str
    source_label: str
    row_number: int | None = None
    column_label: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.uploaded_file_id, "Source uploaded file id")
        _require_text(self.source_label, "Source label")
        if self.row_number is not None and self.row_number < 1:
            raise DomainValidationError("Source row number must be positive.")
        if self.column_label is not None:
            _require_text(self.column_label, "Source column label")


@dataclass(frozen=True, slots=True)
class MeasurementReading:
    timestamp: datetime
    channel_id: str
    value: float
    unit: str
    source: SourceLocation
    quality_flag: str | None = None

    def __post_init__(self) -> None:
        _require_timezone_aware(self.timestamp, "Reading timestamp")
        _require_text(self.channel_id, "Reading channel id")
        _require_text(self.unit, "Reading unit")
        if not isfinite(self.value):
            raise DomainValidationError("Reading value must be finite.")
        if self.quality_flag is not None:
            _require_text(self.quality_flag, "Reading quality flag")


@dataclass(frozen=True, slots=True)
class LinkedTemperatureReading:
    timestamp: datetime
    dut_channel_id: str
    reference: MeasurementReading
    indication: MeasurementReading

    def __post_init__(self) -> None:
        _require_timezone_aware(self.timestamp, "Linked temperature reading timestamp")
        _require_text(self.dut_channel_id, "Linked temperature reading DUT channel id")
        _require_instance(
            self.reference,
            MeasurementReading,
            "Linked temperature reference reading",
        )
        _require_instance(
            self.indication,
            MeasurementReading,
            "Linked temperature indication reading",
        )
        if self.reference.timestamp != self.timestamp:
            raise DomainValidationError(
                "Linked temperature reference timestamp must match link timestamp."
            )
        if self.indication.timestamp != self.timestamp:
            raise DomainValidationError(
                "Linked temperature indication timestamp must match link timestamp."
            )
        if self.indication.channel_id != self.dut_channel_id:
            raise DomainValidationError(
                "Linked temperature indication channel must match DUT channel id."
            )
        if self.reference.unit != self.indication.unit:
            raise DomainValidationError(
                "Linked temperature readings must use the same unit."
            )


@dataclass(frozen=True, slots=True)
class RequiredTemperatureSetpoint:
    id: str
    job_id: str
    setpoint: float
    unit: str
    sequence_index: int
    created_by: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        _require_text(self.id, "Required temperature setpoint id")
        _require_text(self.job_id, "Required temperature setpoint job id")
        _require_text(self.unit, "Required temperature setpoint unit")
        _require_text(self.created_by, "Required temperature setpoint created_by")
        _require_timezone_aware(
            self.created_at,
            "Required temperature setpoint created_at",
        )
        if not isfinite(self.setpoint):
            raise DomainValidationError(
                "Required temperature setpoint must be finite."
            )
        if self.sequence_index < 0:
            raise DomainValidationError(
                "Required temperature setpoint sequence index cannot be negative."
            )

    @property
    def coverage_key(self) -> tuple[float, str]:
        return (self.setpoint, self.unit)


@dataclass(frozen=True, slots=True)
class MeasurementWindow:
    id: str
    job_id: str
    dut_id: str
    setpoint: float
    unit: str
    selected_by: str
    readings: tuple[MeasurementReading, ...]
    selected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        _require_text(self.id, "Measurement window id")
        _require_text(self.job_id, "Measurement window job id")
        _require_text(self.dut_id, "Measurement window DUT id")
        _require_text(self.unit, "Measurement window unit")
        _require_text(self.selected_by, "Measurement window selected_by")
        _require_timezone_aware(self.selected_at, "Measurement window selected_at")
        if not isfinite(self.setpoint):
            raise DomainValidationError("Measurement window setpoint must be finite.")
        if len(self.readings) == 0:
            raise DomainValidationError("Measurement window requires at least one reading.")

        channels = {reading.channel_id for reading in self.readings}
        if len(channels) != 1:
            raise DomainValidationError("Measurement window readings must use one channel.")
        units = {reading.unit for reading in self.readings}
        if units != {self.unit}:
            raise DomainValidationError("Measurement window readings must match window unit.")
        timestamps = [reading.timestamp for reading in self.readings]
        if timestamps != sorted(timestamps):
            raise DomainValidationError("Measurement window readings must be chronological.")

    @property
    def channel_id(self) -> str:
        return self.readings[0].channel_id

    @property
    def reading_count(self) -> int:
        return len(self.readings)

    @property
    def start_timestamp(self) -> datetime:
        return self.readings[0].timestamp

    @property
    def end_timestamp(self) -> datetime:
        return self.readings[-1].timestamp
