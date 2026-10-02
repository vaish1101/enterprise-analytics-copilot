"""Deterministic PDF parser with governed source adapters.

The generic layer owns extraction and unit contracts. Source adapters only add
document-specific page semantics (scope, period, section and table identity).
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

from .evidence_units import make_evidence_unit, normalize_text
from .models import EvidenceRelevance, EvidenceUnit, EvidenceUnitType


PDF_SOURCES = (
    "henkel_h1_2026_financial_report",
    "mercedes_q2_2026_interim_report",
    "mercedes_q2_2026_fact_sheet_pdf",
    "mercedes_q2_2026_capital_market_presentation",
    "siemens_q2_fy2026_earnings_release",
)

_SOURCE_COMPANIES = {
    "henkel_h1_2026_financial_report": "henkel",
    "mercedes_q2_2026_interim_report": "mercedes_benz_group",
    "mercedes_q2_2026_fact_sheet_pdf": "mercedes_benz_group",
    "mercedes_q2_2026_capital_market_presentation": "mercedes_benz_group",
    "siemens_q2_fy2026_earnings_release": "siemens",
}


@dataclass(frozen=True)
class PageSemantics:
    section: str
    scopes: tuple[str, ...]
    periods: tuple[str, ...]
    table_title: str | None = None
    unit_type: EvidenceUnitType | None = None


_PAGE_RULES: dict[tuple[str, int], PageSemantics] = {
    ("henkel_h1_2026_financial_report", 6): PageSemantics("Business performance at a glance", ("henkel_group",), ("H1_2025", "H1_2026"), "Key financials", EvidenceUnitType.HEADLINE_SUMMARY),
    ("henkel_h1_2026_financial_report", 7): PageSemantics("Sales", ("henkel_group",), ("Q2_2025", "Q2_2026", "H1_2025", "H1_2026"), "Sales development"),
    ("henkel_h1_2026_financial_report", 11): PageSemantics("Adhesive Technologies", ("henkel_adhesive_technologies",), ("Q2_2025", "Q2_2026", "H1_2025", "H1_2026"), "Sales development"),
    ("henkel_h1_2026_financial_report", 12): PageSemantics("Adhesive Technologies", ("henkel_adhesive_technologies", "henkel_mobility_electronics", "henkel_packaging_consumer_goods", "henkel_craftsmen_construction_professional"), ("Q2_2025", "Q2_2026", "H1_2025", "H1_2026"), "Sales development by business area"),
    ("henkel_h1_2026_financial_report", 13): PageSemantics("Consumer Brands", ("henkel_consumer_brands",), ("Q2_2025", "Q2_2026", "H1_2025", "H1_2026"), "Sales development"),
    ("henkel_h1_2026_financial_report", 14): PageSemantics("Consumer Brands", ("henkel_consumer_brands", "henkel_laundry_home_care", "henkel_hair", "henkel_other_consumer_businesses"), ("Q2_2025", "Q2_2026", "H1_2025", "H1_2026"), "Sales development by business area"),
    ("mercedes_q2_2026_interim_report", 3): PageSemantics("Group financial key figures", ("mercedes_group",), ("Q2_2025", "Q2_2026", "H1_2025", "H1_2026"), "Group financial key figures"),
    ("mercedes_q2_2026_interim_report", 4): PageSemantics("Segment financial key figures", ("mercedes_cars", "mercedes_vans", "mercedes_financial_services"), ("Q2_2025", "Q2_2026"), "Q2 segment financial key figures"),
    ("mercedes_q2_2026_interim_report", 5): PageSemantics("Segment financial key figures", ("mercedes_cars", "mercedes_vans", "mercedes_financial_services"), ("H1_2025", "H1_2026"), "H1 segment financial key figures"),
    ("mercedes_q2_2026_interim_report", 22): PageSemantics("Adjustments", ("mercedes_cars", "mercedes_vans"), ("Q2_2025", "Q2_2026", "H1_2025", "H1_2026"), "Adjustments affecting EBIT"),
    ("mercedes_q2_2026_interim_report", 23): PageSemantics("Adjustments", ("mercedes_financial_services", "mercedes_group"), ("Q2_2025", "Q2_2026", "H1_2025", "H1_2026"), "Adjustments affecting EBIT"),
    ("mercedes_q2_2026_fact_sheet_pdf", 4): PageSemantics("Key Figures", ("mercedes_group",), ("Q2_2025", "Q2_2026", "H1_2025", "H1_2026"), "Key Figures of the Mercedes-Benz Group"),
    ("mercedes_q2_2026_fact_sheet_pdf", 12): PageSemantics("Adjustments", ("mercedes_cars", "mercedes_vans", "mercedes_financial_services", "mercedes_group"), ("Q2_2025", "Q2_2026", "H1_2025", "H1_2026"), "Adjustments affecting EBIT"),
    ("mercedes_q2_2026_fact_sheet_pdf", 13): PageSemantics("Adjusted performance", ("mercedes_cars", "mercedes_vans", "mercedes_financial_services", "mercedes_group"), ("Q2_2025", "Q2_2026", "H1_2025", "H1_2026"), "EBIT Adjusted and RoS/RoE Adjusted"),
    ("mercedes_q2_2026_fact_sheet_pdf", 19): PageSemantics("Mercedes-Benz Cars", ("mercedes_cars",), ("Q2_2025", "Q2_2026", "H1_2025", "H1_2026"), "Mercedes-Benz Cars - Overview"),
    ("mercedes_q2_2026_fact_sheet_pdf", 23): PageSemantics("Mercedes-Benz Vans", ("mercedes_vans",), ("Q2_2025", "Q2_2026", "H1_2025", "H1_2026"), "Mercedes-Benz Vans - Overview"),
    ("mercedes_q2_2026_fact_sheet_pdf", 27): PageSemantics("Mercedes-Benz Financial Services", ("mercedes_financial_services",), ("Q2_2025", "Q2_2026", "H1_2025", "H1_2026"), "Mercedes-Benz Financial Services - Overview"),
    ("mercedes_q2_2026_capital_market_presentation", 8): PageSemantics("Mercedes-Benz Cars EBIT and RoS bridge", ("mercedes_cars",), ("Q2_2025", "Q2_2026"), "Mercedes-Benz Cars EBIT and RoS bridge", EvidenceUnitType.BRIDGE_DECOMPOSITION),
    ("mercedes_q2_2026_capital_market_presentation", 11): PageSemantics("Mercedes-Benz Vans EBIT and RoS bridge", ("mercedes_vans",), ("Q2_2025", "Q2_2026"), "Mercedes-Benz Vans EBIT and RoS bridge", EvidenceUnitType.BRIDGE_DECOMPOSITION),
    ("mercedes_q2_2026_capital_market_presentation", 21): PageSemantics("Mercedes-Benz Financial Services EBIT and RoE bridge", ("mercedes_financial_services",), ("Q2_2025", "Q2_2026"), "Mercedes-Benz Financial Services EBIT and RoE bridge", EvidenceUnitType.BRIDGE_DECOMPOSITION),
    ("siemens_q2_fy2026_earnings_release", 1): PageSemantics("Q2 FY 2026 highlights", ("siemens_group",), ("Q2_2025", "Q2_2026"), None, EvidenceUnitType.HEADLINE_SUMMARY),
    ("siemens_q2_fy2026_earnings_release", 2): PageSemantics("Siemens Group key figures", ("siemens_group",), ("Q2_2025", "Q2_2026"), "Siemens Q2 key figures", EvidenceUnitType.TABLE),
}

_METRIC_LABELS = {
    "henkel_sales": ("sales",),
    "henkel_nominal_sales_change": ("change versus previous year", "nominal"),
    "henkel_organic_sales_growth": ("organic",),
    "henkel_fx_effect": ("foreign exchange",),
    "henkel_acquisitions_divestments_effect": ("acquisitions/divestments", "acquisitions and divestments"),
    "henkel_price_contribution": ("of which price", "price and volume"),
    "henkel_volume_contribution": ("of which volume", "price and volume"),
    "mercedes_revenue": ("revenue",),
    "mercedes_ebit": ("ebit",),
    "mercedes_adjusted_ebit": ("ebit adjusted", "adjusted ebit"),
    "mercedes_unit_sales": ("unit sales",),
    "mercedes_bridge_volume_structure_net_pricing": ("volume / structure / net pricing",),
    "mercedes_bridge_foreign_exchange_rates": ("foreign exchange rates",),
    "mercedes_bridge_industrial_performance": ("industrial performance",),
    "mercedes_bridge_selling_expenses": ("selling expenses",),
    "mercedes_bridge_general_administrative_expenses": ("general administrative expenses",),
    "mercedes_bridge_research_noncapitalized_development": ("research & non-capitalized development", "research and non-capitalized development"),
    "mercedes_bridge_others": ("others",),
    "mercedes_bridge_adjustments": ("adjustments",),
    "mercedes_bridge_cost_of_credit_risk": ("cost of credit risk",),
    "mercedes_bridge_volume_margin": ("volume / margin",),
    "siemens_orders": ("orders", "order intake"),
    "siemens_revenue": ("revenue",),
    "siemens_profit_industrial_business": ("profit industrial business",),
    "siemens_profit_margin_industrial_business": ("profit margin industrial business",),
    "siemens_segment_profit": ("profit",),
    "siemens_segment_profit_margin": ("profit margin",),
}

_METRIC_OVERRIDES: dict[tuple[str, int], tuple[str, ...]] = {
    ("mercedes_q2_2026_fact_sheet_pdf", 4): ("mercedes_revenue", "mercedes_ebit"),
    ("mercedes_q2_2026_fact_sheet_pdf", 12): ("mercedes_bridge_adjustments",),
    ("mercedes_q2_2026_fact_sheet_pdf", 13): ("mercedes_adjusted_ebit",),
    ("mercedes_q2_2026_fact_sheet_pdf", 19): ("mercedes_revenue", "mercedes_ebit", "mercedes_adjusted_ebit", "mercedes_unit_sales"),
    ("mercedes_q2_2026_fact_sheet_pdf", 23): ("mercedes_revenue", "mercedes_ebit", "mercedes_adjusted_ebit", "mercedes_unit_sales"),
    ("mercedes_q2_2026_fact_sheet_pdf", 27): ("mercedes_revenue", "mercedes_ebit", "mercedes_adjusted_ebit"),
    ("mercedes_q2_2026_interim_report", 3): ("mercedes_revenue", "mercedes_ebit", "mercedes_adjusted_ebit"),
    ("mercedes_q2_2026_interim_report", 4): ("mercedes_revenue", "mercedes_ebit", "mercedes_adjusted_ebit"),
    ("mercedes_q2_2026_interim_report", 5): ("mercedes_revenue", "mercedes_ebit", "mercedes_adjusted_ebit"),
    ("mercedes_q2_2026_interim_report", 22): ("mercedes_bridge_adjustments",),
    ("mercedes_q2_2026_interim_report", 23): ("mercedes_bridge_adjustments",),
    ("siemens_q2_fy2026_earnings_release", 2): ("siemens_orders", "siemens_revenue", "siemens_profit_industrial_business", "siemens_profit_margin_industrial_business"),
}

_SIEMENS_SEGMENTS = (
    ("Digital Industries", "siemens_digital_industries", "Smart Infrastructure"),
    ("Smart Infrastructure", "siemens_smart_infrastructure", "Mobility"),
    ("Mobility", "siemens_mobility", "Siemens Healthineers"),
)


def _metric_ids(text: str, company: str) -> tuple[str, ...]:
    low = re.sub(r"\s+", " ", text.lower())
    prefix = "mercedes_" if company == "mercedes_benz_group" else f"{company}_"
    found = {mid for mid, labels in _METRIC_LABELS.items() if mid.startswith(prefix) and any(label in low for label in labels)}
    if "mercedes_adjusted_ebit" in found and ("ebit adjusted" in low or "adjusted ebit" in low):
        found.discard("mercedes_ebit")
    return tuple(sorted(found))


def _generic_semantics(source: dict[str, str], page_number: int, text: str) -> PageSemantics:
    company = source["company"]
    periods = ("H1_2025", "H1_2026") if company == "henkel" else ("Q2_2025", "Q2_2026", "H1_2025", "H1_2026")
    scope_prefix = "mercedes" if company == "mercedes_benz_group" else company
    scopes = (f"{scope_prefix}_group",)
    first = next((line.strip() for line in text.splitlines() if len(line.strip()) > 3), f"Page {page_number}")
    return PageSemantics(first[:120], scopes, periods, f"Page {page_number} extracted table")


def _printed_label(source_id: str, page_number: int, text: str) -> str:
    if source_id == "henkel_h1_2026_financial_report":
        return str(max(1, page_number - 1))
    return str(page_number)


def _is_table(text: str) -> bool:
    lines = [line for line in text.splitlines() if line.strip()]
    numeric = sum(bool(re.search(r"(?:\d[\d,.]*%?|[+-]\d)", line)) for line in lines)
    return numeric >= 5


def _table_headers(text: str, periods: tuple[str, ...]) -> tuple[str, ...]:
    candidates = []
    for period in periods:
        display = period.replace("_", " ")
        if display not in candidates:
            candidates.append(display)
    return tuple(candidates or ("Reported value",))


def parse_corpus(root: Path) -> list[EvidenceUnit]:
    manifest = list(csv.DictReader((root / "data/source_manifest.csv").open()))
    sources = {row["source_id"]: row for row in manifest if row["source_id"] in PDF_SOURCES}
    if set(sources) != set(PDF_SOURCES):
        raise ValueError("approved PDF corpus does not match the governed source manifest")
    units: list[EvidenceUnit] = []
    for source_id in PDF_SOURCES:
        source = sources[source_id]
        if source["company"] != _SOURCE_COMPANIES[source_id]:
            raise ValueError(f"invalid company/source combination: {source_id}")
        pdf_path = root / "data/raw_sources" / source["expected_filename"]
        if not pdf_path.exists():
            raise FileNotFoundError(pdf_path)
        reader = PdfReader(str(pdf_path))
        for page_number, page in enumerate(reader.pages, start=1):
            raw = page.extract_text() or ""
            text = normalize_text(raw)
            if not text:
                continue
            if source_id == "siemens_q2_fy2026_earnings_release" and page_number == 3:
                for ordinal, (label, scope_id, next_label) in enumerate(_SIEMENS_SEGMENTS, start=1):
                    start = text.find(label)
                    end = text.find(next_label, start + len(label))
                    block = text[start:end if end >= 0 else None] if start >= 0 else ""
                    if not block:
                        continue
                    units.append(make_evidence_unit(
                        source=source, page_number=page_number, printed_page_or_slide=str(page_number),
                        section=label, text=block, unit_type=EvidenceUnitType.TABLE,
                        relevance=EvidenceRelevance.REPORTED, ordinal=ordinal,
                        reporting_periods=("Q2_2025", "Q2_2026"), business_scopes=(scope_id,),
                        metric_ids=("siemens_orders", "siemens_revenue", "siemens_segment_profit", "siemens_segment_profit_margin"),
                        table_title=f"{label} Q2 key figures", table_headers=("Q2 FY 2026", "Q2 FY 2025"),
                    ))
                continue
            semantics = _PAGE_RULES.get((source_id, page_number), _generic_semantics(source, page_number, text))
            governed_page = (source_id, page_number) in _PAGE_RULES
            metrics = _METRIC_OVERRIDES.get((source_id, page_number), _metric_ids(text, source["company"]) if governed_page else ())
            printed = _printed_label(source_id, page_number, text)
            unit_type = semantics.unit_type or (EvidenceUnitType.TABLE if _is_table(text) else EvidenceUnitType.NARRATIVE_SECTION)
            relevance = EvidenceRelevance.MANAGEMENT_ATTRIBUTED if unit_type is EvidenceUnitType.BRIDGE_DECOMPOSITION else EvidenceRelevance.REPORTED
            primary_text = re.sub(r"\s+", " ", text) if unit_type is EvidenceUnitType.BRIDGE_DECOMPOSITION else text
            if "organic terms (i.e." in text.lower():
                units.append(make_evidence_unit(
                    source=source, page_number=page_number, printed_page_or_slide=printed,
                    section=semantics.section, subsection="Organic sales definition",
                    text="Organic sales growth is sales growth adjusted for foreign exchange effects and acquisitions/divestments.",
                    unit_type=EvidenceUnitType.METRIC_DEFINITION, relevance=EvidenceRelevance.DEFINITION,
                    ordinal=90, reporting_periods=semantics.periods, business_scopes=semantics.scopes,
                    metric_ids=("henkel_organic_sales_growth",), neighboring_context=text[:1000],
                ))
            units.append(make_evidence_unit(
                source=source, page_number=page_number, printed_page_or_slide=printed,
                section=semantics.section, text=primary_text, unit_type=unit_type, relevance=relevance,
                ordinal=0, reporting_periods=semantics.periods, business_scopes=semantics.scopes,
                metric_ids=metrics, table_title=semantics.table_title if unit_type in {EvidenceUnitType.TABLE, EvidenceUnitType.BRIDGE_DECOMPOSITION} else None,
                table_headers=_table_headers(text, semantics.periods) if unit_type is EvidenceUnitType.TABLE else (),
            ))
            if _is_table(text) and semantics.table_title:
                lines = [normalize_text(line) for line in raw.splitlines() if re.search(r"\d", line)]
                for ordinal, line in enumerate(lines[:12], start=1):
                    if len(line) < 12:
                        continue
                    units.append(make_evidence_unit(
                        source=source, page_number=page_number, printed_page_or_slide=printed,
                        section=semantics.section, text=line, unit_type=EvidenceUnitType.TABLE_ROW,
                        relevance=relevance, ordinal=ordinal, reporting_periods=semantics.periods,
                        business_scopes=semantics.scopes,
                        metric_ids=(_metric_ids(line, source["company"]) or metrics) if governed_page else (),
                        table_title=semantics.table_title, table_headers=_table_headers(text, semantics.periods),
                        neighboring_context=text[:700],
                    ))
            footnotes = [normalize_text(line) for line in raw.splitlines() if re.match(r"^\s*(?:\d+|\*)\s+\D", line)]
            for ordinal, line in enumerate(footnotes[:3], start=70):
                units.append(make_evidence_unit(
                    source=source, page_number=page_number, printed_page_or_slide=printed,
                    section=semantics.section, text=line, unit_type=EvidenceUnitType.FOOTNOTE,
                    relevance=EvidenceRelevance.LIMITATION, ordinal=ordinal,
                    reporting_periods=semantics.periods, business_scopes=semantics.scopes,
                    metric_ids=_metric_ids(line, source["company"]), neighboring_context=text[:500],
                ))
            method_lines = [line for line in text.splitlines() if any(p in line.lower() for p in ("adjusted for one-time", "correspond to", "ratio of", "including the impacts"))]
            if method_lines:
                units.append(make_evidence_unit(
                    source=source, page_number=page_number, printed_page_or_slide=printed,
                    section=semantics.section, text=" ".join(method_lines),
                    unit_type=EvidenceUnitType.GOVERNANCE_METHODOLOGY,
                    relevance=EvidenceRelevance.METHODOLOGY, ordinal=95,
                    reporting_periods=semantics.periods, business_scopes=semantics.scopes,
                    metric_ids=_metric_ids(" ".join(method_lines), source["company"]), neighboring_context=text[:700],
                ))
    with (root / "config/metric_catalog.csv").open() as handle:
        metric_families = {row["metric_id"]: row["canonical_family"] for row in csv.DictReader(handle)}
    return [
        unit.model_copy(update={
            "metric_families": tuple(sorted({metric_families[mid] for mid in unit.metric_ids if mid in metric_families}))
        })
        for unit in units
    ]
