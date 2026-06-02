"""Contract for KAYE verification PDF reference data.

The production PDF table extractor is intentionally not implemented in P1.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, tzinfo
from pathlib import Path
from typing import Sequence

from app.backend.domain.entities import MeasurementReading, SourceLocation


class VerificationPdfExtractionNotImplemented(NotImplementedError):
    """Raised while P1 only defines the PDF extraction contract."""


class VerificationPdfParseError(ValueError):
    """Raised when extracted verification table rows are structurally invalid."""


@dataclass(frozen=True, slots=True)
class VerificationPdfContract:
    time_column_name: str = "Time"
    irtd_column_position: int = 2


@dataclass(frozen=True, slots=True)
class VerificationIrtdParseResult:
    contract: VerificationPdfContract
    irtd_column_name: str
    readings: tuple[MeasurementReading, ...]
    warnings: tuple[str, ...]


def parse_irtd_reference_table(
    *,
    rows: Sequence[Sequence[str]],
    uploaded_file_id: str,
    unit: str = "deg C",
    source_label: str = "Verification IRTD",
    default_timezone: tzinfo = timezone.utc,
) -> VerificationIrtdParseResult:
    """Parse extracted verification table rows into traceable IRTD readings."""
    if uploaded_file_id.strip() == "":
        raise VerificationPdfParseError("uploaded_file_id is required.")
    if not rows:
        raise VerificationPdfParseError("Verification table requires a header row.")
    contract = VerificationPdfContract()
    header = tuple(_normalize_cell(value) for value in rows[0])
    try:
        time_index = header.index(contract.time_column_name)
    except ValueError as exc:
        raise VerificationPdfParseError(
            "Verification table must contain a Time column."
        ) from exc
    irtd_index = time_index + 1
    if irtd_index >= len(header) or header[irtd_index] == "":
        raise VerificationPdfParseError(
            "Verification table must contain an IRTD column immediately after Time."
        )
    irtd_column_name = header[irtd_index]

    readings: list[MeasurementReading] = []
    warnings: list[str] = []
    for row_number, row in enumerate(rows[1:], start=2):
        time_value = _cell_at(row, time_index)
        irtd_value = _cell_at(row, irtd_index)
        if time_value == "":
            warnings.append(
                f"Skipped row {row_number} in {source_label} because timestamp is missing."
            )
            continue
        try:
            timestamp = _parse_timestamp(time_value, default_timezone)
        except ValueError:
            warnings.append(
                f"Skipped row {row_number} in {source_label} because timestamp is invalid."
            )
            continue
        if irtd_value == "":
            warnings.append(
                f"Skipped missing IRTD value at {source_label}!{irtd_column_name} row {row_number}."
            )
            continue
        try:
            value = float(irtd_value)
        except ValueError:
            warnings.append(
                f"Skipped nonnumeric IRTD value at {source_label}!{irtd_column_name} row {row_number}."
            )
            continue
        readings.append(
            MeasurementReading(
                timestamp=timestamp,
                channel_id="IRTD",
                value=value,
                unit=unit,
                source=SourceLocation(
                    uploaded_file_id=uploaded_file_id,
                    source_label=source_label,
                    row_number=row_number,
                    column_label=irtd_column_name,
                ),
            )
        )

    return VerificationIrtdParseResult(
        contract=contract,
        irtd_column_name=irtd_column_name,
        readings=tuple(readings),
        warnings=tuple(warnings),
    )


def extract_irtd_reference_rows(_path: Path) -> None:
    """Placeholder for the future verification PDF table extractor."""
    raise VerificationPdfExtractionNotImplemented(
        "Verification PDF extraction is deferred until a dependency is approved."
    )


def _cell_at(row: Sequence[str], index: int) -> str:
    if index >= len(row):
        return ""
    return _normalize_cell(row[index])


def _normalize_cell(value: str) -> str:
    return str(value).strip()


def _parse_timestamp(value: str, default_timezone: tzinfo) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=default_timezone)
    return parsed
