import sqlite3

import pytest


def insert_fact(connection, **overrides):
    values = {
        "fact_id": 1,
        "metric_id": "henkel_sales",
        "company_id": "henkel",
        "period_id": "2026-Q2",
        "period_grain": "QUARTER",
        "scope_id": "henkel_group",
        "scope_type": "GROUP",
        "source_id": "henkel_report",
        "value_numeric": 100,
        "unit": "EUR_million",
        "value_type": "DECIMAL",
        "provenance_type": "REPORTED",
        "claim_semantics": "REPORTED_FACT",
        "causal_claim": 0,
        "confidence_class": "HIGH",
        "calculation_run_id": None,
        "calculation_status": None,
        "extraction_method": "test",
    }
    values.update(overrides)
    connection.execute(
        """
        INSERT INTO fact_reported_metric(
            fact_id, metric_id, company_id, period_id, period_grain,
            scope_id, scope_type, source_id, value_numeric, unit, value_type,
            provenance_type, claim_semantics, causal_claim, confidence_class,
            calculation_run_id, calculation_status, extraction_method
        ) VALUES (
            :fact_id, :metric_id, :company_id, :period_id, :period_grain,
            :scope_id, :scope_type, :source_id, :value_numeric, :unit, :value_type,
            :provenance_type, :claim_semantics, :causal_claim, :confidence_class,
            :calculation_run_id, :calculation_status, :extraction_method
        )
        """,
        values,
    )


def add_successful_calculation_lineage(connection, *, result=120):
    insert_fact(connection, fact_id=10)
    connection.execute(
        "INSERT INTO calculation_rule VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("test_sum", "Test sum", "1.0.0", "python:test_sum", "henkel_calc", "henkel", 1, "Test rule"),
    )
    connection.execute(
        "INSERT INTO calculation_run VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "run-1", "test_sum", "1.0.0", "henkel_calc", "henkel",
            "2026-09-24T00:00:00Z", "python", "3.14", "sha256:test", result, "SUCCESS",
        ),
    )
    connection.execute(
        "INSERT INTO calculation_input VALUES (?, ?, ?, ?, ?)",
        ("run-1", "henkel", 10, "input", 0),
    )


def test_valid_quarter_and_half_year_facts_are_accepted(contract_db):
    insert_fact(contract_db, fact_id=1)
    insert_fact(
        contract_db, fact_id=2, period_id="2026-H1", period_grain="HALF_YEAR", value_numeric=200
    )
    assert contract_db.execute("SELECT COUNT(*) FROM fact_reported_metric").fetchone()[0] == 2


@pytest.mark.negative
def test_henkel_metric_with_mercedes_company_is_rejected(contract_db):
    with pytest.raises(sqlite3.IntegrityError):
        insert_fact(
            contract_db, company_id="mercedes_benz_group", scope_id="mercedes_group",
            source_id="mercedes_report",
        )


@pytest.mark.negative
def test_henkel_metric_with_mercedes_source_is_rejected(contract_db):
    with pytest.raises(sqlite3.IntegrityError):
        insert_fact(contract_db, source_id="mercedes_report")


@pytest.mark.negative
def test_mercedes_scope_with_henkel_metric_is_rejected(contract_db):
    with pytest.raises(sqlite3.IntegrityError):
        insert_fact(contract_db, scope_id="mercedes_cars", scope_type="SEGMENT")


@pytest.mark.negative
@pytest.mark.parametrize(
    ("period_id", "period_grain"),
    [("2026-FY", "YEAR"), ("2026-06-30", "POINT_IN_TIME")],
)
def test_unsupported_metric_period_grain_is_rejected(contract_db, period_id, period_grain):
    with pytest.raises(sqlite3.IntegrityError):
        insert_fact(contract_db, period_id=period_id, period_grain=period_grain)


@pytest.mark.negative
@pytest.mark.parametrize(
    ("field", "value"),
    [("unit", "vehicle"), ("value_type", "INTEGER")],
)
def test_invalid_unit_or_value_type_is_rejected(contract_db, field, value):
    with pytest.raises(sqlite3.IntegrityError):
        insert_fact(contract_db, **{field: value})


@pytest.mark.negative
def test_invalid_provenance_is_rejected(contract_db):
    with pytest.raises(sqlite3.IntegrityError):
        insert_fact(contract_db, provenance_type="INVENTED")


