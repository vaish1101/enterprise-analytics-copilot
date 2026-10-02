// GENERATED from a governed test-mode run of the real pipeline (analytics, fact sources,
// citations) plus illustrative claim wording that restates governed values exactly.
// This is a SAMPLE for product storytelling. It is never presented as a live query:
// it carries no request id, latency, token counts or recorded stages.
import type { CatalogLabels, QueryResponse } from '../types'

export const SAMPLE_QUESTION = "What drove Mercedes-Benz Cars adjusted EBIT in Q2 2026?"

export const SAMPLE_RESPONSE: QueryResponse = {
  "request_id": "sample",
  "session_id": "sample",
  "status": "COMPLETED",
  "route": "DECOMPOSITION_EXPLANATION",
  "answer": "Adjusted EBIT at Mercedes-Benz Cars was €909 million in Q2 2026, against €1,228 million a year earlier. In management’s bridge the largest items were volume / structure / net pricing (−€602 million) and industrial performance (+€482 million). These are management attributions, not established causes.",
  "claims": [
    {
      "claim_id": "claim_001",
      "provenance": "REPORTED",
      "text": "Mercedes-Benz Cars reported adjusted EBIT of €909 million for Q2 2026.",
      "company_id": "mercedes_benz_group",
      "metric_id": "mercedes_adjusted_ebit",
      "business_scope": "mercedes_cars",
      "periods": [
        "Q2_2026"
      ],
      "value": "909",
      "unit": "EUR_million",
      "fact_ids": [
        110
      ],
      "calculation_run_ids": [],
      "evidence_ids": [
        "evidence_0110"
      ]
    },
    {
      "claim_id": "claim_002",
      "provenance": "REPORTED",
      "text": "Adjusted EBIT in the prior-year quarter, Q2 2025, was €1,228 million.",
      "company_id": "mercedes_benz_group",
      "metric_id": "mercedes_adjusted_ebit",
      "business_scope": "mercedes_cars",
      "periods": [
        "Q2_2025"
      ],
      "value": "1228",
      "unit": "EUR_million",
      "fact_ids": [
        109
      ],
      "calculation_run_ids": [],
      "evidence_ids": [
        "evidence_0109"
      ]
    },
    {
      "claim_id": "claim_003",
      "provenance": "MANAGEMENT_ATTRIBUTED",
      "text": "Management attributed −€602 million to volume / structure / net pricing, which is reported as one combined component.",
      "company_id": "mercedes_benz_group",
      "metric_id": "mercedes_bridge_volume_structure_net_pricing",
      "business_scope": "mercedes_cars",
      "periods": [
        "Q2_2026"
      ],
      "value": "-602",
      "unit": "EUR_million",
      "fact_ids": [
        141
      ],
      "calculation_run_ids": [],
      "evidence_ids": [
        "evidence_0141"
      ]
    },
    {
      "claim_id": "claim_004",
      "provenance": "MANAGEMENT_ATTRIBUTED",
      "text": "Management attributed +€482 million to industrial performance.",
      "company_id": "mercedes_benz_group",
      "metric_id": "mercedes_bridge_industrial_performance",
      "business_scope": "mercedes_cars",
      "periods": [
        "Q2_2026"
      ],
      "value": "482",
      "unit": "EUR_million",
      "fact_ids": [
        143
      ],
      "calculation_run_ids": [],
      "evidence_ids": [
        "evidence_0143"
      ]
    },
    {
      "claim_id": "claim_005",
      "provenance": "REPORTED",
      "text": "The Q2 2026 fact sheet presents the segment’s results in its “Adjusted performance” table.",
      "company_id": "mercedes_benz_group",
      "metric_id": null,
      "business_scope": "mercedes_cars",
      "periods": [
        "Q2_2026"
      ],
      "value": null,
      "unit": null,
      "fact_ids": [],
      "calculation_run_ids": [],
      "evidence_ids": [
        "eu_3ab7507262836f5e75ab6f73"
      ]
    }
  ],
  "citations": [
    {
      "evidence_unit_id": "eu_3ab7507262836f5e75ab6f73",
      "source_id": "mercedes_q2_2026_fact_sheet_pdf",
      "source_title": "Mercedes-Benz Group Fact Sheet Q2 2026 PDF",
      "official_url": "https://group.mercedes-benz.com/documents/investors/reports/interim-reports/q2/mercedes-benz-fact-sheet-q2-2026.pdf",
      "page_number": 13,
      "citation": "Mercedes-Benz Group Fact Sheet Q2 2026 PDF, page 13 (PDF 13), section: Adjusted performance, table: EBIT Adjusted and RoS/RoE Adjusted",
      "company_id": "mercedes_benz_group",
      "evidence_type": "TABLE",
      "section": "Adjusted performance"
    },
    {
      "evidence_unit_id": "eu_6a1d41a6cbac2324c7735822",
      "source_id": "mercedes_q2_2026_fact_sheet_pdf",
      "source_title": "Mercedes-Benz Group Fact Sheet Q2 2026 PDF",
      "official_url": "https://group.mercedes-benz.com/documents/investors/reports/interim-reports/q2/mercedes-benz-fact-sheet-q2-2026.pdf",
      "page_number": 19,
      "citation": "Mercedes-Benz Group Fact Sheet Q2 2026 PDF, page 19 (PDF 19), section: Mercedes-Benz Cars",
      "company_id": "mercedes_benz_group",
      "evidence_type": "FOOTNOTE",
      "section": "Mercedes-Benz Cars"
    },
    {
      "evidence_unit_id": "eu_8a25aa83889ad663f23268e0",
      "source_id": "mercedes_q2_2026_fact_sheet_pdf",
      "source_title": "Mercedes-Benz Group Fact Sheet Q2 2026 PDF",
      "official_url": "https://group.mercedes-benz.com/documents/investors/reports/interim-reports/q2/mercedes-benz-fact-sheet-q2-2026.pdf",
      "page_number": 19,
      "citation": "Mercedes-Benz Group Fact Sheet Q2 2026 PDF, page 19 (PDF 19), section: Mercedes-Benz Cars",
      "company_id": "mercedes_benz_group",
      "evidence_type": "GOVERNANCE_METHODOLOGY",
      "section": "Mercedes-Benz Cars"
    },
    {
      "evidence_unit_id": "eu_7ff720f6582865529821e01b",
      "source_id": "mercedes_q2_2026_interim_report",
      "source_title": "Mercedes-Benz Group Interim Report Q2 2026",
      "official_url": "https://group.mercedes-benz.com/documents/investors/reports/interim-reports/q2/mercedes-benz-interim-report-q2-2026.pdf",
      "page_number": 4,
      "citation": "Mercedes-Benz Group Interim Report Q2 2026, page 4 (PDF 4), section: Segment financial key figures",
      "company_id": "mercedes_benz_group",
      "evidence_type": "FOOTNOTE",
      "section": "Segment financial key figures"
    },
    {
      "evidence_unit_id": "eu_c42d28190ad9c61fa2f53b7d",
      "source_id": "mercedes_q2_2026_interim_report",
      "source_title": "Mercedes-Benz Group Interim Report Q2 2026",
      "official_url": "https://group.mercedes-benz.com/documents/investors/reports/interim-reports/q2/mercedes-benz-interim-report-q2-2026.pdf",
      "page_number": 4,
      "citation": "Mercedes-Benz Group Interim Report Q2 2026, page 4 (PDF 4), section: Segment financial key figures",
      "company_id": "mercedes_benz_group",
      "evidence_type": "GOVERNANCE_METHODOLOGY",
      "section": "Segment financial key figures"
    }
  ],
  "limitations": [
    "MANAGEMENT_ATTRIBUTION_NOT_CAUSAL",
    "COMBINED_COMPONENT_NOT_SPLIT"
  ],
  "verification": {
    "verdict": "PASS",
    "label": "Verified",
    "supported_claims": 5,
    "total_claims": 5,
    "errors": []
  },
  "provenance_summary": [
    {
      "provenance": "MANAGEMENT_ATTRIBUTED",
      "count": 2
    },
    {
      "provenance": "REPORTED",
      "count": 3
    }
  ],
  "execution": {
    "analytics_used": true,
    "retrieval_used": true,
    "revision_used": true,
    "provider_calls": 0,
    "verifier_interventions": 1,
    "input_tokens": 0,
    "output_tokens": 0,
    "cost_usd": "0",
    "stages": []
  },
  "latency_ms": 0,
  "provider": "sample",
  "model": "sample",
  "clarification_question": null,
  "refusal_reason": null,
  "analytics": {
    "operation": "DECOMPOSITION",
    "primary": {
      "fact_id": 110,
      "company_id": "mercedes_benz_group",
      "metric_id": "mercedes_adjusted_ebit",
      "label": "Adjusted EBIT",
      "business_scope": "mercedes_cars",
      "period": "Q2_2026",
      "period_grain": "QUARTER",
      "value": "909",
      "unit": "EUR_million",
      "provenance": "REPORTED",
      "bridge_role": "ADJUSTED_ENDPOINT",
      "component_order": 8
    },
    "comparison": null,
    "changes": [],
    "components": [
      {
        "fact_id": 141,
        "company_id": "mercedes_benz_group",
        "metric_id": "mercedes_bridge_volume_structure_net_pricing",
        "label": "Volume / structure / net pricing",
        "business_scope": "mercedes_cars",
        "period": "Q2_2026",
        "period_grain": "QUARTER_YOY",
        "value": "-602",
        "unit": "EUR_million",
        "provenance": "MANAGEMENT_ATTRIBUTED",
        "bridge_role": "COMPONENT",
        "component_order": 1
      },
      {
        "fact_id": 142,
        "company_id": "mercedes_benz_group",
        "metric_id": "mercedes_bridge_foreign_exchange_rates",
        "label": "Foreign exchange rates",
        "business_scope": "mercedes_cars",
        "period": "Q2_2026",
        "period_grain": "QUARTER_YOY",
        "value": "17",
        "unit": "EUR_million",
        "provenance": "MANAGEMENT_ATTRIBUTED",
        "bridge_role": "COMPONENT",
        "component_order": 2
      },
      {
        "fact_id": 143,
        "company_id": "mercedes_benz_group",
        "metric_id": "mercedes_bridge_industrial_performance",
        "label": "Industrial performance",
        "business_scope": "mercedes_cars",
        "period": "Q2_2026",
        "period_grain": "QUARTER_YOY",
        "value": "482",
        "unit": "EUR_million",
        "provenance": "MANAGEMENT_ATTRIBUTED",
        "bridge_role": "COMPONENT",
        "component_order": 3
      },
      {
        "fact_id": 144,
        "company_id": "mercedes_benz_group",
        "metric_id": "mercedes_bridge_selling_expenses",
        "label": "Selling expenses",
        "business_scope": "mercedes_cars",
        "period": "Q2_2026",
        "period_grain": "QUARTER_YOY",
        "value": "-194",
        "unit": "EUR_million",
        "provenance": "MANAGEMENT_ATTRIBUTED",
        "bridge_role": "COMPONENT",
        "component_order": 4
      },
      {
        "fact_id": 145,
        "company_id": "mercedes_benz_group",
        "metric_id": "mercedes_bridge_general_administrative_expenses",
        "label": "General administrative expenses",
        "business_scope": "mercedes_cars",
        "period": "Q2_2026",
        "period_grain": "QUARTER_YOY",
        "value": "-28",
        "unit": "EUR_million",
        "provenance": "MANAGEMENT_ATTRIBUTED",
        "bridge_role": "COMPONENT",
        "component_order": 5
      },
      {
        "fact_id": 146,
        "company_id": "mercedes_benz_group",
        "metric_id": "mercedes_bridge_research_noncapitalized_development",
        "label": "Research & non-capitalized development costs",
        "business_scope": "mercedes_cars",
        "period": "Q2_2026",
        "period_grain": "QUARTER_YOY",
        "value": "143",
        "unit": "EUR_million",
        "provenance": "MANAGEMENT_ATTRIBUTED",
        "bridge_role": "COMPONENT",
        "component_order": 6
      },
      {
        "fact_id": 147,
        "company_id": "mercedes_benz_group",
        "metric_id": "mercedes_bridge_others",
        "label": "Others",
        "business_scope": "mercedes_cars",
        "period": "Q2_2026",
        "period_grain": "QUARTER_YOY",
        "value": "-137",
        "unit": "EUR_million",
        "provenance": "MANAGEMENT_ATTRIBUTED",
        "bridge_role": "COMPONENT",
        "component_order": 7
      }
    ],
    "supporting": [
      {
        "fact_id": 109,
        "company_id": "mercedes_benz_group",
        "metric_id": "mercedes_adjusted_ebit",
        "label": "Adjusted EBIT",
        "business_scope": "mercedes_cars",
        "period": "Q2_2025",
        "period_grain": "QUARTER",
        "value": "1228",
        "unit": "EUR_million",
        "provenance": "REPORTED",
        "bridge_role": "START",
        "component_order": 0
      },
      {
        "fact_id": 110,
        "company_id": "mercedes_benz_group",
        "metric_id": "mercedes_adjusted_ebit",
        "label": "Adjusted EBIT",
        "business_scope": "mercedes_cars",
        "period": "Q2_2026",
        "period_grain": "QUARTER",
        "value": "909",
        "unit": "EUR_million",
        "provenance": "REPORTED",
        "bridge_role": "ADJUSTED_ENDPOINT",
        "component_order": 8
      },
      {
        "fact_id": 148,
        "company_id": "mercedes_benz_group",
        "metric_id": "mercedes_bridge_adjustments",
        "label": "Adjustments",
        "business_scope": "mercedes_cars",
        "period": "Q2_2026",
        "period_grain": "QUARTER",
        "value": "-860",
        "unit": "EUR_million",
        "provenance": "REPORTED",
        "bridge_role": "ADJUSTMENT",
        "component_order": 9
      },
      {
        "fact_id": 106,
        "company_id": "mercedes_benz_group",
        "metric_id": "mercedes_ebit",
        "label": "EBIT",
        "business_scope": "mercedes_cars",
        "period": "Q2_2026",
        "period_grain": "QUARTER",
        "value": "49",
        "unit": "EUR_million",
        "provenance": "REPORTED",
        "bridge_role": "REPORTED_ENDPOINT",
        "component_order": 10
      }
    ],
    "ranked": [],
    "reconciliations": [
      {
        "rule_id": "MERCEDES_EBIT_BRIDGE_V1",
        "expected_value": "909",
        "calculated_value": "909",
        "absolute_difference": "0",
        "tolerance": "0",
        "passed": true,
        "source_fact_ids": [
          109,
          141,
          142,
          143,
          144,
          145,
          146,
          147,
          110
        ],
        "calculation_run_id": "run_a8ac25c4390dd8bb"
      },
      {
        "rule_id": "MERCEDES_ADJUSTED_TO_REPORTED_EBIT_V1",
        "expected_value": "49",
        "calculated_value": "49",
        "absolute_difference": "0",
        "tolerance": "0",
        "passed": true,
        "source_fact_ids": [
          110,
          148,
          106
        ],
        "calculation_run_id": "run_0e76c2fac011f8dc"
      }
    ],
    "calculation_run_ids": [
      "run_a8ac25c4390dd8bb",
      "run_0e76c2fac011f8dc"
    ],
    "warnings": [],
    "limitations": [
      "MANAGEMENT_ATTRIBUTION_NOT_CAUSAL",
      "COMBINED_COMPONENT_NOT_SPLIT"
    ]
  },
  "fact_sources": [
    {
      "fact_id": 110,
      "source_id": "mercedes_q2_2026_fact_sheet_xlsx",
      "source_title": "Mercedes-Benz Group Fact Sheet Q2 2026 XLSX",
      "official_url": "https://group.mercedes-benz.com/documents/investors/reports/interim-reports/q2/mercedes-benz-fact-sheet-q2-2026.xlsx",
      "source_type": "xlsx",
      "location": "MBC Overview",
      "page_or_sheet": "Sheet 19",
      "cell_or_range": "G15 and J15",
      "evidence_type": "CORROBORATING_NUMERIC"
    },
    {
      "fact_id": 141,
      "source_id": "mercedes_q2_2026_capital_market_presentation",
      "source_title": "Mercedes-Benz Group Capital Market Presentation Q2 2026",
      "official_url": "https://group.mercedes-benz.com/dokumente/investoren/praesentationen/mercedes-benz-ir-capitalmarketpresentation-q2-2026.pdf",
      "source_type": "pdf",
      "location": "Mercedes-Benz Cars EBIT and RoS bridge",
      "page_or_sheet": "PDF page 8",
      "cell_or_range": null,
      "evidence_type": "MANAGEMENT_BRIDGE"
    },
    {
      "fact_id": 142,
      "source_id": "mercedes_q2_2026_capital_market_presentation",
      "source_title": "Mercedes-Benz Group Capital Market Presentation Q2 2026",
      "official_url": "https://group.mercedes-benz.com/dokumente/investoren/praesentationen/mercedes-benz-ir-capitalmarketpresentation-q2-2026.pdf",
      "source_type": "pdf",
      "location": "Mercedes-Benz Cars EBIT and RoS bridge",
      "page_or_sheet": "PDF page 8",
      "cell_or_range": null,
      "evidence_type": "MANAGEMENT_BRIDGE"
    },
    {
      "fact_id": 143,
      "source_id": "mercedes_q2_2026_capital_market_presentation",
      "source_title": "Mercedes-Benz Group Capital Market Presentation Q2 2026",
      "official_url": "https://group.mercedes-benz.com/dokumente/investoren/praesentationen/mercedes-benz-ir-capitalmarketpresentation-q2-2026.pdf",
      "source_type": "pdf",
      "location": "Mercedes-Benz Cars EBIT and RoS bridge",
      "page_or_sheet": "PDF page 8",
      "cell_or_range": null,
      "evidence_type": "MANAGEMENT_BRIDGE"
    },
    {
      "fact_id": 144,
      "source_id": "mercedes_q2_2026_capital_market_presentation",
      "source_title": "Mercedes-Benz Group Capital Market Presentation Q2 2026",
      "official_url": "https://group.mercedes-benz.com/dokumente/investoren/praesentationen/mercedes-benz-ir-capitalmarketpresentation-q2-2026.pdf",
      "source_type": "pdf",
      "location": "Mercedes-Benz Cars EBIT and RoS bridge",
      "page_or_sheet": "PDF page 8",
      "cell_or_range": null,
      "evidence_type": "MANAGEMENT_BRIDGE"
    },
    {
      "fact_id": 145,
      "source_id": "mercedes_q2_2026_capital_market_presentation",
      "source_title": "Mercedes-Benz Group Capital Market Presentation Q2 2026",
      "official_url": "https://group.mercedes-benz.com/dokumente/investoren/praesentationen/mercedes-benz-ir-capitalmarketpresentation-q2-2026.pdf",
      "source_type": "pdf",
      "location": "Mercedes-Benz Cars EBIT and RoS bridge",
      "page_or_sheet": "PDF page 8",
      "cell_or_range": null,
      "evidence_type": "MANAGEMENT_BRIDGE"
    },
    {
      "fact_id": 146,
      "source_id": "mercedes_q2_2026_capital_market_presentation",
      "source_title": "Mercedes-Benz Group Capital Market Presentation Q2 2026",
      "official_url": "https://group.mercedes-benz.com/dokumente/investoren/praesentationen/mercedes-benz-ir-capitalmarketpresentation-q2-2026.pdf",
      "source_type": "pdf",
      "location": "Mercedes-Benz Cars EBIT and RoS bridge",
      "page_or_sheet": "PDF page 8",
      "cell_or_range": null,
      "evidence_type": "MANAGEMENT_BRIDGE"
    },
    {
      "fact_id": 147,
      "source_id": "mercedes_q2_2026_capital_market_presentation",
      "source_title": "Mercedes-Benz Group Capital Market Presentation Q2 2026",
      "official_url": "https://group.mercedes-benz.com/dokumente/investoren/praesentationen/mercedes-benz-ir-capitalmarketpresentation-q2-2026.pdf",
      "source_type": "pdf",
      "location": "Mercedes-Benz Cars EBIT and RoS bridge",
      "page_or_sheet": "PDF page 8",
      "cell_or_range": null,
      "evidence_type": "MANAGEMENT_BRIDGE"
    },
    {
      "fact_id": 109,
      "source_id": "mercedes_q2_2026_fact_sheet_xlsx",
      "source_title": "Mercedes-Benz Group Fact Sheet Q2 2026 XLSX",
      "official_url": "https://group.mercedes-benz.com/documents/investors/reports/interim-reports/q2/mercedes-benz-fact-sheet-q2-2026.xlsx",
      "source_type": "xlsx",
      "location": "MBC Overview",
      "page_or_sheet": "Sheet 19",
      "cell_or_range": "C15 and I15",
      "evidence_type": "CORROBORATING_NUMERIC"
    },
    {
      "fact_id": 148,
      "source_id": "mercedes_q2_2026_capital_market_presentation",
      "source_title": "Mercedes-Benz Group Capital Market Presentation Q2 2026",
      "official_url": "https://group.mercedes-benz.com/dokumente/investoren/praesentationen/mercedes-benz-ir-capitalmarketpresentation-q2-2026.pdf",
      "source_type": "pdf",
      "location": "Mercedes-Benz Cars adjustment bar",
      "page_or_sheet": "PDF page 8",
      "cell_or_range": null,
      "evidence_type": "MANAGEMENT_BRIDGE"
    },
    {
      "fact_id": 106,
      "source_id": "mercedes_q2_2026_fact_sheet_xlsx",
      "source_title": "Mercedes-Benz Group Fact Sheet Q2 2026 XLSX",
      "official_url": "https://group.mercedes-benz.com/documents/investors/reports/interim-reports/q2/mercedes-benz-fact-sheet-q2-2026.xlsx",
      "source_type": "xlsx",
      "location": "MBC Overview",
      "page_or_sheet": "Sheet 19",
      "cell_or_range": "G14 and J14",
      "evidence_type": "CORROBORATING_NUMERIC"
    }
  ]
}

