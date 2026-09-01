from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Iterable

MONEY_QUANTUM = Decimal("0.01")
ZERO = Decimal("0.00")
MAX_MONEY = Decimal("999999999.99")


class MoneyValidationError(ValueError):
    """Raised when a user-supplied monetary value is unsafe or unsupported."""


def as_decimal(value) -> Decimal:
    """Convert an already-trusted database/domain value to a two-cent Decimal."""
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        amount = value
    else:
        amount = Decimal(str(value))
    if not amount.is_finite():
        raise MoneyValidationError("Money values must be finite.")
    return amount.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def parse_money(
    value,
    *,
    allow_zero: bool = True,
    allow_negative: bool = True,
    max_abs: Decimal = MAX_MONEY,
) -> Decimal:
    """Parse an API money literal without routing it through binary floating point.

    Ledgerly deliberately rejects scientific notation for user-facing currency inputs.
    Values are rounded to cents using ROUND_HALF_UP and bounded to the supported range.
    """
    if isinstance(value, bool) or value is None:
        raise MoneyValidationError("A decimal money value is required.")

    raw = str(value).strip()
    if not raw or "e" in raw.lower():
        raise MoneyValidationError("Use a standard decimal amount, not scientific notation.")

    try:
        amount = Decimal(raw)
    except (InvalidOperation, ValueError):
        raise MoneyValidationError("A valid decimal money value is required.") from None

    if not amount.is_finite():
        raise MoneyValidationError("Money values must be finite.")

    amount = amount.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    if abs(amount) > max_abs:
        raise MoneyValidationError("Money value is outside Ledgerly's supported range.")
    if not allow_negative and amount < ZERO:
        raise MoneyValidationError("Money value cannot be negative.")
    if not allow_zero and amount == ZERO:
        raise MoneyValidationError("Money value must be greater than zero.")
    return amount


def json_money(value) -> float:
    """Serialize money as a JSON number only at the API boundary."""
    return float(as_decimal(value))


def money_sum(values: Iterable) -> Decimal:
    total = ZERO
    for value in values:
        total += as_decimal(value)
    return total.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def percent(numerator, denominator) -> Decimal:
    denominator_value = as_decimal(denominator)
    if denominator_value == ZERO:
        return ZERO
    result = (as_decimal(numerator) / denominator_value) * Decimal("100")
    return result.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
