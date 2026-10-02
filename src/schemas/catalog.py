"""Load and cross-validate the governed CSV catalog into Python contracts."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from .models import EvidenceExpectation, EvidenceType, MetricDefinition, VerificationStatus


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"{path} has no header")
        return list(reader)


def load_metric_catalog(config_dir: Path, source_manifest: Path) -> dict[str, MetricDefinition]:
    catalog_rows = _rows(config_dir / "metric_catalog.csv")
    period_rows = _rows(config_dir / "metric_allowed_period_grains.csv")
    scope_rows = _rows(config_dir / "metric_allowed_scope_types.csv")
    evidence_rows = _rows(config_dir / "metric_evidence_expectations.csv")
    source_rows = _rows(source_manifest)

    source_companies = {row["source_id"]: row["company"] for row in source_rows}
    periods: dict[str, list[str]] = defaultdict(list)
    scopes: dict[str, list[str]] = defaultdict(list)
    evidence: dict[str, list[EvidenceExpectation]] = defaultdict(list)
    for row in period_rows:
        periods[row["metric_id"]].append(row["period_grain"])
    for row in scope_rows:
        scopes[row["metric_id"]].append(row["scope_type"])

    expectation_ids: set[str] = set()
    for row in evidence_rows:
        if row["expectation_id"] in expectation_ids:
            raise ValueError(f"duplicate evidence expectation_id {row['expectation_id']}")
        expectation_ids.add(row["expectation_id"])
        if row["source_id"] not in source_companies:
            raise ValueError(f"unknown source_id {row['source_id']}")
        if source_companies[row["source_id"]] != row["company"]:
            raise ValueError(f"evidence source/company mismatch for {row['expectation_id']}")
        item = EvidenceExpectation(
            expectation_id=row["expectation_id"], metric_id=row["metric_id"],
            company_id=row["company"], source_id=row["source_id"],
            source_location=row["source_location"],
            source_page_or_sheet=row["source_page_or_sheet"],
            source_cell_or_range=row["source_cell_or_range"],
            evidence_type=EvidenceType(row["evidence_type"]),
            verification_status=VerificationStatus(row["verification_status"]),
            note=row["note"],
        )
        evidence[item.metric_id].append(item)

    definitions: dict[str, MetricDefinition] = {}
    for row in catalog_rows:
        metric_id = row["metric_id"]
        if metric_id in definitions:
            raise ValueError(f"duplicate metric_id {metric_id}")
        definitions[metric_id] = MetricDefinition.from_catalog_row(
            row, allowed_period_grains=periods[metric_id],
            allowed_scope_types=scopes[metric_id],
            evidence_expectations=evidence[metric_id],
        )
    unknown = (set(periods) | set(scopes) | set(evidence)) - set(definitions)
    if unknown:
        raise ValueError(f"association rows reference unknown metrics: {sorted(unknown)}")
    return definitions
