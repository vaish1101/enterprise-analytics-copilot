"""Deterministic, catalog-grounded question classifier and plan builder.

This module resolves intent only. It performs no document retrieval, SQL execution,
calculation, or answer generation.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from src.schemas.models import ConfidenceLevel, EvidenceType, PeriodGrain, ScopeType

from .models import (
    AnalyticalDimension,
    AnalyticalPlan,
    ComparabilityStatus,
    CompanyId,
    MetricId,
    MissingField,
    PeriodId,
    PlanOperation,
    PlanningStatus,
    PlanTarget,
    QuestionType,
    RankingDirection,
)
from .registry import PeriodAlias, PlanningRegistry, ScopeAlias


_OUT_OF_SCOPE_COMPANIES = ("bmw", "volkswagen", "vw", "audi", "tesla", "stellantis")
_OUT_OF_SCOPE_METRICS = ("ebitda", "free cash flow", "cash flow", "net income", "eps", "roe", "market share")
_CALCULATION_PHRASES = (
    "calculate", "difference between", "change from", "changed from", "how much did", "reconcile",
)
_NUMERIC_LOOKUP_PHRASES = (
    "what was", "what were", "how much", "what value", "value of", "reported value", "reported number",
)
_PREDICTIVE_REQUEST_PHRASES = (
    "predict ", "prediction for", "forecast ", "project ", "projection for", "estimate next",
)


@dataclass(frozen=True)
class _MetricResolution:
    metric_id: str | None
    candidates: tuple[str, ...]


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower().replace("’", "'")).strip()


def _contains(text: str, phrase: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text) is not None


def _first_position(text: str, aliases: tuple[str, ...]) -> int | None:
    positions = [match.start() for alias in aliases if (match := re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", text))]
    return min(positions) if positions else None


def _has_document_intent(text: str) -> bool:
    direct_phrases = (
        "according to management", "according to the report", "according to report",
        "what does the report say", "what does report say", "in the report",
        "from the report", "document context", "documentary context",
    )
    if any(phrase in text for phrase in direct_phrases):
        return True
    if _contains(text, "outlook") or _contains(text, "guidance"):
        return True
    management = re.search(r"\bmanagement(?:'s)?\b", text) is not None
    documentary_action = re.search(
        r"\b(?:report|reported|reports|say|said|says|commentary|explain|explained|explanation|outlook|guidance)\b",
        text,
    ) is not None
    return management and documentary_action


def _has_numeric_request(text: str) -> bool:
    return any(phrase in text for phrase in (*_NUMERIC_LOOKUP_PHRASES, *_CALCULATION_PHRASES))


def _is_predictive_request(text: str) -> bool:
    return any(phrase in text for phrase in _PREDICTIVE_REQUEST_PHRASES)


class QuestionPlanner:
    """Build a strict plan from governed aliases and the hardened metric catalog."""

    def __init__(self, root: Path | str | None = None):
        project_root = Path(root) if root else Path(__file__).resolve().parents[2]
        self.registry = PlanningRegistry(project_root)

    def plan(self, question: str, *, question_id: str | None = None) -> AnalyticalPlan:
        raw = question.strip()
        if not raw:
            raise ValueError("question must not be empty")
        qid = question_id or f"q_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:12]}"
        text = _normalize(raw)
        companies = self._companies(text)
        base_type = self._classify(text, len(companies))

        if _is_predictive_request(text):
            return self._unsupported(
                qid, raw,
                "Predictive forecasts and projections are outside the governed reported-information scope.",
            )
        if any(_contains(text, name) for name in _OUT_OF_SCOPE_COMPANIES):
            return self._unsupported(qid, raw, "The requested company is outside the governed Henkel and Mercedes-Benz scope.")
        if any(_contains(text, metric) for metric in _OUT_OF_SCOPE_METRICS):
            return self._unsupported(qid, raw, "The requested metric is not present in the governed metric catalog.")
        unsupported_period = self._unsupported_period(text)
        if unsupported_period:
            return self._unsupported(
                qid, raw,
                f"Period {unsupported_period} is not available in the governed Q2/H1 2025-2026 planning scope.",
            )
        if not companies:
            return self._clarify(
                qid, raw, "No governed company was stated.", (MissingField.COMPANY,),
                "Should this question use Henkel or Mercedes-Benz Group?",
            )
        if len(companies) > 1 or base_type is QuestionType.CROSS_COMPANY_COMPARISON:
            return self._plan_cross_company(qid, raw, text, companies)
        return self._plan_single(qid, raw, text, companies[0], base_type)

    def _companies(self, text: str) -> tuple[CompanyId, ...]:
        found: list[tuple[int, CompanyId]] = []
        for alias, company in self.registry.company_aliases:
            if _contains(text, alias):
                position = text.find(alias)
                found.append((position, company))
        ordered: list[CompanyId] = []
        for _, company in sorted(found, key=lambda item: item[0]):
            if company not in ordered:
                ordered.append(company)
        return tuple(ordered)

    @staticmethod
    def _classify(text: str, company_count: int) -> QuestionType:
        if any(phrase in text for phrase in ("define ", "definition of", "what does ", "how does ")) and any(
            word in text for word in ("define", "definition", "mean")
        ):
            return QuestionType.METRIC_DEFINITION
        if company_count > 1 or text.startswith("compare "):
            return QuestionType.CROSS_COMPANY_COMPARISON
        if any(phrase in text for phrase in (
            "what contributed", "what drove", "drivers of", "bridge", "breakdown", "decompose",
            "largest positive", "largest negative", "rank contribution", "rank the contribution",
        )):
            return QuestionType.VARIANCE_DECOMPOSITION
        if text.startswith("why ") or "explain why" in text:
            return QuestionType.HYBRID_ANALYSIS
        if _has_document_intent(text):
            return QuestionType.HYBRID_ANALYSIS if _has_numeric_request(text) else QuestionType.DOCUMENT_CONTEXT
        if any(phrase in text for phrase in _CALCULATION_PHRASES):
            return QuestionType.CALCULATION
        return QuestionType.REPORTED_FACT

    def _metric(self, text: str, company: CompanyId) -> _MetricResolution:
        matches: list[tuple[int, str]] = []
        for alias, alias_company, metric_id in self.registry.metric_aliases:
            if alias_company is company and _contains(text, alias):
                matches.append((len(alias), metric_id))
        if not matches:
            return _MetricResolution(None, ())
        longest = max(length for length, _ in matches)
        candidates = tuple(sorted({metric_id for length, metric_id in matches if length == longest}))
        return _MetricResolution(candidates[0] if len(candidates) == 1 else None, candidates)

    def _periods(self, text: str) -> tuple[PeriodAlias, ...]:
        found: list[tuple[int, PeriodAlias]] = []
        for item in self.registry.period_aliases:
            match = re.search(rf"(?<![a-z0-9]){re.escape(item.alias)}(?![a-z0-9])", text)
            if match:
                found.append((match.start(), item))
        result: list[PeriodAlias] = []
        for _, item in sorted(found, key=lambda value: value[0]):
            if item.period not in {existing.period for existing in result}:
                result.append(item)
        return tuple(result)

    def _unsupported_period(self, text: str) -> str | None:
        supported = {item.alias for item in self.registry.period_aliases}
        for match in re.finditer(r"(?<![a-z0-9])(?:q[1-4]|h[12]|fy)\s*20\d{2}(?![a-z0-9])", text):
            label = re.sub(r"\s+", " ", match.group(0))
            if label not in supported:
                return label.upper()
        return None

    def _scope(self, text: str, company: CompanyId) -> ScopeAlias | None:
        matches = [item for item in self.registry.scope_aliases if item.company is company and _contains(text, item.alias)]
        return max(matches, key=lambda item: len(item.alias)) if matches else None

    def _wrong_company_scope(self, text: str, company: CompanyId) -> ScopeAlias | None:
        valid_matches = [
            item for item in self.registry.scope_aliases
            if item.company is company and _contains(text, item.alias)
        ]
        matches = [
            item for item in self.registry.scope_aliases
            if item.company is not company and item.alias != "group" and _contains(text, item.alias)
            and not any(item.alias in valid.alias for valid in valid_matches)
        ]
        return max(matches, key=lambda item: len(item.alias)) if matches else None

    @staticmethod
    def _mercedes_split_is_requested(text: str) -> bool:
        combined = any(phrase in text for phrase in (
            "volume / structure / net pricing", "volume structure net pricing", "combined volume structure and net pricing"
        ))
        asks_price = any(_contains(text, phrase) for phrase in ("price", "prices", "pricing", "price contribution", "net pricing"))
        asks_split = any(phrase in text for phrase in ("separate", "split", "how much was due", "versus reduced", "vs reduced"))
        return asks_price and not combined and (asks_split or "ebit" in text or "contribution" in text)

    def _plan_single(
        self, qid: str, raw: str, text: str, company: CompanyId, question_type: QuestionType
    ) -> AnalyticalPlan:
        if company is CompanyId.MERCEDES_BENZ_GROUP and self._mercedes_split_is_requested(text):
            return self._unsupported(
                qid, raw,
                "Mercedes-Benz does not disclose a separate governed price contribution here; the source only supports the combined 'Volume / structure / net pricing' bridge component.",
            )
        wrong_scope = self._wrong_company_scope(text, company)
        if wrong_scope:
            return self._unsupported(qid, raw, f"Scope '{wrong_scope.alias}' belongs to the other governed company.")

        resolution = self._metric(text, company)
        if len(resolution.candidates) > 1:
            names = ", ".join(resolution.candidates)
            return self._clarify(
                qid, raw, f"The metric phrase maps to multiple governed metrics: {names}.",
                (MissingField.METRIC,),
                "For Mercedes-Benz, does 'sales' mean revenue or vehicle unit sales?",
            )
        if resolution.metric_id is None:
            return self._clarify(
                qid, raw, "No governed metric could be resolved from the question.",
                (MissingField.METRIC,), "Which governed metric should be used?",
            )

        metric = self.registry.metric(resolution.metric_id)
        if question_type is QuestionType.METRIC_DEFINITION:
            target = PlanTarget(company=company, metric_id=MetricId(metric.metric_id))
            return self._ready(qid, raw, question_type, target, text)

        periods = self._periods(text)
        if not periods:
            return self._clarify(
                qid, raw, "No supported reporting period was stated.",
                (MissingField.PERIOD,), "Should the plan use Q2 2026, H1 2026, Q2 2025, or H1 2025?",
            )
        period = periods[-1]
        comparison_period = periods[0].period if len(periods) > 1 else None
        scope = self._scope(text, company)
        if scope is None and ScopeType.GROUP in metric.allowed_scope_types:
            scope = self._default_group(company)
        if scope is None:
            return self._clarify(
                qid, raw, "This metric is not valid at Group scope, and no supported business scope was stated.",
                (MissingField.BUSINESS_SCOPE,), "Which supported segment, region, or product scope should be used?",
            )
        if scope.scope_type not in metric.allowed_scope_types:
            return self._unsupported(
                qid, raw,
                f"Metric {metric.metric_id} is not governed for scope type {scope.scope_type.value}.",
            )
        if period.period not in self.registry.availability.get(metric.metric_id, frozenset()):
            return self._unsupported(qid, raw, f"Metric {metric.metric_id} is not available for {period.period.value}.")
        if not self.registry.has_runtime_fact(company, metric.metric_id, scope.scope_id, period.period):
            return self._unsupported(
                qid, raw,
                f"No normalized runtime fact exists for {metric.metric_id}/{scope.scope_id}/{period.period.value}.",
            )

        target_grain = period.grain
        if PeriodGrain.QUARTER_YOY in metric.allowed_period_grains:
            if period.period is not PeriodId.Q2_2026:
                return self._unsupported(qid, raw, f"The governed Mercedes-Benz bridge is only available for Q2 2026 versus Q2 2025.")
            comparison_period = PeriodId.Q2_2025
            target_grain = PeriodGrain.QUARTER_YOY
        elif period.grain not in metric.allowed_period_grains:
            return self._unsupported(qid, raw, f"Metric {metric.metric_id} does not support {period.grain.value} periods.")

        requested_operation = self._operation(question_type, text)
        if requested_operation is PlanOperation.CALCULATE_CHANGE and comparison_period is None:
            return self._clarify(
                qid, raw, "A calculation request needs both a current and comparison period.",
                (MissingField.COMPARISON_PERIOD,),
                "Which two supported periods should be compared?",
            )
        if (
            comparison_period
            and target_grain is not PeriodGrain.QUARTER_YOY
            and comparison_period not in self.registry.availability.get(metric.metric_id, frozenset())
        ):
            return self._unsupported(qid, raw, f"Metric {metric.metric_id} is not available for {comparison_period.value}.")
        if (
            comparison_period
            and target_grain is not PeriodGrain.QUARTER_YOY
            and not self.registry.has_runtime_fact(company, metric.metric_id, scope.scope_id, comparison_period)
        ):
            return self._unsupported(
                qid, raw,
                f"No normalized comparison fact exists for {metric.metric_id}/{scope.scope_id}/{comparison_period.value}.",
            )

        target = PlanTarget(
            company=company, metric_id=MetricId(metric.metric_id),
            business_scope=scope.scope_id, scope_type=scope.scope_type,
            period=period.period, period_grain=target_grain,
            comparison_period=comparison_period,
        )
        return self._ready(qid, raw, question_type, target, text)

    def _plan_cross_company(
        self, qid: str, raw: str, text: str, companies: tuple[CompanyId, ...]
    ) -> AnalyticalPlan:
        if len(companies) < 2:
            return self._clarify(
                qid, raw, "A cross-company comparison requires both governed companies.",
                (MissingField.COMPARISON_COMPANY,), "Which other governed company should be compared?",
            )
        positions: list[tuple[int, CompanyId]] = []
        for company in companies:
            aliases = tuple(alias for alias, item_company in self.registry.company_aliases if item_company is company)
            position = _first_position(text, aliases)
            if position is not None:
                positions.append((position, company))
        positions.sort()
        targets: list[PlanTarget] = []
        periods = self._periods(text)
        if not periods:
            return self._clarify(
                qid, raw, "No common supported comparison period was stated.",
                (MissingField.PERIOD,), "Which common Q2 or H1 2025-2026 period should be compared?",
            )
        period = periods[-1]
        for index, (start, company) in enumerate(positions):
            end = positions[index + 1][0] if index + 1 < len(positions) else len(text)
            segment = text[start:end]
            resolution = self._metric(segment, company)
            if resolution.metric_id is None:
                field = MissingField.METRIC if index == 0 else MissingField.COMPARISON_METRIC
                return self._clarify(
                    qid, raw, f"A unique metric was not resolved for {company.value}.",
                    (field,), "Which governed metric should be used for each company?",
                )
            metric = self.registry.metric(resolution.metric_id)
            scope = self._scope(segment, company)
            if scope is None and ScopeType.GROUP in metric.allowed_scope_types:
                scope = self._default_group(company)
            if scope is None or scope.scope_type not in metric.allowed_scope_types:
                return self._clarify(
                    qid, raw, f"A compatible business scope is required for {metric.metric_id}.",
                    (MissingField.BUSINESS_SCOPE,), "Which compatible scope should be used for the comparison?",
                )
            if period.period not in self.registry.availability.get(metric.metric_id, frozenset()):
                return self._unsupported(qid, raw, f"Metric {metric.metric_id} is not available for {period.period.value}.", question_type=QuestionType.CROSS_COMPANY_COMPARISON)
            if not self.registry.has_runtime_fact(company, metric.metric_id, scope.scope_id, period.period):
                return self._unsupported(
                    qid, raw,
                    f"No normalized runtime fact exists for {metric.metric_id}/{scope.scope_id}/{period.period.value}.",
                    question_type=QuestionType.CROSS_COMPANY_COMPARISON,
                )
            targets.append(PlanTarget(
                company=company, metric_id=MetricId(metric.metric_id),
                business_scope=scope.scope_id, scope_type=scope.scope_type,
                period=period.period, period_grain=period.grain,
            ))

        first_metric = self.registry.metric(targets[0].metric_id.value)
        second_metric = self.registry.metric(targets[1].metric_id.value)
        if first_metric.canonical_family == second_metric.canonical_family == "revenue":
            comparability = ComparabilityStatus.LIMITED
            note = "Descriptive side-by-side comparison only: issuer definitions, consolidation, and scope semantics are not like-for-like."
        elif first_metric.comparable_across_companies and second_metric.comparable_across_companies:
            comparability = ComparabilityStatus.ALLOWED
            note = "Catalog comparability controls allow the comparison."
        else:
            comparability = ComparabilityStatus.NOT_COMPARABLE
            note = "The requested metrics have different canonical families or are explicitly non-comparable in the catalog."
            return self._unsupported(
                qid, raw, note, question_type=QuestionType.CROSS_COMPANY_COMPARISON,
                primary_target=targets[0], comparison_target=targets[1], comparability=comparability,
            )
        return self._ready(
            qid, raw, QuestionType.CROSS_COMPANY_COMPARISON, targets[0], text,
            comparison_target=targets[1], comparability=comparability, comparability_note=note,
        )

    def _default_group(self, company: CompanyId) -> ScopeAlias:
        matches = [
            item for item in self.registry.scope_aliases
            if item.company is company and item.scope_type is ScopeType.GROUP
        ]
        if not matches:
            raise ValueError(f"no governed group scope exists for {company.value}")
        return min(matches, key=lambda item: (item.alias != "group", len(item.alias), item.scope_id))

    def _evidence(
        self, metric_id: str, question_type: QuestionType, operation: PlanOperation
    ) -> tuple[tuple[EvidenceType, ...], tuple[str, ...]]:
        metric_ids = [metric_id]
        if question_type is QuestionType.VARIANCE_DECOMPOSITION or operation is PlanOperation.EXPLAIN_WITH_EVIDENCE:
            if metric_id == "henkel_organic_sales_growth":
                metric_ids.extend(("henkel_price_contribution", "henkel_volume_contribution"))
            if metric_id == "mercedes_adjusted_ebit":
                metric_ids.extend(item for item in self.registry.metrics if item.startswith("mercedes_bridge_") and item != "mercedes_bridge_adjustments")
        evidence_types: set[EvidenceType] = set()
        expectation_ids: list[str] = []
        for item_id in metric_ids:
            for expectation in self.registry.metric(item_id).evidence_expectations:
                evidence_types.add(expectation.evidence_type)
                expectation_ids.append(expectation.expectation_id)
        return tuple(sorted(evidence_types, key=lambda item: item.value)), tuple(dict.fromkeys(expectation_ids))

    def _ready(
        self, qid: str, raw: str, question_type: QuestionType, primary_target: PlanTarget, text: str,
        *, comparison_target: PlanTarget | None = None,
        comparability: ComparabilityStatus = ComparabilityStatus.NOT_APPLICABLE,
        comparability_note: str | None = None,
    ) -> AnalyticalPlan:
        operation = self._operation(question_type, text)
        default_operations = {
            QuestionType.REPORTED_FACT: PlanOperation.LOOKUP,
            QuestionType.CALCULATION: PlanOperation.CALCULATE_CHANGE,
            QuestionType.VARIANCE_DECOMPOSITION: PlanOperation.DECOMPOSE_VARIANCE,
            QuestionType.METRIC_DEFINITION: PlanOperation.DEFINE_METRIC,
            QuestionType.CROSS_COMPANY_COMPARISON: PlanOperation.COMPARE,
            QuestionType.DOCUMENT_CONTEXT: PlanOperation.RETRIEVE_CONTEXT,
            QuestionType.HYBRID_ANALYSIS: PlanOperation.EXPLAIN_WITH_EVIDENCE,
        }
        operation = operation if operation is not PlanOperation.NONE else default_operations[question_type]
        requires_documents = question_type is not QuestionType.METRIC_DEFINITION
        evidence_types, expectations = self._evidence(primary_target.metric_id.value, question_type, operation) if requires_documents else ((), ())
        if comparison_target and requires_documents:
            extra_types, extra_expectations = self._evidence(comparison_target.metric_id.value, question_type, operation)
            evidence_types = tuple(sorted(set(evidence_types) | set(extra_types), key=lambda item: item.value))
            expectations = tuple(dict.fromkeys(expectations + extra_expectations))
        dimensions = [AnalyticalDimension.COMPANY, AnalyticalDimension.METRIC]
        if primary_target.business_scope:
            dimensions.append(AnalyticalDimension.BUSINESS_SCOPE)
        if primary_target.period:
            dimensions.append(AnalyticalDimension.PERIOD)
        if primary_target.comparison_period:
            dimensions.append(AnalyticalDimension.COMPARISON_PERIOD)
        confidence = ConfidenceLevel.MEDIUM if question_type is QuestionType.HYBRID_ANALYSIS or comparability is ComparabilityStatus.LIMITED else ConfidenceLevel.HIGH
        return AnalyticalPlan(
            question_id=qid, raw_question=raw, question_type=question_type,
            status=PlanningStatus.READY, operation=operation,
            ranking_direction=self._ranking_direction(text) if operation is PlanOperation.RANK_CONTRIBUTIONS else None,
            primary_target=primary_target, comparison_target=comparison_target,
            dimensions=tuple(dimensions), required_evidence_types=evidence_types,
            evidence_expectation_ids=expectations,
            requires_documents=requires_documents,
            requires_calculation=operation in {PlanOperation.CALCULATE_CHANGE, PlanOperation.RECONCILE},
            requires_decomposition=(
                question_type is QuestionType.VARIANCE_DECOMPOSITION
                or operation in {PlanOperation.EXPLAIN_WITH_EVIDENCE, PlanOperation.RECONCILE, PlanOperation.RANK_CONTRIBUTIONS}
            ),
            requires_cross_company_comparison=question_type is QuestionType.CROSS_COMPANY_COMPARISON,
            comparability_status=comparability, comparability_note=comparability_note,
            resolution_confidence=confidence,
        )

    @staticmethod
    def _operation(question_type: QuestionType, text: str) -> PlanOperation:
        if any(phrase in text for phrase in ("largest positive", "largest negative", "rank contribution", "rank the contribution")):
            return PlanOperation.RANK_CONTRIBUTIONS
        if "reconcile" in text:
            return PlanOperation.RECONCILE
        if question_type is QuestionType.CALCULATION or any(phrase in text for phrase in _CALCULATION_PHRASES):
            return PlanOperation.CALCULATE_CHANGE
        if question_type is QuestionType.HYBRID_ANALYSIS and any(
            phrase in text for phrase in _NUMERIC_LOOKUP_PHRASES
        ):
            return PlanOperation.LOOKUP
        return PlanOperation.NONE

    @staticmethod
    def _ranking_direction(text: str) -> RankingDirection:
        if "largest negative" in text:
            return RankingDirection.LARGEST_NEGATIVE
        if "largest positive" in text:
            return RankingDirection.LARGEST_POSITIVE
        return RankingDirection.ABSOLUTE_MAGNITUDE

    @staticmethod
    def _clarify(
        qid: str, raw: str, reason: str, missing: tuple[MissingField, ...], question: str
    ) -> AnalyticalPlan:
        return AnalyticalPlan(
            question_id=qid, raw_question=raw, question_type=QuestionType.AMBIGUOUS,
            status=PlanningStatus.NEEDS_CLARIFICATION, operation=PlanOperation.NONE,
            requires_documents=False, requires_calculation=False,
            requires_decomposition=False, requires_cross_company_comparison=False,
            ambiguity_reason=reason, missing_fields=missing, clarification_question=question,
            resolution_confidence=ConfidenceLevel.LOW,
        )

    @staticmethod
    def _unsupported(
        qid: str, raw: str, reason: str, *,
        question_type: QuestionType = QuestionType.UNSUPPORTED,
        primary_target: PlanTarget | None = None,
        comparison_target: PlanTarget | None = None,
        comparability: ComparabilityStatus = ComparabilityStatus.NOT_APPLICABLE,
    ) -> AnalyticalPlan:
        is_cross = question_type is QuestionType.CROSS_COMPANY_COMPARISON
        return AnalyticalPlan(
            question_id=qid, raw_question=raw, question_type=question_type,
            status=PlanningStatus.UNSUPPORTED, operation=PlanOperation.COMPARE if is_cross else PlanOperation.NONE,
            primary_target=primary_target, comparison_target=comparison_target,
            requires_documents=False, requires_calculation=False,
            requires_decomposition=False, requires_cross_company_comparison=is_cross,
            comparability_status=comparability,
            comparability_note=reason if comparability is not ComparabilityStatus.NOT_APPLICABLE else None,
            unsupported_reason=reason, resolution_confidence=ConfidenceLevel.HIGH,
        )
