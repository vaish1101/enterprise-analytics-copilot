"""Public-safe product catalog: display labels and numeric fact provenance.

Everything here is read from the governed catalogs that the analytics layer
already validates. Nothing is inferred from prose, and only public-safe fields
(titles, official URLs, page or sheet locations) are ever exposed.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re

from src.analytics.facts import FactRecord, FactStore


_PERIOD = re.compile(r"^(Q[1-4]|H[12]|FY)_(\d{4})$")


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    company_id: str
    source_title: str
    official_url: str
    source_type: str
    reporting_period: str


class ProductCatalog:
    """Loaded once per process; every lookup is a pure dictionary read."""

    def __init__(self, root: Path):
        self.facts = FactStore(root)
        self.registry = self.facts.registry
        self.records: dict[int, FactRecord] = {record.fact.fact_id: record for record in self.facts.records}
        self.expectations = {
            item.expectation_id: item
            for metric in self.registry.metrics.values()
            for item in metric.evidence_expectations
        }
        self.sources = {
            row["source_id"]: SourceRecord(
                source_id=row["source_id"], company_id=row["company"], source_title=row["source_title"],
                official_url=row["official_url"], source_type=row["source_type"],
                reporting_period=row["reporting_period"],
            )
            for row in _read(root / "data/source_manifest.csv")
        }
        self.scope_labels = {row["scope_id"]: row for row in _read(root / "config/scope_labels.csv")}
        # Display names for business users. The issuer's reported name stays available;
        # some reported names are table fragments ("Organic", "Of which price").
        self.metric_display = {row["metric_id"]: row["display_label"] for row in _read(root / "config/metric_display_labels.csv")}
        missing_metrics = set(self.registry.metrics) - set(self.metric_display)
        if missing_metrics:
            raise ValueError(f"metric display labels missing for {sorted(missing_metrics)}")
        known_scopes = {item.scope_id for item in self.registry.scope_aliases}
        missing = known_scopes - set(self.scope_labels)
        if missing:
            raise ValueError(f"scope labels missing for {sorted(missing)}")
        # A company reports on a fiscal calendar when its governed sources say so.
        self.fiscal_companies = frozenset(
            source.company_id for source in self.sources.values()
            if re.search(r"\bFY\b", source.reporting_period)
        )

    # ---- labels -------------------------------------------------------------

    def period_label(self, company_id: str, period_id: str, grain: str) -> str:
        match = _PERIOD.match(period_id)
        if not match:
            raise ValueError(f"unrecognized governed period {period_id}")
        part, year = match.group(1), int(match.group(2))
        fiscal = company_id in self.fiscal_companies

        def label(y: int) -> str:
            return f"{part} FY{y}" if fiscal else f"{part} {y}"

        if grain == "QUARTER_YOY":
            return f"{label(year)} vs {label(year - 1)}"
        return label(year)

    def labels(self) -> dict:
        metrics = {
            metric_id: {"label": self.metric_display[metric_id], "reported_name": metric.reported_name,
                        "unit": metric.unit.value, "company_id": metric.company_id}
            for metric_id, metric in sorted(self.registry.metrics.items())
        }
        scope_types = {item.scope_id: item.scope_type.value for item in self.registry.scope_aliases}
        scopes = {
            scope_id: {"label": row["label"], "company_id": row["company_id"], "scope_type": scope_types.get(scope_id)}
            for scope_id, row in sorted(self.scope_labels.items())
        }
        seen: set[tuple[str, str, str]] = set()
        periods = []
        for record in self.facts.records:
            fact = record.fact
            key = (fact.company.value, fact.period.value, fact.period_grain.value)
            if key in seen:
                continue
            seen.add(key)
            periods.append({
                "company_id": key[0], "period_id": key[1], "period_grain": key[2],
                "label": self.period_label(*key), "fiscal": key[0] in self.fiscal_companies,
            })
        periods.sort(key=lambda item: (item["company_id"], item["period_id"], item["period_grain"]))
        return {"metrics": metrics, "scopes": scopes, "periods": periods}

    # ---- fact provenance ----------------------------------------------------

    def bridge_position(self, fact_id: int) -> tuple[str | None, int | None]:
        record = self.records.get(fact_id)
        return (record.bridge_role, record.component_order) if record else (None, None)

    def fact_source(self, fact_id: int) -> dict | None:
        record = self.records.get(fact_id)
        if record is None:
            return None
        expectation = self.expectations.get(record.expectation_id)
        source_id = record.fact.source_ids[0]
        source = self.sources.get(source_id)
        if expectation is None or source is None:
            return None
        return {
            "fact_id": fact_id,
            "source_id": source.source_id,
            "source_title": source.source_title,
            "official_url": source.official_url,
            "source_type": source.source_type,
            "location": expectation.source_location,
            "page_or_sheet": expectation.source_page_or_sheet,
            "cell_or_range": expectation.source_cell_or_range or None,
            "evidence_type": expectation.evidence_type.value,
        }


@lru_cache(maxsize=4)
def product_catalog(root: Path) -> ProductCatalog:
    return ProductCatalog(root)