@pytest.mark.negative
def test_management_attribution_cannot_be_causal(contract_db):
    with pytest.raises(sqlite3.IntegrityError):
        insert_fact(
            contract_db, metric_id="mercedes_bridge", company_id="mercedes_benz_group",
            period_id="2026-Q2-YOY", period_grain="QUARTER_YOY",
            scope_id="mercedes_cars", scope_type="SEGMENT",
            source_id="mercedes_presentation", provenance_type="MANAGEMENT_ATTRIBUTED",
            claim_semantics="MANAGEMENT_ATTRIBUTION", causal_claim=1,
            confidence_class="MEDIUM",
        )


@pytest.mark.negative
def test_calculated_fact_without_lineage_is_rejected(contract_db):
    with pytest.raises(sqlite3.IntegrityError):
        insert_fact(
            contract_db, metric_id="henkel_calc", period_id="2026-H1",
            period_grain="HALF_YEAR", source_id=None, value_numeric=120,
            provenance_type="CALCULATED", claim_semantics="DERIVED_CALCULATION",
            confidence_class="MEDIUM",
        )


def test_calculated_fact_with_valid_lineage_is_accepted(contract_db):
    add_successful_calculation_lineage(contract_db)
    insert_fact(
        contract_db, fact_id=11, metric_id="henkel_calc", period_id="2026-H1",
        period_grain="HALF_YEAR", source_id=None, value_numeric=120,
        provenance_type="CALCULATED", claim_semantics="DERIVED_CALCULATION",
        confidence_class="MEDIUM", calculation_run_id="run-1", calculation_status="SUCCESS",
    )
    assert contract_db.execute("SELECT calculation_run_id FROM fact_reported_metric WHERE fact_id=11").fetchone()[0] == "run-1"


@pytest.mark.negative
def test_calculation_run_result_mismatch_is_rejected(contract_db):
    add_successful_calculation_lineage(contract_db, result=120)
    with pytest.raises(sqlite3.IntegrityError):
        insert_fact(
            contract_db, fact_id=11, metric_id="henkel_calc", period_id="2026-H1",
            period_grain="HALF_YEAR", source_id=None, value_numeric=121,
            provenance_type="CALCULATED", claim_semantics="DERIVED_CALCULATION",
            confidence_class="MEDIUM", calculation_run_id="run-1", calculation_status="SUCCESS",
        )


@pytest.mark.negative
def test_calculation_run_wrong_output_metric_is_rejected(contract_db):
    add_successful_calculation_lineage(contract_db, result=120)
    contract_db.execute(
        """
        INSERT INTO dim_metric VALUES (
            'henkel_calc_other', 'henkel', 'Other calculated value', 'test_calculation',
            'Test only', 'Other deterministic output', 'EUR_million', 'DECIMAL',
            'DETERMINISTIC_CALCULATION', 'test_calculation', 0,
            'Test-only contract fixture', 0, 0, 0
        )
        """
    )
    contract_db.execute("INSERT INTO metric_allowed_period_grain VALUES ('henkel_calc_other', 'HALF_YEAR')")
    contract_db.execute("INSERT INTO metric_allowed_scope_type VALUES ('henkel_calc_other', 'GROUP')")
    contract_db.execute(
        "INSERT INTO metric_allowed_provenance VALUES ('henkel_calc_other', 'CALCULATED', 'DERIVED_CALCULATION', 0)"
    )
    with pytest.raises(sqlite3.IntegrityError):
        insert_fact(
            contract_db, fact_id=11, metric_id="henkel_calc_other", period_id="2026-H1",
            period_grain="HALF_YEAR", source_id=None, value_numeric=120,
            provenance_type="CALCULATED", claim_semantics="DERIVED_CALCULATION",
            confidence_class="MEDIUM", calculation_run_id="run-1", calculation_status="SUCCESS",
        )


@pytest.mark.negative
def test_evidence_with_mismatched_source_company_is_rejected(contract_db):
    insert_fact(contract_db)
    with pytest.raises(sqlite3.IntegrityError):
        contract_db.execute(
            """
            INSERT INTO fact_evidence VALUES (
                'e-1', 1, 'henkel_sales', 'henkel', 'mercedes_revenue_page3',
                'mercedes_report', 'Key figures table', 'PDF page 3', '',
                'PRIMARY_NUMERIC', 'VERIFIED', ''
            )
            """
        )


@pytest.mark.negative
def test_duplicate_evidence_identifier_is_rejected(contract_db):
    insert_fact(contract_db)
    evidence = (
        "e-1", 1, "henkel_sales", "henkel", "henkel_sales_page7", "henkel_report",
        "Sales development table", "PDF page 7", "", "PRIMARY_NUMERIC", "VERIFIED", "",
    )
    contract_db.execute("INSERT INTO fact_evidence VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", evidence)
    with pytest.raises(sqlite3.IntegrityError):
        contract_db.execute("INSERT INTO fact_evidence VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", evidence)
