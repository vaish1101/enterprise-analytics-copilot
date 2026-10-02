PRAGMA foreign_keys = ON;

-- Controlled vocabularies. config/controlled_vocabularies.csv is the reviewable
-- catalog counterpart; tests require exact agreement with these SQL values.
CREATE TABLE ref_period_grain (value TEXT PRIMARY KEY);
INSERT INTO ref_period_grain VALUES
    ('QUARTER'), ('HALF_YEAR'), ('YEAR'), ('POINT_IN_TIME'),
    ('QUARTER_YOY'), ('HALF_YEAR_YOY');

CREATE TABLE ref_provenance_type (value TEXT PRIMARY KEY);
INSERT INTO ref_provenance_type VALUES
    ('REPORTED'), ('CALCULATED'), ('MANAGEMENT_ATTRIBUTED'),
    ('INTERPRETATION'), ('UNSUPPORTED'), ('AMBIGUOUS');

CREATE TABLE ref_claim_semantics (value TEXT PRIMARY KEY);
INSERT INTO ref_claim_semantics VALUES
    ('REPORTED_FACT'), ('DERIVED_CALCULATION'), ('MANAGEMENT_ATTRIBUTION'),
    ('INTERPRETATION'), ('UNSUPPORTED'), ('AMBIGUOUS');

CREATE TABLE ref_calculation_type (value TEXT PRIMARY KEY);
INSERT INTO ref_calculation_type VALUES
    ('REPORTED'), ('REPORTED_MANAGEMENT_DECOMPOSITION'),
    ('REPORTED_RECONCILIATION'), ('DETERMINISTIC_CALCULATION');

CREATE TABLE ref_value_type (value TEXT PRIMARY KEY);
INSERT INTO ref_value_type VALUES ('DECIMAL'), ('INTEGER');

CREATE TABLE ref_scope_type (value TEXT PRIMARY KEY);
INSERT INTO ref_scope_type VALUES
    ('GROUP'), ('BUSINESS_UNIT'), ('BUSINESS_AREA'),
    ('SEGMENT'), ('REGION'), ('PRODUCT_CATEGORY');

CREATE TABLE ref_confidence_class (value TEXT PRIMARY KEY);
INSERT INTO ref_confidence_class VALUES ('HIGH'), ('MEDIUM'), ('LOW');

CREATE TABLE ref_evidence_type (value TEXT PRIMARY KEY);
INSERT INTO ref_evidence_type VALUES
    ('PRIMARY_NUMERIC'), ('CORROBORATING_NUMERIC'), ('MANAGEMENT_BRIDGE');

CREATE TABLE ref_verification_status (value TEXT PRIMARY KEY);
INSERT INTO ref_verification_status VALUES ('VERIFIED'), ('PENDING'), ('REJECTED');

CREATE TABLE ref_calculation_run_status (value TEXT PRIMARY KEY);
INSERT INTO ref_calculation_run_status VALUES ('SUCCESS'), ('FAILED');

CREATE TABLE ref_bridge_component_role (value TEXT PRIMARY KEY);
INSERT INTO ref_bridge_component_role VALUES
    ('START'), ('COMPONENT'), ('ADJUSTED_ENDPOINT'), ('ADJUSTMENT'), ('REPORTED_ENDPOINT');

CREATE TABLE dim_company (
    company_id TEXT PRIMARY KEY,
    legal_name TEXT NOT NULL UNIQUE
);

CREATE TABLE dim_reporting_period (
    period_id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    grain TEXT NOT NULL REFERENCES ref_period_grain(value),
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    CHECK (end_date >= start_date),
    UNIQUE (period_id, grain)
);

CREATE TABLE dim_business_scope (
    scope_id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES dim_company(company_id),
    scope_type TEXT NOT NULL REFERENCES ref_scope_type(value),
    scope_name TEXT NOT NULL,
    parent_scope_id TEXT,
    UNIQUE (scope_id, company_id),
    UNIQUE (scope_id, company_id, scope_type),
    UNIQUE (company_id, scope_name),
    FOREIGN KEY (parent_scope_id, company_id)
        REFERENCES dim_business_scope(scope_id, company_id)
);

