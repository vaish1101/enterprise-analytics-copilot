"""Auditable arithmetic reconciliations using decimal, source-preserving values."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable


Number = Decimal | int | str


def _decimal(value: Number) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


@dataclass(frozen=True)
class ReconciliationResult:
    rule_id: str
    passed: bool
    calculated_value: Decimal
    reported_value: Decimal
    difference: Decimal
    tolerance: Decimal


def _reconcile(rule_id: str, calculated: Number, reported: Number, tolerance: Number) -> ReconciliationResult:
    calculated_value = _decimal(calculated)
    reported_value = _decimal(reported)
    tolerance_value = _decimal(tolerance)
    if tolerance_value < 0:
        raise ValueError("tolerance must be non-negative")
    difference = calculated_value - reported_value
    return ReconciliationResult(
        rule_id=rule_id,
        passed=abs(difference) <= tolerance_value,
        calculated_value=calculated_value,
        reported_value=reported_value,
        difference=difference,
        tolerance=tolerance_value,
    )


def reconcile_henkel_price_volume(
    price: Number, volume: Number, reported_organic_growth: Number, tolerance_pp: Number = "0.1"
) -> ReconciliationResult:
    return _reconcile(
        "henkel_price_plus_volume_equals_organic_growth",
        _decimal(price) + _decimal(volume),
        reported_organic_growth,
        tolerance_pp,
    )


def reconcile_henkel_nominal_change(
    foreign_exchange: Number,
    acquisitions_divestments: Number,
    organic_growth: Number,
    reported_nominal_change: Number,
    tolerance_pp: Number = "0.1",
) -> ReconciliationResult:
    return _reconcile(
        "henkel_fx_plus_portfolio_plus_organic_equals_nominal",
        _decimal(foreign_exchange) + _decimal(acquisitions_divestments) + _decimal(organic_growth),
        reported_nominal_change,
        tolerance_pp,
    )


def reconcile_mercedes_bridge(
    starting_value: Number,
    components: Iterable[Number],
    reported_adjusted_endpoint: Number,
    tolerance_eur_m: Number = "0",
) -> ReconciliationResult:
    calculated = _decimal(starting_value) + sum((_decimal(value) for value in components), Decimal("0"))
    return _reconcile(
        "mercedes_start_plus_components_equals_adjusted_endpoint",
        calculated,
        reported_adjusted_endpoint,
        tolerance_eur_m,
    )


def reconcile_mercedes_reported_ebit(
    adjusted_ebit: Number,
    adjustments: Number,
    reported_ebit: Number,
    tolerance_eur_m: Number = "0",
) -> ReconciliationResult:
    return _reconcile(
        "mercedes_adjusted_ebit_plus_adjustments_equals_reported_ebit",
        _decimal(adjusted_ebit) + _decimal(adjustments),
        reported_ebit,
        tolerance_eur_m,
    )
