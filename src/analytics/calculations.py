"""Versioned Decimal calculations with complete input lineage."""

from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path

from src.schemas.models import CalculationRunStatus, Unit
from src.planning.models import MetricId

from .models import (
    CalculationOutputField,
    CalculationRuleId,
    CalculationRunRecord,
    FactValue,
    WarningCode,
)


class CalculationError(ValueError):
    pass


@dataclass(frozen=True)
class ChangeCalculation:
    absolute_change: Decimal | None
    percentage_change: Decimal | None
    percentage_point_change: Decimal | None
    runs: tuple[CalculationRunRecord, ...]
    warnings: tuple[WarningCode, ...]


class PercentageBaselinePolicy(str, Enum):
    POSITIVE = "POSITIVE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class MetricCalculationPolicy:
    metric_id: MetricId
    allow_absolute_change: bool
    allow_percentage_change: bool
    allow_percentage_point_change: bool
    percentage_baseline_policy: PercentageBaselinePolicy
    minimum_absolute_baseline: Decimal


class RuleRegistry:
    def __init__(self, root: Path):
        with (root / "config/calculation_rules.csv").open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.rows = {CalculationRuleId(row["rule_id"]): row for row in rows}
        if set(self.rows) != set(CalculationRuleId):
            raise ValueError("calculation rule registry must exactly cover CalculationRuleId")
        with (root / "config/metric_calculation_policies.csv").open(newline="", encoding="utf-8") as handle:
            policy_rows = list(csv.DictReader(handle))

        def parse_bool(value: str) -> bool:
            if value not in {"true", "false"}:
                raise ValueError(f"invalid calculation-policy boolean: {value}")
            return value == "true"

        self.policies = {
            MetricId(row["metric_id"]): MetricCalculationPolicy(
                metric_id=MetricId(row["metric_id"]),
                allow_absolute_change=parse_bool(row["allow_absolute_change"]),
                allow_percentage_change=parse_bool(row["allow_percentage_change"]),
                allow_percentage_point_change=parse_bool(row["allow_percentage_point_change"]),
                percentage_baseline_policy=PercentageBaselinePolicy(row["percentage_baseline_policy"]),
                minimum_absolute_baseline=Decimal(row["minimum_absolute_baseline"]),
            )
            for row in policy_rows
        }
        with (root / "config/metric_catalog.csv").open(newline="", encoding="utf-8") as handle:
            governed_metric_ids = {MetricId(row["metric_id"]) for row in csv.DictReader(handle)}
        if set(self.policies) != governed_metric_ids:
            raise ValueError("metric calculation policies must exactly cover MetricId")
        for policy in self.policies.values():
            if policy.minimum_absolute_baseline < 0:
                raise ValueError("minimum_absolute_baseline must be non-negative")
            expected_baseline_policy = (
                PercentageBaselinePolicy.POSITIVE
                if policy.allow_percentage_change else PercentageBaselinePolicy.NOT_APPLICABLE
            )
            if policy.percentage_baseline_policy is not expected_baseline_policy:
                raise ValueError(f"inconsistent percentage baseline policy for {policy.metric_id.value}")

    def version(self, rule_id: CalculationRuleId) -> str:
        return self.rows[rule_id]["rule_version"]

    def assert_unit(self, rule_id: CalculationRuleId, unit: Unit) -> None:
        allowed = self.rows[rule_id]["allowed_units"].split("|")
        if unit.value not in allowed:
            raise CalculationError(f"{rule_id.value} does not allow unit {unit.value}")

    def policy(self, metric_id: MetricId) -> MetricCalculationPolicy:
        return self.policies[metric_id]


