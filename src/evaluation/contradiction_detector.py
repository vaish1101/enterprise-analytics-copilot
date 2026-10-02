"""Conservative metadata-aligned structured/document contradiction detection."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re

from pydantic import BaseModel, ConfigDict

from src.analytics.models import AnalyticalResult, FactValue
from src.retrieval.models import EvidenceResult


class NumericMention(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    evidence_unit_id: str
    company_id: str
    metric_id: str
    business_scope: str
    period: str
    value: Decimal
    unit: str


class EvidenceConflict(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    fact_id: int
    evidence_unit_id: str
    conflict_type: str
    structured_value: Decimal
    documentary_value: Decimal
    structured_unit: str
    documentary_unit: str


_MONEY = re.compile(r"(?:€\s*)?([+-]?\d[\d,]*(?:\.\d+)?)\s*(?:million|mn|€m)\b", re.I)
_PERCENT = re.compile(r"([+-]?\d+(?:\.\d+)?)\s*%")


def extract_numeric_mentions(evidence: EvidenceResult) -> tuple[NumericMention, ...]:
    """Extract only when metadata identifies exactly one metric/scope/period."""
    if len(evidence.metric_ids) != 1 or len(evidence.business_scopes) != 1 or len(evidence.reporting_periods) != 1:
        return ()
    patterns = ((_MONEY, "EUR_million"), (_PERCENT, "percentage_point"))
    mentions = []
    for pattern, unit in patterns:
        for match in pattern.finditer(evidence.text):
            try:
                value = Decimal(match.group(1).replace(",", ""))
            except InvalidOperation:
                continue
            mentions.append(NumericMention(
                evidence_unit_id=evidence.evidence_unit_id, company_id=evidence.company_id,
                metric_id=evidence.metric_ids[0], business_scope=evidence.business_scopes[0],
                period=evidence.reporting_periods[0], value=value, unit=unit,
            ))
    return tuple(mentions)


class ContradictionDetector:
    version = "conservative-metadata-numeric-v1.0.0"

    def detect(self, analytics: AnalyticalResult | None,
               evidence: tuple[EvidenceResult, ...]) -> tuple[EvidenceConflict, ...]:
        if analytics is None:
            return ()
        facts = [analytics.primary_result, analytics.comparison_result,
                 *analytics.supporting_results, *analytics.decomposition_components]
        facts = [fact for fact in facts if fact is not None]
        conflicts = []
        for item in evidence:
            for mention in extract_numeric_mentions(item):
                matches = [fact for fact in facts if self._metadata_matches(fact, mention)]
                for fact in matches:
                    if mention.unit != fact.unit.value:
                        conflicts.append(self._conflict(fact, mention, "UNIT_MISMATCH"))
                    elif abs(mention.value - fact.value) > fact.rounding_tolerance:
                        conflicts.append(self._conflict(fact, mention, "VALUE_MISMATCH"))
        return tuple(conflicts)

    @staticmethod
    def _metadata_matches(fact: FactValue, mention: NumericMention) -> bool:
        return (
            fact.company.value == mention.company_id
            and fact.metric_id.value == mention.metric_id
            and fact.business_scope == mention.business_scope
            and fact.period.value == mention.period
        )

    @staticmethod
    def _conflict(fact: FactValue, mention: NumericMention, conflict_type: str) -> EvidenceConflict:
        return EvidenceConflict(
            fact_id=fact.fact_id, evidence_unit_id=mention.evidence_unit_id,
            conflict_type=conflict_type, structured_value=fact.value,
            documentary_value=mention.value, structured_unit=fact.unit.value,
            documentary_unit=mention.unit,
        )

