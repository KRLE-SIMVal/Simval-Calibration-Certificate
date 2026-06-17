from datetime import timezone

import pytest

from app.backend.imports.pressure_csv import (
    PressureCsvParseError,
    parse_pressure_csv,
)


def test_pressure_csv_parser_reads_known_paired_schema():
    parsed = parse_pressure_csv(
        (
            b"timestamp,reference,indication,unit\n"
            b"2026-06-01T14:21:00Z,10.002,10.006,bar\n"
            b"2026-06-01T14:20:00Z,10.000,10.004,bar\n"
        ),
        parser_version="pressure-csv-parser-v1",
    )

    assert parsed.schema_name == "simval-pressure-paired-csv-v1"
    assert parsed.warnings == ()
    assert [reading.row_number for reading in parsed.readings] == [3, 2]
    assert [reading.reference_value for reading in parsed.readings] == [10.0, 10.002]
    assert [reading.indication_value for reading in parsed.readings] == [10.004, 10.006]
    assert parsed.readings[0].timestamp.tzinfo is timezone.utc


def test_pressure_csv_parser_warns_and_skips_invalid_rows():
    parsed = parse_pressure_csv(
        (
            b"timestamp,reference,indication\n"
            b"missing,10.000,10.004\n"
            b"2026-06-01T14:20:00Z,10.000,10.004\n"
            b"2026-06-01T14:21:00Z,10.001,10.005\n"
        ),
        parser_version="pressure-csv-parser-v1",
    )

    assert parsed.warnings == (
        "Skipped row 2 in pressure CSV because timestamp is invalid.",
    )
    assert len(parsed.readings) == 2


def test_pressure_csv_parser_rejects_missing_required_columns():
    with pytest.raises(PressureCsvParseError) as exc_info:
        parse_pressure_csv(
            b"timestamp,indication\n2026-06-01T14:20:00Z,10.004\n",
            parser_version="pressure-csv-parser-v1",
        )

    assert "missing required columns: reference" in str(exc_info.value)


def test_pressure_csv_parser_requires_two_linked_readings():
    with pytest.raises(PressureCsvParseError) as exc_info:
        parse_pressure_csv(
            b"timestamp,reference,indication\n2026-06-01T14:20:00Z,10.000,10.004\n",
            parser_version="pressure-csv-parser-v1",
        )

    assert "at least two linked readings" in str(exc_info.value)


def test_pressure_csv_parser_rejects_naive_timestamps():
    with pytest.raises(PressureCsvParseError) as exc_info:
        parse_pressure_csv(
            (
                b"timestamp,reference,indication\n"
                b"2026-06-01T14:20:00,10.000,10.004\n"
                b"2026-06-01T14:21:00Z,10.001,10.005\n"
            ),
            parser_version="pressure-csv-parser-v1",
        )

    assert "at least two linked readings" in str(exc_info.value)