def _digest(facts: tuple[FactValue, ...]) -> str:
    payload = "|".join(
        f"{fact.fact_id}:{fact.metric_id.value}:{fact.value}:{fact.unit.value}"
        for fact in facts
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def calculation_run(
    registry: RuleRegistry,
    rule_id: CalculationRuleId,
    output_field: CalculationOutputField,
    facts: tuple[FactValue, ...],
    result_value: Decimal | None,
    executed_at: datetime,
    question_id: str,
    *,
    status: CalculationRunStatus = CalculationRunStatus.SUCCESS,
    tolerance: Decimal = Decimal("0"),
) -> CalculationRunRecord:
    if not facts:
        raise CalculationError("calculation requires input facts")
    input_digest = _digest(facts)
    identity = f"{question_id}|{rule_id.value}|{input_digest}|{output_field.value}"
    run_id = f"run_{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:16]}"
    return CalculationRunRecord(
        run_id=run_id, rule_id=rule_id, rule_version=registry.version(rule_id),
        company=facts[0].company, metric_id=facts[0].metric_id,
        output_field=output_field, input_fact_ids=tuple(fact.fact_id for fact in facts),
        input_digest=input_digest, result_value=result_value, executed_at=executed_at,
        status=status, tolerance_applied=tolerance,
    )


def calculate_period_change(
    registry: RuleRegistry,
    current: FactValue,
    comparison: FactValue,
    executed_at: datetime,
    question_id: str,
) -> ChangeCalculation:
    if (
        current.company is not comparison.company
        or current.metric_id is not comparison.metric_id
        or current.business_scope != comparison.business_scope
    ):
        raise CalculationError("period comparison requires the same company, metric, and scope")
    if current.unit is not comparison.unit:
        raise CalculationError("period comparison requires identical units")
    facts = (comparison, current)
    policy = registry.policy(current.metric_id)
    warnings: list[WarningCode] = []
    runs: list[CalculationRunRecord] = []
    delta = current.value - comparison.value
    if current.unit is Unit.PERCENTAGE_POINT:
        if not policy.allow_percentage_point_change:
            raise CalculationError(f"percentage-point change is not allowed for {current.metric_id.value}")
        registry.assert_unit(CalculationRuleId.PERCENTAGE_POINT_CHANGE_V1, current.unit)
        runs.append(calculation_run(
            registry, CalculationRuleId.PERCENTAGE_POINT_CHANGE_V1,
            CalculationOutputField.PERCENTAGE_POINT_CHANGE, facts, delta, executed_at, question_id,
        ))
        return ChangeCalculation(None, None, delta, tuple(runs), ())

    if not policy.allow_absolute_change:
        raise CalculationError(f"absolute change is not allowed for {current.metric_id.value}")
    registry.assert_unit(CalculationRuleId.ABSOLUTE_CHANGE_V1, current.unit)
    runs.append(calculation_run(
        registry, CalculationRuleId.ABSOLUTE_CHANGE_V1,
        CalculationOutputField.ABSOLUTE_CHANGE, facts, delta, executed_at, question_id,
    ))
    registry.assert_unit(CalculationRuleId.PERCENT_CHANGE_V1, current.unit)
    if not policy.allow_percentage_change:
        warnings.append(WarningCode.PERCENT_CHANGE_DISALLOWED_FOR_METRIC)
        runs.append(calculation_run(
            registry, CalculationRuleId.PERCENT_CHANGE_V1,
            CalculationOutputField.PERCENT_CHANGE, facts, None, executed_at, question_id,
            status=CalculationRunStatus.FAILED,
        ))
        percentage = None
    elif comparison.value == 0:
        warnings.append(WarningCode.ZERO_DENOMINATOR)
        runs.append(calculation_run(
            registry, CalculationRuleId.PERCENT_CHANGE_V1,
            CalculationOutputField.PERCENT_CHANGE, facts, None, executed_at, question_id,
            status=CalculationRunStatus.FAILED,
        ))
        percentage = None
    elif abs(comparison.value) < policy.minimum_absolute_baseline:
        warnings.append(WarningCode.NEAR_ZERO_BASELINE_PERCENT_CHANGE_UNAVAILABLE)
        runs.append(calculation_run(
            registry, CalculationRuleId.PERCENT_CHANGE_V1,
            CalculationOutputField.PERCENT_CHANGE, facts, None, executed_at, question_id,
            status=CalculationRunStatus.FAILED,
        ))
        percentage = None
    elif policy.percentage_baseline_policy is PercentageBaselinePolicy.POSITIVE and comparison.value <= 0:
        warnings.append(WarningCode.NON_POSITIVE_BASELINE_PERCENT_CHANGE_UNAVAILABLE)
        runs.append(calculation_run(
            registry, CalculationRuleId.PERCENT_CHANGE_V1,
            CalculationOutputField.PERCENT_CHANGE, facts, None, executed_at, question_id,
            status=CalculationRunStatus.FAILED,
        ))
        percentage = None
    else:
        percentage = delta / comparison.value * Decimal("100")
        runs.append(calculation_run(
            registry, CalculationRuleId.PERCENT_CHANGE_V1,
            CalculationOutputField.PERCENT_CHANGE, facts, percentage, executed_at, question_id,
        ))
    return ChangeCalculation(delta, percentage, None, tuple(runs), tuple(warnings))
