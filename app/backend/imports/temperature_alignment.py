"""Alignment helpers for parsed temperature logger and IRTD readings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.backend.domain.entities import MeasurementReading


class TemperatureAlignmentError(ValueError):
    """Raised when parsed readings cannot be linked without ambiguity."""


@dataclass(frozen=True, slots=True)
class LinkedTemperatureReading:
    timestamp: datetime
    dut_channel_id: str
    reference: MeasurementReading
    indication: MeasurementReading


@dataclass(frozen=True, slots=True)
class TemperatureAlignmentResult:
    linked_readings: tuple[LinkedTemperatureReading, ...]
    warnings: tuple[str, ...]


def link_logger_readings_to_irtd(
    *,
    logger_readings: tuple[MeasurementReading, ...],
    irtd_readings: tuple[MeasurementReading, ...],
) -> TemperatureAlignmentResult:
    """Link each logger reading to an IRTD reference reading at the same timestamp."""
    irtd_by_timestamp = _index_irtd_readings(irtd_readings)
    linked: list[LinkedTemperatureReading] = []
    warnings: list[str] = []

    for logger_reading in logger_readings:
        reference = irtd_by_timestamp.get(logger_reading.timestamp)
        timestamp_text = logger_reading.timestamp.isoformat()
        if reference is None:
            warnings.append(
                "Missing IRTD reference for logger channel "
                f"{logger_reading.channel_id} at {timestamp_text}."
            )
            continue
        if logger_reading.unit != reference.unit:
            warnings.append(
                "Unit mismatch for logger channel "
                f"{logger_reading.channel_id} at {timestamp_text}: "
                f"logger {logger_reading.unit}, IRTD {reference.unit}."
            )
            continue
        linked.append(
            LinkedTemperatureReading(
                timestamp=logger_reading.timestamp,
                dut_channel_id=logger_reading.channel_id,
                reference=reference,
                indication=logger_reading,
            )
        )

    return TemperatureAlignmentResult(
        linked_readings=tuple(linked),
        warnings=tuple(warnings),
    )


def _index_irtd_readings(
    readings: tuple[MeasurementReading, ...],
) -> dict[datetime, MeasurementReading]:
    indexed: dict[datetime, MeasurementReading] = {}
    for reading in readings:
        if reading.timestamp in indexed:
            raise TemperatureAlignmentError(
                f"Duplicate IRTD reference timestamp {reading.timestamp.isoformat()}."
            )
        indexed[reading.timestamp] = reading
    return indexed
