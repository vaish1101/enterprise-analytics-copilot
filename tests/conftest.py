from pathlib import Path
import sqlite3

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def contract_db():
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript((ROOT / "src/schemas/normalized_schema.sql").read_text(encoding="utf-8"))
    connection.executescript(
        """
        INSERT INTO dim_company VALUES ('henkel', 'Henkel AG & Co. KGaA');
        INSERT INTO dim_company VALUES ('mercedes_benz_group', 'Mercedes-Benz Group AG');

        INSERT INTO dim_reporting_period VALUES ('2026-Q2', 'Q2 2026', 'QUARTER', '2026-04-01', '2026-06-30');
        INSERT INTO dim_reporting_period VALUES ('2026-H1', 'H1 2026', 'HALF_YEAR', '2026-01-01', '2026-06-30');
        INSERT INTO dim_reporting_period VALUES ('2026-FY', 'FY 2026', 'YEAR', '2026-01-01', '2026-12-31');
        INSERT INTO dim_reporting_period VALUES ('2026-06-30', '30 June 2026', 'POINT_IN_TIME', '2026-06-30', '2026-06-30');
        INSERT INTO dim_reporting_period VALUES ('2026-Q2-YOY', 'Q2 2026 vs Q2 2025', 'QUARTER_YOY', '2025-04-01', '2026-06-30');

        INSERT INTO dim_business_scope(scope_id, company_id, scope_type, scope_name)
            VALUES ('henkel_group', 'henkel', 'GROUP', 'Henkel Group');
        INSERT INTO dim_business_scope(scope_id, company_id, scope_type, scope_name)
            VALUES ('mercedes_group', 'mercedes_benz_group', 'GROUP', 'Mercedes-Benz Group');
        INSERT INTO dim_business_scope(scope_id, company_id, scope_type, scope_name)
            VALUES ('mercedes_cars', 'mercedes_benz_group', 'SEGMENT', 'Mercedes-Benz Cars');

        INSERT INTO dim_source_document VALUES (
            'henkel_report', 'henkel', 'Henkel H1 2026', 'pdf', 'H1 2026', '2026-08-06',
            'https://www.henkel.com/report.pdf', 'report.pdf', 'application/pdf', NULL, 'test', NULL
        );
        INSERT INTO dim_source_document VALUES (
            'mercedes_report', 'mercedes_benz_group', 'Mercedes Q2 2026', 'pdf', 'Q2 2026', '2026-07-28',
            'https://group.mercedes-benz.com/report.pdf', 'report.pdf', 'application/pdf', NULL, 'test', NULL
        );
        INSERT INTO dim_source_document VALUES (
            'mercedes_presentation', 'mercedes_benz_group', 'Mercedes Q2 presentation', 'pdf', 'Q2 2026', '2026-07-28',
            'https://group.mercedes-benz.com/presentation.pdf', 'presentation.pdf', 'application/pdf', NULL, 'test', NULL
        );

        INSERT INTO dim_metric VALUES (
            'henkel_sales', 'henkel', 'Sales', 'revenue', 'Henkel sales', 'Reported Henkel sales',
            'EUR_million', 'DECIMAL', 'REPORTED', 'henkel_sales', 0,
            'Issuer-specific definition', 0.5, 1, 0
        );
        INSERT INTO dim_metric VALUES (
            'mercedes_revenue', 'mercedes_benz_group', 'Revenue', 'revenue', 'Mercedes revenue', 'Reported Mercedes revenue',
            'EUR_million', 'DECIMAL', 'REPORTED', 'mercedes_revenue', 0,
            'Issuer-specific definition', 0.5, 1, 0
        );
        INSERT INTO dim_metric VALUES (
            'mercedes_bridge', 'mercedes_benz_group', 'Volume / structure / net pricing', 'ebit_bridge',
            'Management bridge', 'Combined bridge component', 'EUR_million', 'DECIMAL',
            'REPORTED_MANAGEMENT_DECOMPOSITION', 'mercedes_bridge', 0,
            'Management attribution only', 0, 1, 0
        );
        INSERT INTO dim_metric VALUES (
            'henkel_calc', 'henkel', 'Test calculated value', 'test_calculation', 'Test only',
            'Deterministic test output', 'EUR_million', 'DECIMAL', 'DETERMINISTIC_CALCULATION',
            'test_calculation', 0, 'Test-only contract fixture', 0, 0, 0
        );

        INSERT INTO metric_allowed_period_grain VALUES ('henkel_sales', 'QUARTER');
        INSERT INTO metric_allowed_period_grain VALUES ('henkel_sales', 'HALF_YEAR');
        INSERT INTO metric_allowed_period_grain VALUES ('mercedes_revenue', 'QUARTER');
        INSERT INTO metric_allowed_period_grain VALUES ('mercedes_revenue', 'HALF_YEAR');
        INSERT INTO metric_allowed_period_grain VALUES ('mercedes_bridge', 'QUARTER_YOY');
        INSERT INTO metric_allowed_period_grain VALUES ('henkel_calc', 'HALF_YEAR');

        INSERT INTO metric_allowed_scope_type VALUES ('henkel_sales', 'GROUP');
        INSERT INTO metric_allowed_scope_type VALUES ('mercedes_revenue', 'GROUP');
        INSERT INTO metric_allowed_scope_type VALUES ('mercedes_revenue', 'SEGMENT');
        INSERT INTO metric_allowed_scope_type VALUES ('mercedes_bridge', 'SEGMENT');
        INSERT INTO metric_allowed_scope_type VALUES ('henkel_calc', 'GROUP');

        INSERT INTO metric_allowed_provenance VALUES ('henkel_sales', 'REPORTED', 'REPORTED_FACT', 0);
        INSERT INTO metric_allowed_provenance VALUES ('mercedes_revenue', 'REPORTED', 'REPORTED_FACT', 0);
        INSERT INTO metric_allowed_provenance VALUES ('mercedes_bridge', 'MANAGEMENT_ATTRIBUTED', 'MANAGEMENT_ATTRIBUTION', 0);
        INSERT INTO metric_allowed_provenance VALUES ('henkel_calc', 'CALCULATED', 'DERIVED_CALCULATION', 0);

        INSERT INTO metric_source_allowlist VALUES ('henkel_sales', 'henkel', 'henkel_report');
        INSERT INTO metric_source_allowlist VALUES ('mercedes_revenue', 'mercedes_benz_group', 'mercedes_report');
        INSERT INTO metric_source_allowlist VALUES ('mercedes_bridge', 'mercedes_benz_group', 'mercedes_presentation');

        INSERT INTO metric_evidence_expectation VALUES (
            'henkel_sales_page7', 'henkel_sales', 'henkel', 'henkel_report',
            'Sales development table', 'PDF page 7', '', 'PRIMARY_NUMERIC', 'VERIFIED', ''
        );
        INSERT INTO metric_evidence_expectation VALUES (
            'mercedes_revenue_page3', 'mercedes_revenue', 'mercedes_benz_group', 'mercedes_report',
            'Key figures table', 'PDF page 3', '', 'PRIMARY_NUMERIC', 'VERIFIED', ''
        );
        INSERT INTO metric_evidence_expectation VALUES (
            'mercedes_bridge_page8', 'mercedes_bridge', 'mercedes_benz_group', 'mercedes_presentation',
            'Cars EBIT bridge', 'PDF page 8', '', 'MANAGEMENT_BRIDGE', 'VERIFIED', ''
        );
        """
    )
    try:
        yield connection
    finally:
        connection.close()