export const SAMPLE_LABELS: CatalogLabels = {
  "metrics": {
    "henkel_acquisitions_divestments_effect": {
      "label": "Acquisitions / divestments effect",
      "reported_name": "Acquisitions/divestments",
      "unit": "percentage_point",
      "company_id": "henkel"
    },
    "henkel_fx_effect": {
      "label": "Foreign exchange effect",
      "reported_name": "Foreign exchange",
      "unit": "percentage_point",
      "company_id": "henkel"
    },
    "henkel_nominal_sales_change": {
      "label": "Nominal sales growth",
      "reported_name": "Change versus previous year",
      "unit": "percentage_point",
      "company_id": "henkel"
    },
    "henkel_organic_sales_growth": {
      "label": "Organic sales growth",
      "reported_name": "Organic",
      "unit": "percentage_point",
      "company_id": "henkel"
    },
    "henkel_price_contribution": {
      "label": "Price contribution to organic growth",
      "reported_name": "Of which price",
      "unit": "percentage_point",
      "company_id": "henkel"
    },
    "henkel_sales": {
      "label": "Sales",
      "reported_name": "Sales",
      "unit": "EUR_million",
      "company_id": "henkel"
    },
    "henkel_volume_contribution": {
      "label": "Volume contribution to organic growth",
      "reported_name": "Of which volume",
      "unit": "percentage_point",
      "company_id": "henkel"
    },
    "mercedes_adjusted_ebit": {
      "label": "Adjusted EBIT",
      "reported_name": "Adjusted EBIT",
      "unit": "EUR_million",
      "company_id": "mercedes_benz_group"
    },
    "mercedes_bridge_adjustments": {
      "label": "Adjustments",
      "reported_name": "Adjustments",
      "unit": "EUR_million",
      "company_id": "mercedes_benz_group"
    },
    "mercedes_bridge_cost_of_credit_risk": {
      "label": "Cost of credit risk",
      "reported_name": "Cost of credit risk",
      "unit": "EUR_million",
      "company_id": "mercedes_benz_group"
    },
    "mercedes_bridge_foreign_exchange_rates": {
      "label": "Foreign exchange rates",
      "reported_name": "Foreign exchange rates",
      "unit": "EUR_million",
      "company_id": "mercedes_benz_group"
    },
    "mercedes_bridge_general_administrative_expenses": {
      "label": "General administrative expenses",
      "reported_name": "General administrative expenses",
      "unit": "EUR_million",
      "company_id": "mercedes_benz_group"
    },
    "mercedes_bridge_industrial_performance": {
      "label": "Industrial performance",
      "reported_name": "Industrial performance",
      "unit": "EUR_million",
      "company_id": "mercedes_benz_group"
    },
    "mercedes_bridge_others": {
      "label": "Others",
      "reported_name": "Others",
      "unit": "EUR_million",
      "company_id": "mercedes_benz_group"
    },
    "mercedes_bridge_research_noncapitalized_development": {
      "label": "Research & non-capitalized development costs",
      "reported_name": "Research & non-capitalized development costs",
      "unit": "EUR_million",
      "company_id": "mercedes_benz_group"
    },
    "mercedes_bridge_selling_expenses": {
      "label": "Selling expenses",
      "reported_name": "Selling expenses",
      "unit": "EUR_million",
      "company_id": "mercedes_benz_group"
    },
    "mercedes_bridge_volume_margin": {
      "label": "Volume / margin",
      "reported_name": "Volume / margin",
      "unit": "EUR_million",
      "company_id": "mercedes_benz_group"
    },
    "mercedes_bridge_volume_structure_net_pricing": {
      "label": "Volume / structure / net pricing",
      "reported_name": "Volume / structure / net pricing",
      "unit": "EUR_million",
      "company_id": "mercedes_benz_group"
    },
    "mercedes_ebit": {
      "label": "EBIT",
      "reported_name": "EBIT",
      "unit": "EUR_million",
      "company_id": "mercedes_benz_group"
    },
    "mercedes_revenue": {
      "label": "Revenue",
      "reported_name": "Revenue",
      "unit": "EUR_million",
      "company_id": "mercedes_benz_group"
    },
    "mercedes_unit_sales": {
      "label": "Unit sales",
      "reported_name": "Unit sales",
      "unit": "vehicle",
      "company_id": "mercedes_benz_group"
    },
    "siemens_orders": {
      "label": "Orders",
      "reported_name": "Orders",
      "unit": "EUR_million",
      "company_id": "siemens"
    },
    "siemens_profit_industrial_business": {
      "label": "Industrial Business profit",
      "reported_name": "Profit Industrial Business",
      "unit": "EUR_million",
      "company_id": "siemens"
    },
    "siemens_profit_margin_industrial_business": {
      "label": "Industrial Business profit margin",
      "reported_name": "Profit margin Industrial Business",
      "unit": "percentage_point",
      "company_id": "siemens"
    },
    "siemens_revenue": {
      "label": "Revenue",
      "reported_name": "Revenue",
      "unit": "EUR_million",
      "company_id": "siemens"
    },
    "siemens_segment_profit": {
      "label": "Segment profit",
      "reported_name": "Profit",
      "unit": "EUR_million",
      "company_id": "siemens"
    },
    "siemens_segment_profit_margin": {
      "label": "Segment profit margin",
      "reported_name": "Profit margin",
      "unit": "percentage_point",
      "company_id": "siemens"
    }
  },
  "scopes": {
    "henkel_adhesive_technologies": {
      "label": "Adhesive Technologies",
      "company_id": "henkel",
      "scope_type": "BUSINESS_UNIT"
    },
    "henkel_consumer_brands": {
      "label": "Consumer Brands",
      "company_id": "henkel",
      "scope_type": "BUSINESS_UNIT"
    },
    "henkel_craftsmen_construction_professional": {
      "label": "Craftsmen, Construction & Professional",
      "company_id": "henkel",
      "scope_type": "BUSINESS_AREA"
    },
    "henkel_group": {
      "label": "Henkel Group",
      "company_id": "henkel",
      "scope_type": "GROUP"
    },
    "henkel_hair": {
      "label": "Hair",
      "company_id": "henkel",
      "scope_type": "BUSINESS_AREA"
    },
    "henkel_laundry_home_care": {
      "label": "Laundry & Home Care",
      "company_id": "henkel",
      "scope_type": "BUSINESS_AREA"
    },
    "henkel_mobility_electronics": {
      "label": "Mobility & Electronics",
      "company_id": "henkel",
      "scope_type": "BUSINESS_AREA"
    },
    "henkel_other_consumer_businesses": {
      "label": "Other Consumer Businesses",
      "company_id": "henkel",
      "scope_type": "BUSINESS_AREA"
    },
    "henkel_packaging_consumer_goods": {
      "label": "Packaging & Consumer Goods",
      "company_id": "henkel",
      "scope_type": "BUSINESS_AREA"
    },
    "mercedes_cars": {
      "label": "Mercedes-Benz Cars",
      "company_id": "mercedes_benz_group",
      "scope_type": "SEGMENT"
    },
    "mercedes_financial_services": {
      "label": "Mercedes-Benz Mobility",
      "company_id": "mercedes_benz_group",
      "scope_type": "SEGMENT"
    },
    "mercedes_group": {
      "label": "Mercedes-Benz Group",
      "company_id": "mercedes_benz_group",
      "scope_type": "GROUP"
    },
    "mercedes_vans": {
      "label": "Mercedes-Benz Vans",
      "company_id": "mercedes_benz_group",
      "scope_type": "SEGMENT"
    },
    "siemens_digital_industries": {
      "label": "Digital Industries",
      "company_id": "siemens",
      "scope_type": "SEGMENT"
    },
    "siemens_group": {
      "label": "Siemens Group",
      "company_id": "siemens",
      "scope_type": "GROUP"
    },
    "siemens_mobility": {
      "label": "Siemens Mobility",
      "company_id": "siemens",
      "scope_type": "SEGMENT"
    },
    "siemens_smart_infrastructure": {
      "label": "Smart Infrastructure",
      "company_id": "siemens",
      "scope_type": "SEGMENT"
    }
  },
  "periods": [
    {
      "company_id": "henkel",
      "period_id": "H1_2025",
      "period_grain": "HALF_YEAR",
      "label": "H1 2025",
      "fiscal": false
    },
    {
      "company_id": "henkel",
      "period_id": "H1_2026",
      "period_grain": "HALF_YEAR",
      "label": "H1 2026",
      "fiscal": false
    },
    {
      "company_id": "henkel",
      "period_id": "Q2_2025",
      "period_grain": "QUARTER",
      "label": "Q2 2025",
      "fiscal": false
    },
    {
      "company_id": "henkel",
      "period_id": "Q2_2026",
      "period_grain": "QUARTER",
      "label": "Q2 2026",
      "fiscal": false
    },
    {
      "company_id": "mercedes_benz_group",
      "period_id": "H1_2025",
      "period_grain": "HALF_YEAR",
      "label": "H1 2025",
      "fiscal": false
    },
    {
      "company_id": "mercedes_benz_group",
      "period_id": "H1_2026",
      "period_grain": "HALF_YEAR",
      "label": "H1 2026",
      "fiscal": false
    },
    {
      "company_id": "mercedes_benz_group",
      "period_id": "Q2_2025",
      "period_grain": "QUARTER",
      "label": "Q2 2025",
      "fiscal": false
    },
    {
      "company_id": "mercedes_benz_group",
      "period_id": "Q2_2026",
      "period_grain": "QUARTER",
      "label": "Q2 2026",
      "fiscal": false
    },
    {
      "company_id": "mercedes_benz_group",
      "period_id": "Q2_2026",
      "period_grain": "QUARTER_YOY",
      "label": "Q2 2026 vs Q2 2025",
      "fiscal": false
    },
    {
      "company_id": "siemens",
      "period_id": "Q2_2025",
      "period_grain": "QUARTER",
      "label": "Q2 FY2025",
      "fiscal": true
    },
    {
      "company_id": "siemens",
      "period_id": "Q2_2026",
      "period_grain": "QUARTER",
      "label": "Q2 FY2026",
      "fiscal": true
    }
  ]
}
