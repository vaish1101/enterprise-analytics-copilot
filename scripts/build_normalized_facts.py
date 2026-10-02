"""Build the reviewed Step 4 normalized fact fixture deterministically.

Values below are transcribed from the pinned, verified Henkel report tables and
Mercedes-Benz fact-sheet/presentation mappings documented in Steps 1-2. This
script does not parse raw sources at query time.
"""

from __future__ import annotations

import csv
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.schemas.catalog import load_metric_catalog  # noqa: E402


OUTPUT = ROOT / "data/normalized/facts.csv"
PERIODS = ("Q2_2025", "Q2_2026", "H1_2025", "H1_2026")
PERIOD_GRAINS = {
    "Q2_2025": "QUARTER", "Q2_2026": "QUARTER",
    "H1_2025": "HALF_YEAR", "H1_2026": "HALF_YEAR",
}

HENKEL = {
    "henkel_group": {
        "henkel_sales": ("5160", "5396", "10402", "10348"),
        "henkel_nominal_sales_change": ("-6.1", "4.6", "-3.8", "-0.5"),
        "henkel_fx_effect": ("-4.1", "-2.6", "-2.8", "-3.9"),
        "henkel_acquisitions_divestments_effect": ("-2.9", "2.5", "-0.9", "0.2"),
        "henkel_organic_sales_growth": ("0.9", "4.7", "-0.1", "3.2"),
        "henkel_price_contribution": ("1.3", "1.5", "1.3", "1.1"),
        "henkel_volume_contribution": ("-0.4", "3.2", "-1.4", "2.1"),
    },
    "henkel_adhesive_technologies": {
        "henkel_sales": ("2701", "2908", "5416", "5534"),
        "henkel_nominal_sales_change": ("-3.5", "7.6", "-1.1", "2.2"),
        "henkel_fx_effect": ("-3.9", "-2.4", "-2.5", "-3.8"),
        "henkel_acquisitions_divestments_effect": ("-0.9", "2.7", "0.2", "1.5"),
        "henkel_organic_sales_growth": ("1.3", "7.4", "1.2", "4.5"),
        "henkel_price_contribution": ("1.0", "3.2", "0.8", "1.8"),
        "henkel_volume_contribution": ("0.3", "4.2", "0.4", "2.8"),
    },
    "henkel_consumer_brands": {
        "henkel_sales": ("2422", "2448", "4907", "4733"),
        "henkel_nominal_sales_change": ("-9.0", "1.1", "-6.8", "-3.5"),
        "henkel_fx_effect": ("-4.4", "-2.9", "-3.2", "-4.1"),
        "henkel_acquisitions_divestments_effect": ("-5.0", "2.4", "-2.1", "-1.2"),
        "henkel_organic_sales_growth": ("0.4", "1.6", "-1.6", "1.7"),
        "henkel_price_contribution": ("1.5", "-0.5", "1.8", "0.3"),
        "henkel_volume_contribution": ("-1.2", "2.1", "-3.4", "1.4"),
    },
}

MERCEDES = {
    "mercedes_group": {
        "mercedes_revenue": ("33153", "32061", "66377", "63663"),
        "mercedes_ebit": ("1273", "1547", "3562", "3451"),
        "mercedes_adjusted_ebit": ("1988", "2299", "4534", "4072"),
    },
    "mercedes_cars": {
        "mercedes_unit_sales": ("453674", "417765", "899974", "837195"),
        "mercedes_revenue": ("24162", "22987", "48400", "45945"),
        "mercedes_ebit": ("783", "49", "2541", "858"),
        "mercedes_adjusted_ebit": ("1228", "909", "2996", "1842"),
    },
    "mercedes_vans": {
        "mercedes_unit_sales": ("93393", "94075", "176336", "174331"),
        "mercedes_revenue": ("4237", "4455", "8317", "8579"),
        "mercedes_ebit": ("274", "502", "503", "894"),
        "mercedes_adjusted_ebit": ("441", "454", "916", "869"),
    },
    "mercedes_financial_services": {
        "mercedes_revenue": ("6248", "6180", "12670", "12285"),
        "mercedes_ebit": ("247", "475", "534", "874"),
        "mercedes_adjusted_ebit": ("290", "492", "577", "905"),
    },
}

