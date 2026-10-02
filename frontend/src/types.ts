export type Claim = {
  claim_id: string; provenance: string; text: string; company_id?: string | null; metric_id?: string | null;
  business_scope?: string | null; periods: string[]; value?: string | null; unit?: string | null; fact_ids: number[];
  calculation_run_ids: string[]; evidence_ids: string[];
}

export type Citation = {
  evidence_unit_id: string; source_id: string; source_title: string; official_url: string;
  page_number: number; citation: string; company_id?: string | null; evidence_type?: string | null; section?: string | null;
}

export type AnalyticsFact = {
  fact_id: number; company_id: string; metric_id: string; label: string; business_scope: string;
  period: string; period_grain: string; value: string; unit: string; provenance: string;
  bridge_role?: string | null; component_order?: number | null;
}

export type Analytics = {
  operation: string
  primary: AnalyticsFact
  comparison?: AnalyticsFact | null
  changes: { kind: 'absolute' | 'percent' | 'percentage_point'; value: string; unit: string; calculation_run_id?: string | null }[]
  components: AnalyticsFact[]
  supporting: AnalyticsFact[]
  ranked: { rank: number; fact_id: number; metric_id: string; label: string; value: string; unit: string; provenance: string }[]
  reconciliations: {
    rule_id: string; expected_value: string; calculated_value: string; absolute_difference: string;
    tolerance: string; passed: boolean; source_fact_ids: number[]; calculation_run_id: string
  }[]
  calculation_run_ids: string[]; warnings: string[]; limitations: string[]
}

export type FactSource = {
  fact_id: number; source_id: string; source_title: string; official_url: string; source_type: string;
  location: string; page_or_sheet: string; cell_or_range?: string | null; evidence_type: string;
}

export type QueryResponse = {
  request_id: string; session_id: string; status: string; route: string; answer: string;
  claims: Claim[]; citations: Citation[]; limitations: string[];
  verification: null | { verdict: string; label: string; supported_claims: number; total_claims: number; errors: string[] };
  provenance_summary: { provenance: string; count: number }[];
  execution: { analytics_used: boolean; retrieval_used: boolean; revision_used: boolean; provider_calls: number;
    verifier_interventions: number; input_tokens: number; output_tokens: number; cost_usd: string;
    stages: { order: number; label: string; status: string; duration_ms?: number | null }[] };
  latency_ms: number; provider: string; model: string; clarification_question?: string | null; refusal_reason?: string | null;
  analytics?: Analytics | null; fact_sources?: FactSource[];
  clarification_options?: { label: string; detail: string; question: string }[];
  alternatives?: { label: string; question: string }[];
}

export type CatalogLabels = {
  metrics: Record<string, { label: string; reported_name?: string; unit: string; company_id: string }>
  scopes: Record<string, { label: string; company_id: string; scope_type?: string | null }>
  periods: { company_id: string; period_id: string; period_grain: string; label: string; fiscal: boolean }[]
}

export type Metadata = {
  system_version: string; headline: string;
  companies: { id: string; name: string; periods: string[]; scopes: string[] }[];
  examples: { category: string; questions: string[] }[];
  retrieval_model: string; retrieval_method: string; retrieval_version: string; top_k: number;
  graph_version: string; verifier_version: string; demo_mode: boolean; rights_notice: string;
  labels?: CatalogLabels; provider_mode?: 'test' | 'live';
}
