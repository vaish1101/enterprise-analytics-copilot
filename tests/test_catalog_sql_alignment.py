import csv
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_rows(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_complete_csv_catalog_loads_into_sql_contract():
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript((ROOT / "src/schemas/normalized_schema.sql").read_text(encoding="utf-8"))
    manifest = read_rows(ROOT / "data/source_manifest.csv")
    catalog = read_rows(ROOT / "config/metric_catalog.csv")
    periods = read_rows(ROOT / "config/metric_allowed_period_grains.csv")
    scopes = read_rows(ROOT / "config/metric_allowed_scope_types.csv")
    expectations = read_rows(ROOT / "config/metric_evidence_expectations.csv")
    try:
        company_names = {
            "henkel": "Henkel AG & Co. KGaA",
            "mercedes_benz_group": "Mercedes-Benz Group AG",
            "siemens": "Siemens AG",
        }
        connection.executemany(
            "INSERT INTO dim_company VALUES (?, ?)", company_names.items()
        )
        connection.executemany(
            """
            INSERT INTO dim_source_document VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["source_id"], row["company"], row["source_title"], row["source_type"],
                    row["reporting_period"], row["publication_date"], row["official_url"],
                    row["expected_filename"], row["expected_content_type"], row["sha256"] or None,
                    row["acquisition_status"], row["retrieval_timestamp"] or None,
                )
                for row in manifest
            ],
        )
        connection.executemany(
            "INSERT INTO dim_metric VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    row["metric_id"], row["company"], row["reported_name"],
                    row["canonical_family"], row["description"], row["definition"],
                    row["unit"], row["value_type"], row["calculation_type"],
                    row["comparability_group"], int(row["comparable_across_companies"] == "true"),
                    row["comparability_notes"], row["rounding_tolerance"],
                    int(row["evidence_required"] == "true"), int(row["causal_claim_allowed"] == "true"),
                )
                for row in catalog
            ],
        )
        connection.executemany(
            "INSERT INTO metric_allowed_period_grain VALUES (?, ?)",
            [(row["metric_id"], row["period_grain"]) for row in periods],
        )
        connection.executemany(
            "INSERT INTO metric_allowed_scope_type VALUES (?, ?)",
            [(row["metric_id"], row["scope_type"]) for row in scopes],
        )
        connection.executemany(
            "INSERT INTO metric_allowed_provenance VALUES (?, ?, ?, ?)",
            [
                (
                    row["metric_id"], row["allowed_provenance_type"],
                    row["claim_semantics"], int(row["causal_claim_allowed"] == "true"),
                )
                for row in catalog
            ],
        )
        allowlist = {
            (row["metric_id"], row["company"], row["source_id"])
            for row in expectations
        }
        connection.executemany(
            "INSERT INTO metric_source_allowlist VALUES (?, ?, ?)", sorted(allowlist)
        )
        connection.executemany(
            "INSERT INTO metric_evidence_expectation VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    row["expectation_id"], row["metric_id"], row["company"], row["source_id"],
                    row["source_location"], row["source_page_or_sheet"], row["source_cell_or_range"],
                    row["evidence_type"], row["verification_status"], row["note"],
                )
                for row in expectations
            ],
        )
        assert connection.execute("SELECT COUNT(*) FROM dim_metric").fetchone()[0] == 27
        assert connection.execute("SELECT COUNT(*) FROM metric_evidence_expectation").fetchone()[0] == len(expectations)
    finally:
        connection.close()