BRIDGES = {
    "mercedes_cars": (
        ("mercedes_bridge_volume_structure_net_pricing", "-602"),
        ("mercedes_bridge_foreign_exchange_rates", "17"),
        ("mercedes_bridge_industrial_performance", "482"),
        ("mercedes_bridge_selling_expenses", "-194"),
        ("mercedes_bridge_general_administrative_expenses", "-28"),
        ("mercedes_bridge_research_noncapitalized_development", "143"),
        ("mercedes_bridge_others", "-137"),
    ),
    "mercedes_vans": (
        ("mercedes_bridge_volume_structure_net_pricing", "98"),
        ("mercedes_bridge_foreign_exchange_rates", "-16"),
        ("mercedes_bridge_industrial_performance", "-94"),
        ("mercedes_bridge_selling_expenses", "7"),
        ("mercedes_bridge_general_administrative_expenses", "-1"),
        ("mercedes_bridge_research_noncapitalized_development", "38"),
        ("mercedes_bridge_others", "-19"),
    ),
    "mercedes_financial_services": (
        ("mercedes_bridge_foreign_exchange_rates", "-7"),
        ("mercedes_bridge_cost_of_credit_risk", "66"),
        ("mercedes_bridge_volume_margin", "188"),
        ("mercedes_bridge_selling_expenses", "31"),
        ("mercedes_bridge_general_administrative_expenses", "2"),
        ("mercedes_bridge_others", "-78"),
    ),
}

ADJUSTMENTS = {
    "mercedes_cars": "-860",
    "mercedes_vans": "48",
    "mercedes_financial_services": "-17",
}


def _henkel_expectation(metric_id: str, scope_id: str) -> str:
    metric = {
        "henkel_sales": "sales", "henkel_nominal_sales_change": "nominal",
        "henkel_organic_sales_growth": "organic", "henkel_fx_effect": "fx",
        "henkel_acquisitions_divestments_effect": "portfolio",
        "henkel_price_contribution": "price", "henkel_volume_contribution": "volume",
    }[metric_id]
    scope = {
        "henkel_group": "group", "henkel_adhesive_technologies": "adhesive",
        "henkel_consumer_brands": "consumer",
    }[scope_id]
    return f"henkel_{metric}_{scope}_pdf"


def _mercedes_expectation(metric_id: str, scope_id: str, period_id: str) -> str:
    metric = {
        "mercedes_revenue": "revenue", "mercedes_ebit": "ebit",
        "mercedes_adjusted_ebit": "adj_ebit", "mercedes_unit_sales": "units",
    }[metric_id]
    scope = {
        "mercedes_group": "group", "mercedes_cars": "cars",
        "mercedes_vans": "vans", "mercedes_financial_services": "fs",
    }[scope_id]
    suffix = "_prior" if period_id.endswith("2025") else ""
    return f"mercedes_{metric}_{scope}_xlsx{suffix}"


def _bridge_expectation(metric_id: str, scope_id: str) -> str:
    metric = {
        "mercedes_bridge_volume_structure_net_pricing": "combined",
        "mercedes_bridge_foreign_exchange_rates": "fx",
        "mercedes_bridge_industrial_performance": "industrial",
        "mercedes_bridge_selling_expenses": "selling",
        "mercedes_bridge_general_administrative_expenses": "ga",
        "mercedes_bridge_research_noncapitalized_development": "rd",
        "mercedes_bridge_others": "others",
        "mercedes_bridge_cost_of_credit_risk": "credit_risk",
        "mercedes_bridge_volume_margin": "volume_margin",
        "mercedes_bridge_adjustments": "adjustments",
    }[metric_id]
    scope = {"mercedes_cars": "cars", "mercedes_vans": "vans", "mercedes_financial_services": "fs"}[scope_id]
    if metric in {"credit_risk", "volume_margin"}:
        return f"mercedes_{metric}_presentation"
    return f"mercedes_{metric}_{scope}_presentation"


