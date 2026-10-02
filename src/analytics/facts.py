"""Validated loader and lookup API for normalized Step 4 facts."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from src.planning.models import CompanyId, MetricId, PeriodId
from src.planning.registry import PlanningRegistry
from src.schemas.models import ClaimSemantics, PeriodGrain, ProvenanceType, Unit, VerificationStatus

from .models import FactValue


class FactNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class FactRecord:
    fact: FactValue
    expectation_id: str
    bridge_id: str | None
    component_order: int | None
    bridge_role: str | None


class FactStore:
    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root else Path(__file__).resolve().parents[2]
        self.registry = PlanningRegistry(self.root)
        self._scope_types = {
            item.scope_id: (item.company, item.scope_type)
            for item in self.registry.scope_aliases
        }
        self._expectations = {
            item.expectation_id: item
            for metric in self.registry.metrics.values()
            for item in metric.evidence_expectations
        }
        self.records = self._load(self.root / "data/normalized/facts.csv")
        self._index = {
            (record.fact.company, record.fact.metric_id, record.fact.business_scope, record.fact.period): record
            for record in self.records
        }
        if len(self._index) != len(self.records):
            raise ValueError("normalized facts contain duplicate company/metric/scope/period keys")

    def _load(self, path: Path) -> tuple[FactRecord, ...]:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        records: list[FactRecord] = []
        fact_ids: set[int] = set()
        evidence_ids: set[str] = set()
        for row in rows:
            fact_id = int(row["fact_id"])
            if fact_id in fact_ids or row["evidence_id"] in evidence_ids:
                raise ValueError("normalized fact_id and evidence_id values must be unique")
            fact_ids.add(fact_id)
            evidence_ids.add(row["evidence_id"])
            company = CompanyId(row["company_id"])
            metric_id = MetricId(row["metric_id"])
            period = PeriodId(row["period_id"])
            metric = self.registry.metric(metric_id.value)
            if metric.company_id != company.value:
                raise ValueError(f"fact {fact_id} has invalid company/metric ownership")
            if row["scope_id"] not in self._scope_types:
                raise ValueError(f"fact {fact_id} uses unknown scope")
            scope_company, scope_type = self._scope_types[row["scope_id"]]
            if scope_company is not company or scope_type not in metric.allowed_scope_types:
                raise ValueError(f"fact {fact_id} uses incompatible scope")
            grain = PeriodGrain(row["period_grain"])
            if grain not in metric.allowed_period_grains:
                raise ValueError(f"fact {fact_id} uses incompatible period grain")
            if period not in self.registry.availability.get(metric_id.value, frozenset()):
                raise ValueError(f"fact {fact_id} uses unavailable metric period")
            if row["reported_name"] != metric.reported_name or Unit(row["unit"]) is not metric.unit:
                raise ValueError(f"fact {fact_id} does not match catalog name/unit")
            provenance = ProvenanceType(row["provenance_type"])
            semantics = ClaimSemantics(row["claim_semantics"])
            if provenance not in metric.allowed_provenance_types or semantics is not metric.claim_semantics:
                raise ValueError(f"fact {fact_id} violates provenance semantics")
            expectation = self._expectations.get(row["expectation_id"])
            if expectation is None:
                raise ValueError(f"fact {fact_id} references unknown evidence expectation")
            if (
                expectation.metric_id != metric_id.value
                or expectation.company_id != company.value
                or expectation.source_id != row["source_id"]
                or expectation.verification_status.value != row["verification_status"]
            ):
                raise ValueError(f"fact {fact_id} evidence does not match expectation")
            fact = FactValue(
                fact_id=fact_id, company=company, metric_id=metric_id,
                reported_name=row["reported_name"], business_scope=row["scope_id"],
                period=period, period_grain=grain, value=Decimal(row["value"]),
                unit=metric.unit, provenance_type=provenance, claim_semantics=semantics,
                source_ids=(row["source_id"],), evidence_ids=(row["evidence_id"],),
                verification_status=VerificationStatus(row["verification_status"]),
                rounding_tolerance=Decimal(row["rounding_tolerance"]),
            )
            records.append(FactRecord(
                fact=fact, expectation_id=row["expectation_id"],
                bridge_id=row["bridge_id"] or None,
                component_order=int(row["component_order"]) if row["component_order"] else None,
                bridge_role=row["bridge_role"] or None,
            ))
        return tuple(records)

    def get(
        self, company: CompanyId, metric_id: MetricId, scope_id: str, period: PeriodId
    ) -> FactValue:
        record = self._index.get((company, metric_id, scope_id, period))
        if record is None:
            raise FactNotFoundError(
                f"no normalized fact for {company.value}/{metric_id.value}/{scope_id}/{period.value}"
            )
        return record.fact

    def bridge(self, scope_id: str) -> tuple[FactRecord, ...]:
        bridge_id = f"{scope_id}_q2_2026_yoy"
        records = tuple(record for record in self.records if record.bridge_id == bridge_id)
        if not records:
            raise FactNotFoundError(f"no governed bridge for {scope_id}")
        return tuple(sorted(records, key=lambda item: item.component_order if item.component_order is not None else -1))
