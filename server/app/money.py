from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

MAX_MONEY_CENTS = 99_999_999_999  # $999,999,999.99
_CENT = Decimal("0.01")
_HUNDRED = Decimal(100)


class MoneyValidationError(ValueError):
    """Raised when a value cannot be represented safely as Ledgerly money."""


def to_cents(
    value: Any,
    *,
    label: str = "Amount",
    allow_zero: bool = True,
    allow_negative: bool = True,
) -> int:
    """Parse a user/API monetary value into exact integer cents.

    Ledgerly accepts at most two decimal places and rejects NaN/Infinity instead of
    rounding surprising inputs. Database calculations operate on the returned integer.
    """
    if isinstance(value, bool) or value is None:
        raise MoneyValidationError(f"{label} must be a valid monetary amount.")

    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, AttributeError, ValueError):
        raise MoneyValidationError(f"{label} must be a valid monetary amount.") from None

    if not amount.is_finite():
        raise MoneyValidationError(f"{label} must be a finite monetary amount.")

    quantized = amount.quantize(_CENT, rounding=ROUND_HALF_UP)
    if quantized != amount:
        raise MoneyValidationError(f"{label} cannot contain more than two decimal places.")

    cents = int(quantized * _HUNDRED)
    if not allow_negative and cents < 0:
        raise MoneyValidationError(f"{label} cannot be negative.")
    if not allow_zero and cents == 0:
        raise MoneyValidationError(f"{label} must be greater than $0.00.")
    if abs(cents) > MAX_MONEY_CENTS:
        raise MoneyValidationError(f"{label} cannot exceed $999,999,999.99.")
    return cents


def cents_to_dollars(cents: int | None) -> float:
    """Convert exact storage cents to a JSON/display dollar number."""
    return float((Decimal(int(cents or 0)) / _HUNDRED).quantize(_CENT))


def percent(numerator_cents: int, denominator_cents: int) -> float:
    if denominator_cents == 0:
        return 0.0
    value = (Decimal(numerator_cents) * Decimal(100)) / Decimal(denominator_cents)
    return float(value.quantize(_CENT, rounding=ROUND_HALF_UP))


def legacy_float(cents: int) -> float:
    """Compatibility mirror for legacy FLOAT columns during the cents migration."""
    return cents_to_dollars(cents)
