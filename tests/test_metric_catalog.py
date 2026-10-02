import csv
from collections import defaultdict
from pathlib import Path

import pytest

from src.schemas.catalog import load_metric_catalog
from src.schemas.models import (
    CalculationType, ClaimSemantics, EvidenceExpectation, EvidenceType,
    MetricDefinition, PeriodGrain, ProvenanceType, ScopeType, VerificationStatus,
)


ROOT = Path(__file__).resolve().parents[1]


def rows(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_catalog_loads_all_verified_metrics_into_python_contracts():
    catalog = load_metric_catalog(ROOT / "config", ROOT / "data/source_manifest.csv")
    assert len(catalog) == 27
    assert all(metric.allowed_period_grains for metric in catalog.values())
    assert all(metric.allowed_scope_types for metric in catalog.values())
    assert all(metric.evidence_expectations for metric in catalog.values())


def test_catalog_has_normalized_fields_not_pipe_pseudo_types():
    catalog_rows = rows(ROOT / "config/metric_catalog.csv")
    assert len(catalog_rows) == 27
    assert "period_grain" not in catalog_rows[0]
    assert "business_scope" not in catalog_rows[0]
    for path, field in (
        (ROOT / "config/metric_allowed_period_grains.csv", "period_grain"),
        (ROOT / "config/metric_allowed_scope_types.csv", "scope_type"),
    ):
        assert all("|" not in row[field] for row in rows(path))


def test_management_metrics_are_noncausal_management_attributions():
    catalog = load_metric_catalog(ROOT / "config", ROOT / "data/source_manifest.csv")
    management = [
        metric for metric in catalog.values()
        if ProvenanceType.MANAGEMENT_ATTRIBUTED in metric.allowed_provenance_types
    ]
    assert management
    assert all(metric.claim_semantics is ClaimSemantics.MANAGEMENT_ATTRIBUTION for metric in management)
    assert all(metric.causal_claim_allowed is False for metric in management)


def test_no_cross_company_comparability_is_implied():
    catalog = load_metric_catalog(ROOT / "config", ROOT / "data/source_manifest.csv")
    assert all(not metric.comparable_across_companies for metric in catalog.values())


def test_mercedes_exact_combined_bridge_label_is_preserved():
    catalog = load_metric_catalog(ROOT / "config", ROOT / "data/source_manifest.csv")
    assert catalog["mercedes_bridge_volume_structure_net_pricing"].reported_name == "Volume / structure / net pricing"


@pytest.mark.negative
def test_split_mercedes_bridge_pseudo_metrics_do_not_exist():
    catalog = load_metric_catalog(ROOT / "config", ROOT / "data/source_manifest.csv")
    forbidden_ids = {
        "mercedes_bridge_volume", "mercedes_bridge_structure", "mercedes_bridge_net_pricing"
    }
    forbidden_labels = {"Volume", "Structure", "Net pricing"}
    assert forbidden_ids.isdisjoint(catalog)
    assert forbidden_labels.isdisjoint({metric.reported_name for metric in catalog.values()})


def test_evidence_expectations_are_document_specific_and_company_compatible():
    evidence_rows = rows(ROOT / "config/metric_evidence_expectations.csv")
    source_company = {
        row["source_id"]: row["company"] for row in rows(ROOT / "data/source_manifest.csv")
    }
    assert len({row["expectation_id"] for row in evidence_rows}) == len(evidence_rows)
    assert all(row["source_id"] and row["source_location"] and row["source_page_or_sheet"] for row in evidence_rows)
    assert all(source_company[row["source_id"]] == row["company"] for row in evidence_rows)
    sources_by_metric = defaultdict(set)
    for row in evidence_rows:
        sources_by_metric[row["metric_id"]].add(row["source_id"])
    assert len(sources_by_metric["mercedes_revenue"]) == 3
    assert len(sources_by_metric["mercedes_adjusted_ebit"]) == 3


@pytest.mark.negative
def test_csv_to_python_rejects_invalid_value_type():
    expectation = EvidenceExpectation(
        "e", "m", "henkel", "s", "table", "PDF page 1", "",
        EvidenceType.PRIMARY_NUMERIC, VerificationStatus.VERIFIED,
    )
    row = {
        "metric_id": "m", "company": "henkel", "reported_name": "Metric",
        "canonical_family": "metric", "description": "Description", "definition": "Definition",
        "unit": "EUR_million", "value_type": "FLOAT", "allowed_provenance_type": "REPORTED",
        "claim_semantics": "REPORTED_FACT", "calculation_type": "REPORTED",
        "comparability_group": "m", "comparable_across_companies": "false",
        "comparability_notes": "Issuer-specific", "rounding_tolerance": "0",
        "evidence_required": "true", "causal_claim_allowed": "false", "notes": "",
    }
    with pytest.raises(ValueError):
        MetricDefinition.from_catalog_row(
            row, allowed_period_grains=[PeriodGrain.QUARTER],
            allowed_scope_types=[ScopeType.GROUP], evidence_expectations=[expectation],
        )


@pytest.mark.negative
def test_csv_to_python_rejects_pipe_separated_period_grain():
    expectation = EvidenceExpectation(
        "e", "m", "henkel", "s", "table", "PDF page 1", "",
        EvidenceType.PRIMARY_NUMERIC, VerificationStatus.VERIFIED,
    )
    row = {
        "metric_id": "m", "company": "henkel", "reported_name": "Metric",
        "canonical_family": "metric", "description": "Description", "definition": "Definition",
        "unit": "EUR_million", "value_type": "DECIMAL", "allowed_provenance_type": "REPORTED",
        "claim_semantics": "REPORTED_FACT", "calculation_type": CalculationType.REPORTED.value,
        "comparability_group": "m", "comparable_across_companies": "false",
        "comparability_notes": "Issuer-specific", "rounding_tolerance": "0",
        "evidence_required": "true", "causal_claim_allowed": "false", "notes": "",
    }
    with pytest.raises(ValueError):
        MetricDefinition.from_catalog_row(
            row, allowed_period_grains=["quarter|half_year"],
            allowed_scope_types=[ScopeType.GROUP], evidence_expectations=[expectation],
        )