def build_rows() -> list[dict[str, str]]:
    catalog = load_metric_catalog(ROOT / "config", ROOT / "data/source_manifest.csv")
    expectations = {
        item.expectation_id: item
        for metric in catalog.values()
        for item in metric.evidence_expectations
    }
    rows: list[dict[str, str]] = []

    def add(
        company: str, metric_id: str, scope_id: str, period_id: str, value: str,
        expectation_id: str, source_id: str, *, period_grain: str | None = None,
        bridge_id: str = "", component_order: str = "", bridge_role: str = "",
    ) -> None:
        metric = catalog[metric_id]
        expectation = expectations[expectation_id]
        rows.append({
            "fact_id": str(len(rows) + 1), "company_id": company,
            "metric_id": metric_id, "reported_name": metric.reported_name,
            "scope_id": scope_id, "period_id": period_id,
            "period_grain": period_grain or PERIOD_GRAINS[period_id], "value": value,
            "unit": metric.unit.value, "value_type": metric.value_type.value,
            "provenance_type": next(iter(metric.allowed_provenance_types)).value,
            "claim_semantics": metric.claim_semantics.value,
            "source_id": source_id, "evidence_id": f"evidence_{len(rows) + 1:04d}",
            "expectation_id": expectation_id,
            "verification_status": expectation.verification_status.value,
            "rounding_tolerance": str(metric.rounding_tolerance),
            "bridge_id": bridge_id, "component_order": component_order,
            "bridge_role": bridge_role,
        })

    for scope_id, metrics in HENKEL.items():
        for metric_id, values in metrics.items():
            for period_id, value in zip(PERIODS, values, strict=True):
                add(
                    "henkel", metric_id, scope_id, period_id, value,
                    _henkel_expectation(metric_id, scope_id),
                    "henkel_h1_2026_financial_report",
                )

    bridge_rows: dict[tuple[str, str, str], tuple[str, str, str]] = {}
    for scope_id, components in BRIDGES.items():
        bridge_id = f"{scope_id}_q2_2026_yoy"
        bridge_rows[("mercedes_adjusted_ebit", scope_id, "Q2_2025")] = (bridge_id, "0", "START")
        endpoint_order = len(components) + 1
        bridge_rows[("mercedes_adjusted_ebit", scope_id, "Q2_2026")] = (bridge_id, str(endpoint_order), "ADJUSTED_ENDPOINT")
        bridge_rows[("mercedes_bridge_adjustments", scope_id, "Q2_2026")] = (bridge_id, str(endpoint_order + 1), "ADJUSTMENT")
        bridge_rows[("mercedes_ebit", scope_id, "Q2_2026")] = (bridge_id, str(endpoint_order + 2), "REPORTED_ENDPOINT")

    for scope_id, metrics in MERCEDES.items():
        for metric_id, values in metrics.items():
            for period_id, value in zip(PERIODS, values, strict=True):
                bridge = bridge_rows.get((metric_id, scope_id, period_id), ("", "", ""))
                add(
                    "mercedes_benz_group", metric_id, scope_id, period_id, value,
                    _mercedes_expectation(metric_id, scope_id, period_id),
                    "mercedes_q2_2026_fact_sheet_xlsx",
                    bridge_id=bridge[0], component_order=bridge[1], bridge_role=bridge[2],
                )

    for scope_id, components in BRIDGES.items():
        bridge_id = f"{scope_id}_q2_2026_yoy"
        for order, (metric_id, value) in enumerate(components, start=1):
            add(
                "mercedes_benz_group", metric_id, scope_id, "Q2_2026", value,
                _bridge_expectation(metric_id, scope_id),
                "mercedes_q2_2026_capital_market_presentation",
                period_grain="QUARTER_YOY", bridge_id=bridge_id,
                component_order=str(order), bridge_role="COMPONENT",
            )
        endpoint_order = len(components) + 1
        add(
            "mercedes_benz_group", "mercedes_bridge_adjustments", scope_id, "Q2_2026",
            ADJUSTMENTS[scope_id], _bridge_expectation("mercedes_bridge_adjustments", scope_id),
            "mercedes_q2_2026_capital_market_presentation",
            bridge_id=bridge_id, component_order=str(endpoint_order + 1), bridge_role="ADJUSTMENT",
        )

    if len(rows) != 163:
        raise AssertionError(f"expected 163 normalized facts, got {len(rows)}")
    return rows


def main() -> int:
    rows = build_rows()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} normalized facts to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