CREATE TABLE dim_source_document (
    source_id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES dim_company(company_id),
    source_title TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN ('pdf', 'xlsx')),
    reporting_period TEXT NOT NULL,
    publication_date TEXT NOT NULL,
    official_url TEXT NOT NULL,
    expected_filename TEXT NOT NULL,
    expected_content_type TEXT NOT NULL,
    sha256 TEXT,
    acquisition_status TEXT NOT NULL,
    retrieval_timestamp TEXT,
    UNIQUE (source_id, company_id)
);

CREATE TABLE dim_metric (
    metric_id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES dim_company(company_id),
    reported_name TEXT NOT NULL,
    canonical_family TEXT NOT NULL,
    description TEXT NOT NULL,
    definition TEXT NOT NULL,
    unit TEXT NOT NULL,
    value_type TEXT NOT NULL REFERENCES ref_value_type(value),
    calculation_type TEXT NOT NULL REFERENCES ref_calculation_type(value),
    comparability_group TEXT NOT NULL,
    comparable_across_companies INTEGER NOT NULL DEFAULT 0
        CHECK (comparable_across_companies IN (0, 1)),
    comparability_notes TEXT NOT NULL,
    rounding_tolerance NUMERIC NOT NULL CHECK (rounding_tolerance >= 0),
    evidence_required INTEGER NOT NULL CHECK (evidence_required IN (0, 1)),
    causal_claim_allowed INTEGER NOT NULL DEFAULT 0
        CHECK (causal_claim_allowed = 0),
    UNIQUE (metric_id, company_id),
    UNIQUE (metric_id, company_id, unit, value_type)
);

CREATE TABLE metric_allowed_period_grain (
    metric_id TEXT NOT NULL REFERENCES dim_metric(metric_id),
    period_grain TEXT NOT NULL REFERENCES ref_period_grain(value),
    PRIMARY KEY (metric_id, period_grain)
);

CREATE TABLE metric_allowed_scope_type (
    metric_id TEXT NOT NULL REFERENCES dim_metric(metric_id),
    scope_type TEXT NOT NULL REFERENCES ref_scope_type(value),
    PRIMARY KEY (metric_id, scope_type)
);

CREATE TABLE metric_allowed_provenance (
    metric_id TEXT NOT NULL REFERENCES dim_metric(metric_id),
    provenance_type TEXT NOT NULL REFERENCES ref_provenance_type(value),
    claim_semantics TEXT NOT NULL REFERENCES ref_claim_semantics(value),
    causal_claim_allowed INTEGER NOT NULL DEFAULT 0 CHECK (causal_claim_allowed = 0),
    PRIMARY KEY (metric_id, provenance_type, claim_semantics, causal_claim_allowed),
    CHECK (NOT (
        provenance_type = 'MANAGEMENT_ATTRIBUTED'
        AND (claim_semantics <> 'MANAGEMENT_ATTRIBUTION' OR causal_claim_allowed <> 0)
    )),
    CHECK (NOT (
        provenance_type = 'CALCULATED'
        AND claim_semantics <> 'DERIVED_CALCULATION'
    ))
);

CREATE TABLE metric_source_allowlist (
    metric_id TEXT NOT NULL,
    company_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    PRIMARY KEY (metric_id, company_id, source_id),
    FOREIGN KEY (metric_id, company_id)
        REFERENCES dim_metric(metric_id, company_id),
    FOREIGN KEY (source_id, company_id)
        REFERENCES dim_source_document(source_id, company_id)
);

CREATE TABLE metric_evidence_expectation (
    expectation_id TEXT PRIMARY KEY,
    metric_id TEXT NOT NULL,
    company_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_location TEXT NOT NULL CHECK (length(trim(source_location)) > 0),
    source_page_or_sheet TEXT NOT NULL CHECK (length(trim(source_page_or_sheet)) > 0),
    source_cell_or_range TEXT NOT NULL DEFAULT '',
    evidence_type TEXT NOT NULL REFERENCES ref_evidence_type(value),
    verification_status TEXT NOT NULL REFERENCES ref_verification_status(value),
    note TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (metric_id, company_id, source_id)
        REFERENCES metric_source_allowlist(metric_id, company_id, source_id),
    UNIQUE (
        expectation_id, metric_id, company_id, source_id, source_location,
        source_page_or_sheet, source_cell_or_range
    )
);

