from datetime import datetime, timezone

import pytest

from app.backend.domain.entities import MeasurementReading, SourceLocation
from app.backend.imports.temperature_alignment import (
    TemperatureAlignmentError,
    link_logger_readings_to_irtd,
)


def test_link_logger_readings_to_irtd_by_timestamp_for_each_channel():
    first_time = datetime(2026, 4, 8, 15, 45, tzinfo=timezone.utc)
    second_time = datetime(2026, 4, 8, 15, 46, tzinfo=timezone.utc)
    logger_readings = (
        _logger_reading(first_time, "MJT1-A", -80.036, row_number=12),
        _logger_reading(first_time, "NWU2-A", -80.041, row_number=12),
        _logger_reading(second_time, "MJT1-A", -80.034, row_number=13),
    )
    irtd_readings = (
        _irtd_reading(first_time, -80.031, row_number=2),
        _irtd_reading(second_time, -80.030, row_number=3),
    )

    result = link_logger_readings_to_irtd(
        logger_readings=logger_readings,
        irtd_readings=irtd_readings,
    )

    assert result.warnings == ()
    assert len(result.linked_readings) == 3
    assert result.linked_readings[0].dut_channel_id == "MJT1-A"
    assert result.linked_readings[0].reference.value == pytest.approx(-80.031)
    assert result.linked_readings[0].indication.value == pytest.approx(-80.036)
    assert result.linked_readings[1].dut_channel_id == "NWU2-A"
    assert result.linked_readings[2].timestamp == second_time


def test_link_logger_readings_warns_and_skips_missing_irtd_reference():
    timestamp = datetime(2026, 4, 8, 15, 45, tzinfo=timezone.utc)

    result = link_logger_readings_to_irtd(
        logger_readings=(_logger_reading(timestamp, "MJT1-A", -80.036, row_number=12),),
        irtd_readings=(),
    )

    assert result.linked_readings == ()
    assert result.warnings == (
        "Missing IRTD reference for logger channel MJT1-A at 2026-04-08T15:45:00+00:00.",
    )


def test_link_logger_readings_warns_and_skips_unit_mismatch():
    timestamp = datetime(2026, 4, 8, 15, 45, tzinfo=timezone.utc)

    result = link_logger_readings_to_irtd(
        logger_readings=(_logger_reading(timestamp, "MJT1-A", -80.036, row_number=12),),
        irtd_readings=(_irtd_reading(timestamp, 193.119, unit="K", row_number=2),),
    )

    assert result.linked_readings == ()
    assert result.warnings == (
        "Unit mismatch for logger channel MJT1-A at "
        "2026-04-08T15:45:00+00:00: logger deg C, IRTD K.",
    )


def test_link_logger_readings_rejects_duplicate_irtd_timestamp():
    timestamp = datetime(2026, 4, 8, 15, 45, tzinfo=timezone.utc)

    with pytest.raises(TemperatureAlignmentError):
        link_logger_readings_to_irtd(
            logger_readings=(
                _logger_reading(timestamp, "MJT1-A", -80.036, row_number=12),
            ),
            irtd_readings=(
                _irtd_reading(timestamp, -80.031, row_number=2),
                _irtd_reading(timestamp, -80.030, row_number=3),
            ),
        )


def _logger_reading(
    timestamp: datetime,
    channel_id: str,
    value: float,
    *,
    unit: str = "deg C",
    row_number: int,
) -> MeasurementReading:
    return MeasurementReading(
        timestamp=timestamp,
        channel_id=channel_id,
        value=value,
        unit=unit,
        source=SourceLocation(
            uploaded_file_id="calibration-xlsx-001",
            source_label="Temperature",
            row_number=row_number,
            column_label="B",
        ),
    )


def _irtd_reading(
    timestamp: datetime,
    value: float,
    *,
    unit: str = "deg C",
    row_number: int,
) -> MeasurementReading:
    return MeasurementReading(
        timestamp=timestamp,
        channel_id="IRTD",
        value=value,
        unit=unit,
        source=SourceLocation(
            uploaded_file_id="verification-pdf-001",
            source_label="Verification IRTD",
            row_number=row_number,
            column_label="IRTD (deg C)",
        ),
    )
