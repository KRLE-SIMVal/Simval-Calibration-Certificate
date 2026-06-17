"""Known-schema pressure CSV parser for automatic pressure readings."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from math import isfinite


class PressureCsvParseError(ValueError):
    """Raised when a pressure CSV file cannot be parsed safely."""


@dataclass(frozen=True, slots=True)
class PressureCsvLinkedReading:
    timestamp: datetime
    reference_value: float
    indication_value: float
    row_number: int
    unit: str | None = None


@dataclass(frozen=True, slots=True)
class ParsedPressureCsv:
    parser_version: str
    schema_name: str
    readings: tuple[PressureCsvLinkedReading, ...]
    warnings: tuple[str, ...]


PRESSURE_CSV_SCHEMA_NAME = "simval-pressure-paired-csv-v1"
REQUIRED_COLUMNS = frozenset({"timestamp", "reference", "indication"})


def parse_pressure_csv(
    content_bytes: bytes,
    *,
    parser_version: str,
) -> ParsedPressureCsv:
    """Parse paired reference/DUT pressure readings from a controlled CSV file."""
    if parser_version.strip() == "":
        raise PressureCsvParseError("parser_version is required.")
    if len(content_bytes) == 0:
        raise PressureCsvParseError("Pressure CSV content is required.")
    if b"\x00" in content_bytes:
        raise PressureCsvParseError("Pressure CSV contains unsupported NUL bytes.")
    try:
        text = content_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise PressureCsvParseError("Pressure CSV must be UTF-8 encoded.") from exc

    reader = csv.DictReader(StringIO(text))
    if reader.fieldnames is None:
        raise PressureCsvParseError("Pressure CSV requires a header row.")
    fieldnames = {_normalize_header(field) for field in reader.fieldnames}
    missing = sorted(REQUIRED_COLUMNS.difference(fieldnames))
    if missing:
        raise PressureCsvParseError(
            "Pressure CSV is missing required columns: " + ", ".join(missing) + "."
        )

    readings: list[PressureCsvLinkedReading] = []
    warnings: list[str] = []
    for row_number, row in enumerate(reader, start=2):
        normalized = {
            _normalize_header(key): (value or "").strip()
            for key, value in row.items()
            if key is not None
        }
        if not any(normalized.values()):
            continue
        timestamp_text = normalized.get("timestamp", "")
        reference_text = normalized.get("reference", "")
        indication_text = normalized.get("indication", "")
        if timestamp_text == "":
            warnings.append(
                f"Skipped row {row_number} in pressure CSV because timestamp is missing."
            )
            continue
        try:
            timestamp = _parse_timestamp(timestamp_text)
        except ValueError:
            warnings.append(
                f"Skipped row {row_number} in pressure CSV because timestamp is invalid."
            )
            continue
        try:
            reference_value = _parse_finite_float(reference_text)
        except ValueError:
            warnings.append(
                f"Skipped row {row_number} in pressure CSV because reference is invalid."
            )
            continue
        try:
            indication_value = _parse_finite_float(indication_text)
        except ValueError:
            warnings.append(
                f"Skipped row {row_number} in pressure CSV because indication is invalid."
            )
            continue
        unit = normalized.get("unit") or None
        readings.append(
            PressureCsvLinkedReading(
                timestamp=timestamp,
                reference_value=reference_value,
                indication_value=indication_value,
                unit=unit,
                row_number=row_number,
            )
        )

    if len(readings) < 2:
        raise PressureCsvParseError(
            "Pressure CSV automatic import requires at least two linked readings."
        )

    return ParsedPressureCsv(
        parser_version=parser_version,
        schema_name=PRESSURE_CSV_SCHEMA_NAME,
        readings=tuple(sorted(readings, key=lambda reading: reading.timestamp)),
        warnings=tuple(warnings),
    )


def _normalize_header(value: str) -> str:
    return value.strip().lower().replace(" ", "_")


def _parse_timestamp(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    timestamp = datetime.fromisoformat(normalized)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("Pressure CSV timestamp must include a timezone.")
    return timestamp


def _parse_finite_float(value: str) -> float:
    parsed = float(value)
    if not isfinite(parsed):
        raise ValueError("Pressure CSV value must be finite.")
    return parsed
