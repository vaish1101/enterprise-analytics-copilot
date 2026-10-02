"""Governed query construction and expansion."""

from __future__ import annotations

import csv
from pathlib import Path

from src.planning.models import AnalyticalPlan, PlanningStatus

from .models import RetrievalQuery


class GovernedVocabulary:
    def __init__(self, root: Path):
        self.metric_aliases: dict[tuple[str, str], set[str]] = {}
        with (root / "config/metric_aliases.csv").open() as handle:
            for row in csv.DictReader(handle):
                self.metric_aliases.setdefault((row["company_id"], row["metric_id"]), set()).add(row["alias"])
        with (root / "config/metric_catalog.csv").open() as handle:
            for row in csv.DictReader(handle):
                self.metric_aliases.setdefault((row["company"], row["metric_id"]), set()).update(
                    {row["reported_name"], row["canonical_family"]}
                )

    def expand(self, company_id: str, metric_ids: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted({alias for metric_id in metric_ids for alias in self.metric_aliases.get((company_id, metric_id), set())}))


def query_from_plan(plan: AnalyticalPlan) -> RetrievalQuery:
    if plan.status is not PlanningStatus.READY or plan.primary_target is None:
        raise ValueError("document retrieval requires a READY governed plan")
    target = plan.primary_target
    periods = tuple(value.value for value in (target.period, target.comparison_period) if value is not None)
    scopes = (target.business_scope,) if target.business_scope else ()
    return RetrievalQuery(
        query_id=plan.question_id,
        raw_question=plan.raw_question,
        company_id=target.company.value,
        reporting_periods=periods,
        business_scopes=scopes,
        metric_ids=(target.metric_id.value,),
    )