CREATE TABLE calculation_rule (
    rule_id TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    rule_version TEXT NOT NULL,
    formula_or_executable_id TEXT NOT NULL,
    output_metric_id TEXT NOT NULL,
    company_id TEXT NOT NULL,
    deterministic INTEGER NOT NULL CHECK (deterministic = 1),
    description TEXT NOT NULL,
    PRIMARY KEY (rule_id, rule_version),
    FOREIGN KEY (output_metric_id, company_id)
        REFERENCES dim_metric(metric_id, company_id),
    UNIQUE (rule_id, rule_version, output_metric_id, company_id)
);

CREATE TABLE calculation_run (
    run_id TEXT PRIMARY KEY,
    rule_id TEXT NOT NULL,
    rule_version TEXT NOT NULL,
    output_metric_id TEXT NOT NULL,
    company_id TEXT NOT NULL,
    executed_at TEXT NOT NULL,
    execution_engine TEXT NOT NULL,
    execution_version TEXT NOT NULL,
    input_digest TEXT NOT NULL,
    result_value NUMERIC NOT NULL,
    status TEXT NOT NULL REFERENCES ref_calculation_run_status(value),
    FOREIGN KEY (rule_id, rule_version, output_metric_id, company_id)
        REFERENCES calculation_rule(rule_id, rule_version, output_metric_id, company_id),
    UNIQUE (run_id, company_id),
    UNIQUE (run_id, output_metric_id, company_id, result_value, status)
);

CREATE TABLE fact_reported_metric (
    fact_id INTEGER PRIMARY KEY,
    metric_id TEXT NOT NULL,
    company_id TEXT NOT NULL,
    period_id TEXT NOT NULL,
    period_grain TEXT NOT NULL,
    scope_id TEXT NOT NULL,
    scope_type TEXT NOT NULL,
    source_id TEXT,
    value_numeric NUMERIC NOT NULL,
    unit TEXT NOT NULL,
    value_type TEXT NOT NULL,
    provenance_type TEXT NOT NULL REFERENCES ref_provenance_type(value),
    claim_semantics TEXT NOT NULL REFERENCES ref_claim_semantics(value),
    causal_claim INTEGER NOT NULL DEFAULT 0 CHECK (causal_claim IN (0, 1)),
    confidence_class TEXT REFERENCES ref_confidence_class(value),
    calculation_run_id TEXT,
    calculation_status TEXT,
    extraction_method TEXT NOT NULL,
    CHECK (provenance_type IN ('REPORTED', 'CALCULATED', 'MANAGEMENT_ATTRIBUTED')),
    CHECK (NOT (provenance_type = 'MANAGEMENT_ATTRIBUTED' AND causal_claim = 1)),
    CHECK (NOT (provenance_type = 'MANAGEMENT_ATTRIBUTED' AND confidence_class = 'HIGH')),
    CHECK (NOT (provenance_type = 'CALCULATED' AND confidence_class = 'HIGH')),
    CHECK (
        (provenance_type = 'CALCULATED'
            AND source_id IS NULL
            AND calculation_run_id IS NOT NULL
            AND calculation_status = 'SUCCESS')
        OR
        (provenance_type <> 'CALCULATED'
            AND source_id IS NOT NULL
            AND calculation_run_id IS NULL
            AND calculation_status IS NULL)
    ),
    FOREIGN KEY (metric_id, company_id, unit, value_type)
        REFERENCES dim_metric(metric_id, company_id, unit, value_type),
    FOREIGN KEY (period_id, period_grain)
        REFERENCES dim_reporting_period(period_id, grain),
    FOREIGN KEY (metric_id, period_grain)
        REFERENCES metric_allowed_period_grain(metric_id, period_grain),
    FOREIGN KEY (scope_id, company_id, scope_type)
        REFERENCES dim_business_scope(scope_id, company_id, scope_type),
    FOREIGN KEY (metric_id, scope_type)
        REFERENCES metric_allowed_scope_type(metric_id, scope_type),
    FOREIGN KEY (metric_id, provenance_type, claim_semantics, causal_claim)
        REFERENCES metric_allowed_provenance(
            metric_id, provenance_type, claim_semantics, causal_claim_allowed
        ),
    FOREIGN KEY (source_id, company_id)
        REFERENCES dim_source_document(source_id, company_id),
    FOREIGN KEY (metric_id, company_id, source_id)
        REFERENCES metric_source_allowlist(metric_id, company_id, source_id),
    FOREIGN KEY (
        calculation_run_id, metric_id, company_id, value_numeric, calculation_status
    ) REFERENCES calculation_run(
        run_id, output_metric_id, company_id, result_value, status
    ),
    UNIQUE (fact_id, metric_id, company_id),
    UNIQUE (fact_id, company_id)
);

