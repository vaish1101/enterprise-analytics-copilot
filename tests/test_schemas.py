import csv
import sqlite3
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from src.schemas.catalog import load_metric_catalog
from src.schemas.models import (
    CalculationInput, CalculationRun, CalculationRunStatus, ClaimSemantics,
    ConfidenceLevel, MetricFact, PeriodGrain, ProvenanceType, ScopeType,
    Unit, ValueType, deterministic_confidence,
)


ROOT = Path(__file__).resolve().parents[1]


def vocabulary_values(name):
    with (ROOT / "config/controlled_vocabularies.csv").open(newline="", encoding="utf-8") as handle:
        return {row["value"] for row in csv.DictReader(handle) if row["vocabulary"] == name}


def test_python_and_csv_controlled_vocabularies_match():
    assert vocabulary_values("period_grain") == {value.value for value in PeriodGrain}
    assert vocabulary_values("provenance_type") == {value.value for value in ProvenanceType}
    assert vocabulary_values("claim_semantics") == {value.value for value in ClaimSemantics}
    assert vocabulary_values("value_type") == {value.value for value in ValueType}
    assert vocabulary_values("scope_type") == {value.value for value in ScopeType}
    assert vocabulary_values("confidence_class") == {value.value for value in ConfidenceLevel}
    with (ROOT / "config/provenance_classes.csv").open(newline="", encoding="utf-8") as handle:
        provenance_policy = list(csv.DictReader(handle))
    assert {row["provenance_type"] for row in provenance_policy} == {value.value for value in ProvenanceType}
    management = next(row for row in provenance_policy if row["provenance_type"] == "MANAGEMENT_ATTRIBUTED")
    assert management["maximum_confidence_when_verified"] == "MEDIUM"
    assert management["causal_claim_allowed"] == "false"


def test_sql_vocabularies_match_python():
    connection = sqlite3.connect(":memory:")
    connection.executescript((ROOT / "src/schemas/normalized_schema.sql").read_text(encoding="utf-8"))
    try:
        assert {row[0] for row in connection.execute("SELECT value FROM ref_period_grain")} == {value.value for value in PeriodGrain}
        assert {row[0] for row in connection.execute("SELECT value FROM ref_provenance_type")} == {value.value for value in ProvenanceType}
        assert {row[0] for row in connection.execute("SELECT value FROM ref_claim_semantics")} == {value.value for value in ClaimSemantics}
    finally:
        connection.close()


def test_confidence_is_separate_from_causality_and_support():
    assert deterministic_confidence([ProvenanceType.REPORTED]) is ConfidenceLevel.HIGH
    assert deterministic_confidence([ProvenanceType.MANAGEMENT_ATTRIBUTED]) is ConfidenceLevel.MEDIUM
    assert deterministic_confidence([ProvenanceType.CALCULATED]) is ConfidenceLevel.MEDIUM
    assert deterministic_confidence([ProvenanceType.INTERPRETATION]) is ConfidenceLevel.LOW
    assert deterministic_confidence([ProvenanceType.REPORTED], evidence_complete=False) is ConfidenceLevel.LOW
    assert deterministic_confidence([ProvenanceType.UNSUPPORTED]) is None


@pytest.mark.negative
def test_successful_calculation_run_requires_inputs():
    with pytest.raises(ValueError):
        CalculationRun(
            run_id="r", rule_id="rule", rule_version="1", output_metric_id="m",
            company_id="henkel", executed_at=datetime.now(), execution_engine="python",
            execution_version="3", input_digest="sha256:x", result_value=Decimal("1"),
            status=CalculationRunStatus.SUCCESS, inputs=(),
        )


@pytest.mark.negative
def test_management_metric_fact_cannot_be_marked_causal():
    catalog = load_metric_catalog(ROOT / "config", ROOT / "data/source_manifest.csv")
    metric = catalog["henkel_price_contribution"]
    fact = MetricFact(
        fact_id=1, metric_id=metric.metric_id, company_id="henkel", period_id="p",
        scope_id="s", value=Decimal("1.1"), unit=Unit.PERCENTAGE_POINT,
        value_type=ValueType.DECIMAL, provenance_type=ProvenanceType.MANAGEMENT_ATTRIBUTED,
        claim_semantics=ClaimSemantics.MANAGEMENT_ATTRIBUTION, causal_claim=True,
        source_id="henkel_h1_2026_financial_report",
    )
    from src.schemas.models import BusinessScope, ReportingPeriod, SourceDocument
    from datetime import date
    with pytest.raises(ValueError):
        fact.validate_against(
            metric,
            ReportingPeriod("p", "Q2", PeriodGrain.QUARTER, date(2026, 4, 1), date(2026, 6, 30)),
            BusinessScope("s", "henkel", ScopeType.GROUP, "Henkel Group"),
            SourceDocument(
                "henkel_h1_2026_financial_report", "henkel", "https://www.henkel.com/report.pdf", "report.pdf"
            ),
        )
