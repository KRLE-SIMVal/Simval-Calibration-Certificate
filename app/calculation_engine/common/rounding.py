"""AB11 reporting rounding primitives."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP


class RoundingError(ValueError):
    """Raised when reporting rounding cannot be performed safely."""


@dataclass(frozen=True, slots=True)
class RoundedUncertainty:
    value: Decimal
    decimal_places: int
    significant_digits: int


def round_expanded_uncertainty(
    expanded_uncertainty: Decimal | float | str,
    *,
    significant_digits: int = 2,
    cmc_floor: Decimal | float | str | None = None,
) -> RoundedUncertainty:
    """Round expanded uncertainty for AB11 reporting.

    AB11 permits no more than two significant digits for expanded
    uncertainty. If one significant digit is used, it must be rounded up.
    With two significant digits, normal rounding is used.
    """
    if significant_digits not in {1, 2}:
        raise RoundingError("AB11 reporting permits one or two significant digits.")

    value = _to_non_negative_decimal(expanded_uncertainty, "expanded_uncertainty")
    floor = (
        _to_non_negative_decimal(cmc_floor, "cmc_floor")
        if cmc_floor is not None
        else None
    )

    quantum = _quantum_for_significant_digits(value, significant_digits)
    rounding_mode = ROUND_CEILING if significant_digits == 1 else ROUND_HALF_UP
    rounded = value.quantize(quantum, rounding=rounding_mode)

    if floor is not None and rounded < floor:
        rounded = value.quantize(quantum, rounding=ROUND_CEILING)
        if rounded < floor:
            raise RoundingError("Rounded uncertainty would be below the CMC floor.")

    return RoundedUncertainty(
        value=rounded,
        decimal_places=max(-rounded.as_tuple().exponent, 0),
        significant_digits=significant_digits,
    )


def round_result_to_uncertainty(
    result: Decimal | float | str,
    uncertainty: RoundedUncertainty,
) -> Decimal:
    """Round a reported result to the least significant digit of U."""
    value = _to_decimal(result, "result")
    quantum = Decimal(1).scaleb(-uncertainty.decimal_places)
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def _quantum_for_significant_digits(value: Decimal, significant_digits: int) -> Decimal:
    if value == 0:
        return Decimal(1).scaleb(-(significant_digits - 1))
    exponent = value.adjusted() - significant_digits + 1
    return Decimal(1).scaleb(exponent)


def _to_non_negative_decimal(value: Decimal | float | str, name: str) -> Decimal:
    decimal_value = _to_decimal(value, name)
    if decimal_value < 0:
        raise RoundingError(f"{name} must be >= 0.")
    return decimal_value


def _to_decimal(value: Decimal | float | str, name: str) -> Decimal:
    decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    if not decimal_value.is_finite():
        raise RoundingError(f"{name} must be finite.")
    return decimal_value