CREATE TABLE calculation_input (
    run_id TEXT NOT NULL,
    company_id TEXT NOT NULL,
    input_fact_id INTEGER NOT NULL,
    input_role TEXT NOT NULL,
    input_position INTEGER NOT NULL CHECK (input_position >= 0),
    PRIMARY KEY (run_id, input_position),
    UNIQUE (run_id, input_fact_id),
    FOREIGN KEY (run_id, company_id)
        REFERENCES calculation_run(run_id, company_id),
    FOREIGN KEY (input_fact_id, company_id)
        REFERENCES fact_reported_metric(fact_id, company_id)
);

CREATE TRIGGER calculated_fact_requires_inputs
BEFORE INSERT ON fact_reported_metric
WHEN NEW.provenance_type = 'CALCULATED'
     AND NOT EXISTS (
        SELECT 1 FROM calculation_input ci
        WHERE ci.run_id = NEW.calculation_run_id
          AND ci.company_id = NEW.company_id
     )
BEGIN
    SELECT RAISE(ABORT, 'CALCULATED fact requires at least one calculation input');
END;

CREATE TABLE fact_evidence (
    evidence_id TEXT PRIMARY KEY,
    fact_id INTEGER NOT NULL,
    metric_id TEXT NOT NULL,
    company_id TEXT NOT NULL,
    expectation_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_location TEXT NOT NULL CHECK (length(trim(source_location)) > 0),
    source_page_or_sheet TEXT NOT NULL CHECK (length(trim(source_page_or_sheet)) > 0),
    source_cell_or_range TEXT NOT NULL DEFAULT '',
    evidence_type TEXT NOT NULL REFERENCES ref_evidence_type(value),
    verification_status TEXT NOT NULL REFERENCES ref_verification_status(value),
    note TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (fact_id, metric_id, company_id)
        REFERENCES fact_reported_metric(fact_id, metric_id, company_id),
    FOREIGN KEY (
        expectation_id, metric_id, company_id, source_id, source_location,
        source_page_or_sheet, source_cell_or_range
    ) REFERENCES metric_evidence_expectation(
        expectation_id, metric_id, company_id, source_id, source_location,
        source_page_or_sheet, source_cell_or_range
    ),
    UNIQUE (
        fact_id, expectation_id, source_id, source_location,
        source_page_or_sheet, source_cell_or_range
    )
);

CREATE TABLE fact_bridge_component (
    bridge_component_id INTEGER PRIMARY KEY,
    fact_id INTEGER NOT NULL UNIQUE REFERENCES fact_reported_metric(fact_id),
    bridge_id TEXT NOT NULL,
    component_label TEXT NOT NULL,
    component_order INTEGER NOT NULL CHECK (component_order >= 0),
    component_role TEXT NOT NULL REFERENCES ref_bridge_component_role(value),
    UNIQUE (bridge_id, component_order)
);

CREATE INDEX idx_fact_lookup
    ON fact_reported_metric(company_id, period_id, scope_id, metric_id);
CREATE INDEX idx_evidence_fact
    ON fact_evidence(fact_id, evidence_id);
CREATE INDEX idx_bridge_lookup
    ON fact_bridge_component(bridge_id, component_order);
