"""CMC range lookup primitives.

This module implements only the approved P1 CMC expression types:
constant, linear_segment, and table_worst_case. It does not implement
certificate calculations.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite


class CmcExpressionType(StrEnum):
    CONSTANT = "constant"
    LINEAR_SEGMENT = "linear_segment"
    TABLE_WORST_CASE = "table_worst_case"


class CmcLookupError(ValueError):
    """Raised when CMC lookup cannot produce an auditable result."""


@dataclass(frozen=True, slots=True)
class CmcRange:
    lower: float
    upper: float
    include_lower: bool = True
    include_upper: bool = False

    def __post_init__(self) -> None:
        if not all(isfinite(v) for v in (self.lower, self.upper)):
            raise ValueError("CMC range bounds must be finite.")
        if self.lower >= self.upper:
            raise ValueError("CMC range lower bound must be below upper bound.")

    def contains(self, value: float) -> bool:
        lower_ok = value >= self.lower if self.include_lower else value > self.lower
        upper_ok = value <= self.upper if self.include_upper else value < self.upper
        return lower_ok and upper_ok


@dataclass(frozen=True, slots=True)
class CmcEntry:
    entry_id: str
    version: str
    expression_type: CmcExpressionType
    range: CmcRange
    unit: str
    value: float | None = None
    lower_value: float | None = None
    upper_value: float | None = None
    approved: bool = True

    def __post_init__(self) -> None:
        if not self.entry_id:
            raise ValueError("CMC entry id is required.")
        if not self.version:
            raise ValueError("CMC entry version is required.")
        if not self.unit:
            raise ValueError("CMC unit is required.")
        if self.expression_type in {
            CmcExpressionType.CONSTANT,
            CmcExpressionType.TABLE_WORST_CASE,
        }:
            if self.value is None or not isfinite(self.value) or self.value < 0:
                raise ValueError("Constant/table CMC value must be finite and >= 0.")
        if self.expression_type is CmcExpressionType.LINEAR_SEGMENT:
            values = (self.lower_value, self.upper_value)
            if any(v is None or not isfinite(v) or v < 0 for v in values):
                raise ValueError("Linear CMC endpoints must be finite and >= 0.")


@dataclass(frozen=True, slots=True)
class CmcLookupResult:
    entry_id: str
    version: str
    expression_type: CmcExpressionType
    raw_cmc: float
    interpolated: bool


def lookup_cmc(value: float, entries: list[CmcEntry], *, unit: str) -> CmcLookupResult:
    """Find the single auditable CMC value for value and unit."""
    if not isfinite(value):
        raise CmcLookupError("Measurement value must be finite.")
    matches = [
        entry
        for entry in entries
        if entry.approved and entry.unit == unit and entry.range.contains(value)
    ]
    if not matches:
        raise CmcLookupError("No approved CMC entry matches the value and unit.")
    if len(matches) > 1:
        raise CmcLookupError("Multiple CMC entries match; lookup is ambiguous.")
    entry = matches[0]
    raw_cmc = _evaluate_entry(value, entry)
    return CmcLookupResult(
        entry_id=entry.entry_id,
        version=entry.version,
        expression_type=entry.expression_type,
        raw_cmc=raw_cmc,
        interpolated=entry.expression_type is CmcExpressionType.LINEAR_SEGMENT,
    )


def apply_cmc_floor(calculated_u: float, cmc_value: float) -> float:
    """Apply the AB11/ILAC floor rule to expanded uncertainty."""
    if calculated_u < 0 or cmc_value < 0:
        raise ValueError("Uncertainty values must be >= 0.")
    return max(calculated_u, cmc_value)


def _evaluate_entry(value: float, entry: CmcEntry) -> float:
    if entry.expression_type in {
        CmcExpressionType.CONSTANT,
        CmcExpressionType.TABLE_WORST_CASE,
    }:
        assert entry.value is not None
        return entry.value
    if entry.expression_type is CmcExpressionType.LINEAR_SEGMENT:
        assert entry.lower_value is not None
        assert entry.upper_value is not None
        span = entry.range.upper - entry.range.lower
        position = (value - entry.range.lower) / span
        return entry.lower_value + position * (entry.upper_value - entry.lower_value)
    raise CmcLookupError(f"Unsupported CMC expression type: {entry.expression_type}")

