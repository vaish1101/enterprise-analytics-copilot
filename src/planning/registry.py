"""Load and validate controlled aliases against the hardened Step 2.5 catalog."""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from src.schemas.catalog import load_metric_catalog
from src.schemas.models import MetricDefinition, PeriodGrain, ScopeType

from .models import CompanyId, PeriodId


@dataclass(frozen=True)
class ScopeAlias:
    alias: str
    company: CompanyId
    scope_id: str
    scope_type: ScopeType


@dataclass(frozen=True)
class PeriodAlias:
    alias: str
    period: PeriodId
    grain: PeriodGrain


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"{path} has no header")
        return list(reader)


class PlanningRegistry:
    def __init__(self, root: Path):
        self.root = root
        config = root / "config"
        self.metrics = load_metric_catalog(config, root / "data/source_manifest.csv")
        self.company_aliases = tuple(
            (row["alias"].lower(), CompanyId(row["company_id"]))
            for row in _read(config / "company_aliases.csv")
        )
        self.metric_aliases = tuple(
            (row["alias"].lower(), CompanyId(row["company_id"]), row["metric_id"])
            for row in _read(config / "metric_aliases.csv")
        )
        self.scope_aliases = tuple(
            ScopeAlias(row["alias"].lower(), CompanyId(row["company_id"]), row["scope_id"], ScopeType(row["scope_type"]))
            for row in _read(config / "business_scope_aliases.csv")
        )
        self.period_aliases = tuple(
            PeriodAlias(row["alias"].lower(), PeriodId(row["period_id"]), PeriodGrain(row["period_grain"]))
            for row in _read(config / "period_aliases.csv")
        )
        availability: dict[str, set[PeriodId]] = defaultdict(set)
        for row in _read(config / "metric_period_availability.csv"):
            availability[row["metric_id"]].add(PeriodId(row["period_id"]))
        self.availability = {key: frozenset(value) for key, value in availability.items()}
        fact_rows = _read(root / "data/normalized/facts.csv")
        self.runtime_fact_keys = frozenset(
            (
                CompanyId(row["company_id"]), row["metric_id"],
                row["scope_id"], PeriodId(row["period_id"]),
            )
            for row in fact_rows
        )
        self._validate()

    def _validate(self) -> None:
        metric_ids = set(self.metrics)
        unknown_aliases = {row[2] for row in self.metric_aliases} - metric_ids
        unknown_availability = set(self.availability) - metric_ids
        if unknown_aliases or unknown_availability:
            raise ValueError(f"planning config references unknown metrics: {sorted(unknown_aliases | unknown_availability)}")
        for _, company, metric_id in self.metric_aliases:
            if self.metrics[metric_id].company_id != company.value:
                raise ValueError(f"metric alias company mismatch for {metric_id}")
        for metric_id, periods in self.availability.items():
            allowed = self.metrics[metric_id].allowed_period_grains
            for period in periods:
                grain = next(item.grain for item in self.period_aliases if item.period is period)
                if grain not in allowed and PeriodGrain.QUARTER_YOY not in allowed:
                    raise ValueError(f"period {period.value} is incompatible with {metric_id}")
        for company, metric_id, scope_id, period in self.runtime_fact_keys:
            if metric_id not in self.metrics or self.metrics[metric_id].company_id != company.value:
                raise ValueError(f"runtime fact coverage references invalid metric ownership: {metric_id}")
            if scope_id not in {item.scope_id for item in self.scope_aliases if item.company is company}:
                raise ValueError(f"runtime fact coverage references unknown scope: {scope_id}")
            if period not in self.availability.get(metric_id, frozenset()):
                raise ValueError(f"runtime fact coverage references unavailable period: {metric_id}/{period.value}")

    def metric(self, metric_id: str) -> MetricDefinition:
        return self.metrics[metric_id]

    def has_runtime_fact(
        self, company: CompanyId, metric_id: str, scope_id: str, period: PeriodId
    ) -> bool:
        return (company, metric_id, scope_id, period) in self.runtime_fact_keys
