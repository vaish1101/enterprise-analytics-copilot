"""Execute validated Step 3 plans using only governed normalized facts."""

from __future__ import annotations

import hashlib
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Callable

from src.planning.models import (
    AnalyticalPlan,
    CompanyId,
    MetricId,
    PlanOperation,
    PlanningStatus,
    RankingDirection,
)
from src.schemas.models import CalculationRunStatus, ProvenanceType, Unit
from src.validation.reconciliation import (
    reconcile_henkel_nominal_change,
    reconcile_henkel_price_volume,
    reconcile_mercedes_bridge,
    reconcile_mercedes_reported_ebit,
)

from .calculations import RuleRegistry, calculate_period_change, calculation_run
from .facts import FactRecord, FactStore
from .models import (
    AnalyticalResult,
    CalculationOutputField,
    CalculationRuleId,
    CalculationRunRecord,
    ExecutionOperation,
    ExecutionStatus,
    FactValue,
    LimitationCode,
    ProvenanceCount,
    RankedComponent,
    ReconciliationResult,
    WarningCode,
)


class ExecutionRejectedError(ValueError):
    pass


class AnalyticsExecutor:
    def __init__(
        self,
        root: Path | str | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ):
        self.root = Path(root) if root else Path(__file__).resolve().parents[2]
        self.facts = FactStore(self.root)
        self.rules = RuleRegistry(self.root)
        self.clock = clock or (lambda: datetime.now(UTC))

    def execute(self, plan: AnalyticalPlan) -> AnalyticalResult:
        if not isinstance(plan, AnalyticalPlan):
            raise ExecutionRejectedError("execution input must be a validated AnalyticalPlan")
        if plan.status is not PlanningStatus.READY:
            raise ExecutionRejectedError(f"execution requires READY plan, got {plan.status.value}")
        if plan.primary_target is None:
            raise ExecutionRejectedError("READY execution requires primary_target")
        if plan.comparison_target is not None or plan.requires_cross_company_comparison:
            raise ExecutionRejectedError("cross-company arithmetic is not supported")
        target = plan.primary_target
        if target.business_scope is None or target.period is None or target.period_grain is None:
            raise ExecutionRejectedError("execution requires metric, scope, period, and period grain")
        try:
            primary = self.facts.get(target.company, target.metric_id, target.business_scope, target.period)
        except (LookupError, ValueError) as error:
            raise ExecutionRejectedError(str(error)) from error
        if primary.period_grain is not target.period_grain:
            raise ExecutionRejectedError("plan period grain does not match normalized fact")

        executed_at = self.clock()
        if plan.operation is PlanOperation.LOOKUP:
            return self._result(plan, ExecutionOperation.RETRIEVE, primary)
        if plan.operation is PlanOperation.CALCULATE_CHANGE:
            if target.comparison_period is None:
                raise ExecutionRejectedError("period comparison requires comparison_period")
            comparison = self.facts.get(
                target.company, target.metric_id, target.business_scope, target.comparison_period
            )
            change = calculate_period_change(self.rules, primary, comparison, executed_at, plan.question_id)
            percentage_unavailable_warnings = {
                WarningCode.ZERO_DENOMINATOR,
                WarningCode.NON_POSITIVE_BASELINE_PERCENT_CHANGE_UNAVAILABLE,
                WarningCode.NEAR_ZERO_BASELINE_PERCENT_CHANGE_UNAVAILABLE,
                WarningCode.PERCENT_CHANGE_DISALLOWED_FOR_METRIC,
            }
            limitations = (
                (LimitationCode.PERCENT_CHANGE_UNAVAILABLE,)
                if percentage_unavailable_warnings.intersection(change.warnings) else ()
            )
            return self._result(
                plan, ExecutionOperation.PERIOD_COMPARISON, primary,
                comparison=comparison, absolute_change=change.absolute_change,
                percentage_change=change.percentage_change,
                percentage_point_change=change.percentage_point_change,
                runs=change.runs, warnings=change.warnings, limitations=limitations,
            )
        if plan.operation in {
            PlanOperation.DECOMPOSE_VARIANCE,
            PlanOperation.RANK_CONTRIBUTIONS,
            PlanOperation.RECONCILE,
        }:
            components = self._decomposition(primary)
            reconciliations, reconciliation_runs, warnings, supporting = self._reconcile(
                primary, components, executed_at, plan.question_id
            )
            limitations = [LimitationCode.MANAGEMENT_ATTRIBUTION_NOT_CAUSAL]
            if any(item.metric_id is MetricId.MERCEDES_BRIDGE_VOLUME_STRUCTURE_NET_PRICING for item in components):
                limitations.append(LimitationCode.COMBINED_COMPONENT_NOT_SPLIT)
            if any(not item.passed for item in reconciliations):
                limitations.append(LimitationCode.RECONCILIATION_FAILED)
            if plan.operation is PlanOperation.RANK_CONTRIBUTIONS:
                ranked, ranking_run = self._rank(
                    components, plan.ranking_direction, executed_at, plan.question_id
                )
                return self._result(
                    plan, ExecutionOperation.RANKING, primary,
                    components=components, supporting=supporting, ranked=ranked,
                    reconciliations=reconciliations,
                    runs=reconciliation_runs + (ranking_run,),
                    warnings=warnings, limitations=tuple(limitations),
                )
            operation = (
                ExecutionOperation.RECONCILIATION
                if plan.operation is PlanOperation.RECONCILE else ExecutionOperation.DECOMPOSITION
            )
            return self._result(
                plan, operation, primary, components=components, supporting=supporting,
                reconciliations=reconciliations, runs=reconciliation_runs,
                warnings=warnings, limitations=tuple(limitations),
            )
        raise ExecutionRejectedError(f"unsupported execution operation {plan.operation.value}")

    def _decomposition(self, primary: FactValue) -> tuple[FactValue, ...]:
        if primary.company is CompanyId.HENKEL:
            if primary.metric_id is MetricId.HENKEL_ORGANIC_SALES_GROWTH:
                metric_ids = (MetricId.HENKEL_PRICE_CONTRIBUTION, MetricId.HENKEL_VOLUME_CONTRIBUTION)
            elif primary.metric_id is MetricId.HENKEL_NOMINAL_SALES_CHANGE:
                metric_ids = (
                    MetricId.HENKEL_FX_EFFECT,
                    MetricId.HENKEL_ACQUISITIONS_DIVESTMENTS_EFFECT,
                    MetricId.HENKEL_ORGANIC_SALES_GROWTH,
                )
            else:
                raise ExecutionRejectedError("unsupported Henkel decomposition metric")
            return tuple(
                self.facts.get(primary.company, metric_id, primary.business_scope, primary.period)
                for metric_id in metric_ids
            )
        if primary.metric_id not in {MetricId.MERCEDES_EBIT, MetricId.MERCEDES_ADJUSTED_EBIT}:
            raise ExecutionRejectedError("unsupported Mercedes decomposition metric")
        bridge = self.facts.bridge(primary.business_scope)
        return tuple(record.fact for record in bridge if record.bridge_role == "COMPONENT")

    def _reconcile(
        self,
        primary: FactValue,
        components: tuple[FactValue, ...],
        executed_at: datetime,
        question_id: str,
    ) -> tuple[
        tuple[ReconciliationResult, ...],
        tuple[CalculationRunRecord, ...],
        tuple[WarningCode, ...],
        tuple[FactValue, ...],
    ]:
        results: list[ReconciliationResult] = []
        runs: list[CalculationRunRecord] = []
        warnings: list[WarningCode] = []
        if primary.company is CompanyId.HENKEL:
            if primary.metric_id is MetricId.HENKEL_ORGANIC_SALES_GROWTH:
                raw = reconcile_henkel_price_volume(
                    components[0].value, components[1].value, primary.value, primary.rounding_tolerance
                )
                rule_id = CalculationRuleId.HENKEL_ORGANIC_RECONCILIATION_V1
            elif primary.metric_id is MetricId.HENKEL_NOMINAL_SALES_CHANGE:
                raw = reconcile_henkel_nominal_change(
                    components[0].value, components[1].value, components[2].value,
                    primary.value, primary.rounding_tolerance,
                )
                rule_id = CalculationRuleId.HENKEL_NOMINAL_BRIDGE_V1
            else:
                raise ExecutionRejectedError("unsupported Henkel reconciliation")
            inputs = components
            run = calculation_run(
                self.rules, rule_id, CalculationOutputField.RECONCILIATION_CALCULATED_VALUE,
                inputs, raw.calculated_value, executed_at, question_id,
                tolerance=raw.tolerance,
            )
            runs.append(run)
            results.append(self._reconciliation_model(rule_id, raw, components + (primary,), run.run_id))
            if raw.passed and raw.difference != 0:
                warnings.append(WarningCode.ROUNDING_TOLERANCE_APPLIED)
            return tuple(results), tuple(runs), tuple(warnings), ()

        bridge = self.facts.bridge(primary.business_scope)
        start = self._bridge_role(bridge, "START")
        endpoint = self._bridge_role(bridge, "ADJUSTED_ENDPOINT")
        adjustment = self._bridge_role(bridge, "ADJUSTMENT")
        reported = self._bridge_role(bridge, "REPORTED_ENDPOINT")
        bridge_raw = reconcile_mercedes_bridge(
            start.value, (fact.value for fact in components), endpoint.value, "0"
        )
        bridge_inputs = (start,) + components
        bridge_run = calculation_run(
            self.rules, CalculationRuleId.MERCEDES_EBIT_BRIDGE_V1,
            CalculationOutputField.RECONCILIATION_CALCULATED_VALUE,
            bridge_inputs, bridge_raw.calculated_value, executed_at, question_id,
        )
        runs.append(bridge_run)
        results.append(self._reconciliation_model(
            CalculationRuleId.MERCEDES_EBIT_BRIDGE_V1, bridge_raw,
            bridge_inputs + (endpoint,), bridge_run.run_id,
        ))
        reported_raw = reconcile_mercedes_reported_ebit(
            endpoint.value, adjustment.value, reported.value, "0"
        )
        reported_inputs = (endpoint, adjustment)
        reported_run = calculation_run(
            self.rules, CalculationRuleId.MERCEDES_ADJUSTED_TO_REPORTED_EBIT_V1,
            CalculationOutputField.RECONCILIATION_CALCULATED_VALUE,
            reported_inputs, reported_raw.calculated_value, executed_at, question_id,
        )
        runs.append(reported_run)
        results.append(self._reconciliation_model(
            CalculationRuleId.MERCEDES_ADJUSTED_TO_REPORTED_EBIT_V1, reported_raw,
            reported_inputs + (reported,), reported_run.run_id,
        ))
        return tuple(results), tuple(runs), (), (start, endpoint, adjustment, reported)

    @staticmethod
    def _bridge_role(records: tuple[FactRecord, ...], role: str) -> FactValue:
        matches = [record.fact for record in records if record.bridge_role == role]
        if len(matches) != 1:
            raise ExecutionRejectedError(f"bridge must contain exactly one {role}")
        return matches[0]

    @staticmethod
    def _reconciliation_model(rule_id, raw, facts, run_id) -> ReconciliationResult:
        return ReconciliationResult(
            rule_id=rule_id, expected_value=raw.reported_value,
            calculated_value=raw.calculated_value,
            absolute_difference=abs(raw.difference), tolerance=raw.tolerance,
            passed=raw.passed, source_fact_ids=tuple(fact.fact_id for fact in facts),
            calculation_run_id=run_id,
        )

    def _rank(
        self,
        components: tuple[FactValue, ...],
        direction: RankingDirection | None,
        executed_at: datetime,
        question_id: str,
    ) -> tuple[tuple[RankedComponent, ...], CalculationRunRecord]:
        if direction is None:
            raise ExecutionRejectedError("ranking plan requires ranking_direction")
        if len({item.unit for item in components}) != 1:
            raise ExecutionRejectedError("ranking requires compatible units")
        if direction is RankingDirection.LARGEST_NEGATIVE:
            eligible = [item for item in components if item.value < 0]
            eligible.sort(key=lambda item: item.value)
        elif direction is RankingDirection.LARGEST_POSITIVE:
            eligible = [item for item in components if item.value > 0]
            eligible.sort(key=lambda item: item.value, reverse=True)
        else:
            eligible = sorted(components, key=lambda item: abs(item.value), reverse=True)
        if not eligible:
            raise ExecutionRejectedError(f"no components match {direction.value}")
        ranked = tuple(
            RankedComponent(
                rank=index, fact_id=fact.fact_id, metric_id=fact.metric_id,
                component_label=fact.reported_name, value=fact.value, unit=fact.unit,
                provenance_type=fact.provenance_type,
            )
            for index, fact in enumerate(eligible, start=1)
        )
        run = calculation_run(
            self.rules, CalculationRuleId.RANK_CONTRIBUTIONS_V1,
            CalculationOutputField.RANKING, tuple(eligible), eligible[0].value,
            executed_at, question_id,
        )
        return ranked, run

    def _result(
        self,
        plan: AnalyticalPlan,
        operation: ExecutionOperation,
        primary: FactValue,
        *,
        comparison: FactValue | None = None,
        absolute_change: Decimal | None = None,
        percentage_change: Decimal | None = None,
        percentage_point_change: Decimal | None = None,
        components: tuple[FactValue, ...] = (),
        supporting: tuple[FactValue, ...] = (),
        ranked: tuple[RankedComponent, ...] = (),
        reconciliations: tuple[ReconciliationResult, ...] = (),
        runs: tuple[CalculationRunRecord, ...] = (),
        warnings: tuple[WarningCode, ...] = (),
        limitations: tuple[LimitationCode, ...] = (),
    ) -> AnalyticalResult:
        facts = (primary,) + ((comparison,) if comparison else ()) + components + supporting
        unique_facts = tuple({fact.fact_id: fact for fact in facts}.values())
        provenance_counts = Counter(fact.provenance_type for fact in unique_facts)
        successful_runs = sum(run.status is CalculationRunStatus.SUCCESS for run in runs)
        if successful_runs:
            provenance_counts[ProvenanceType.CALCULATED] += successful_runs
        provenance = tuple(
            ProvenanceCount(provenance_type=item, fact_count=provenance_counts[item])
            for item in sorted(provenance_counts, key=lambda value: value.value)
        )
        evidence_ids = tuple(dict.fromkeys(
            evidence_id for fact in unique_facts for evidence_id in fact.evidence_ids
        ))
        identity = plan.model_dump_json() + "|" + "|".join(
            f"{fact.fact_id}:{fact.value}" for fact in unique_facts
        )
        execution_id = f"exec_{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:16]}"
        status = ExecutionStatus.SUCCESS_WITH_LIMITATIONS if warnings or limitations else ExecutionStatus.SUCCESS
        return AnalyticalResult(
            execution_id=execution_id, question_id=plan.question_id,
            source_plan_operation=plan.operation, operation=operation, status=status,
            primary_result=primary, comparison_result=comparison,
            supporting_results=tuple({fact.fact_id: fact for fact in supporting}.values()),
            absolute_change=absolute_change, percentage_change=percentage_change,
            percentage_point_change=percentage_point_change,
            decomposition_components=components, ranked_components=ranked,
            reconciliation_results=reconciliations, provenance_summary=provenance,
            evidence_ids=evidence_ids, calculation_runs=runs,
            calculation_run_ids=tuple(run.run_id for run in runs),
            warnings=warnings, limitations=limitations,
        )
