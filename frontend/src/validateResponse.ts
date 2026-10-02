import type { QueryResponse } from './types'

const record = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v)
const strings = (v: unknown): v is string[] => Array.isArray(v) && v.every(x => typeof x === 'string')
const count = (v: unknown): v is number => typeof v === 'number' && Number.isSafeInteger(v) && v >= 0
const finite = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v) && v >= 0
const optionalString = (v: unknown) => v == null || typeof v === 'string'
const decimal = (v: unknown) => typeof v === 'string' && /^-?\d+(?:\.\d+)?$/.test(v)
const provenance = ['REPORTED', 'CALCULATED', 'MANAGEMENT_ATTRIBUTED', 'INTERPRETATION']

/** Validate the wire contract before any answer reaches the rendering boundary. */
export function validateQueryResponse(v: unknown): QueryResponse {
  const invalid = () => { throw new Error('Invalid or non-releasable verification response') }
  if (!record(v)) return invalid()
  for (const key of ['request_id', 'session_id', 'answer', 'provider', 'model']) if (typeof v[key] !== 'string') return invalid()
  if (!['COMPLETED', 'REFUSED', 'NEEDS_CLARIFICATION', 'EVIDENCE_CONFLICT', 'FAILED'].includes(String(v.status)) ||
      !['ANALYTICS_ONLY', 'KNOWLEDGE_ONLY', 'HYBRID', 'DECOMPOSITION_EXPLANATION', 'NEEDS_CLARIFICATION', 'UNSUPPORTED'].includes(String(v.route))) return invalid()
  if (!strings(v.limitations) || !finite(v.latency_ms) || !optionalString(v.clarification_question) || !optionalString(v.refusal_reason)) return invalid()
  if (!Array.isArray(v.claims) || !Array.isArray(v.citations) || !Array.isArray(v.provenance_summary)) return invalid()
  const counts = new Map<string, number>(); const ids = new Set<string>()
  for (const c of v.claims) {
    if (!record(c) || typeof c.claim_id !== 'string' || !c.claim_id || ids.has(c.claim_id) || typeof c.text !== 'string' || !c.text || !provenance.includes(String(c.provenance)) ||
        !strings(c.periods) || !strings(c.calculation_run_ids) || !strings(c.evidence_ids) || !Array.isArray(c.fact_ids) || !c.fact_ids.every(count) ||
        !['company_id', 'metric_id', 'business_scope', 'unit'].every(k => optionalString(c[k])) || (c.value != null && !decimal(c.value))) return invalid()
    if (c.unit != null && !['EUR_million', 'percentage_point', 'percent', 'vehicle'].includes(String(c.unit))) return invalid()
    if (c.value != null && (typeof c.unit !== 'string' || !c.unit)) return invalid()
    if (c.provenance === 'CALCULATED' && !c.calculation_run_ids.length) return invalid()
    ids.add(c.claim_id); counts.set(String(c.provenance), (counts.get(String(c.provenance)) ?? 0) + 1)
  }
  for (const c of v.citations) {
    if (!record(c) || !['evidence_unit_id', 'source_id', 'source_title', 'official_url', 'citation'].every(k => typeof c[k] === 'string') ||
        !count(c.page_number) || !['company_id', 'evidence_type', 'section'].every(k => optionalString(c[k]))) return invalid()
    try { if (!['https:', 'http:'].includes(new URL(String(c.official_url)).protocol)) return invalid() } catch { return invalid() }
  }
  const summaries = new Set<string>()
  for (const p of v.provenance_summary) {
    if (!record(p) || !provenance.includes(String(p.provenance)) || !count(p.count) || summaries.has(String(p.provenance)) || p.count !== (counts.get(String(p.provenance)) ?? 0)) return invalid()
    summaries.add(String(p.provenance))
  }
  if ([...counts.keys()].some(k => !summaries.has(k))) return invalid()
  const e = v.execution
  if (!record(e) || !['analytics_used', 'retrieval_used', 'revision_used'].every(k => typeof e[k] === 'boolean') ||
      !['provider_calls', 'verifier_interventions', 'input_tokens', 'output_tokens'].every(k => count(e[k])) || !decimal(e.cost_usd) || !finite(Number(e.cost_usd)) || !Array.isArray(e.stages)) return invalid()
  for (const s of e.stages) if (!record(s) || !count(s.order) || typeof s.label !== 'string' || !['completed', 'skipped', 'failed'].includes(String(s.status)) || (s.duration_ms != null && !finite(s.duration_ms))) return invalid()
  const verification = v.verification
  if (verification != null && (!record(verification) || !['PASS', 'NEEDS_REVISION', 'REFUSE'].includes(String(verification.verdict)) || typeof verification.label !== 'string' ||
      !count(verification.supported_claims) || !count(verification.total_claims) || verification.supported_claims > verification.total_claims || !strings(verification.errors))) return invalid()
  if (record(verification) && verification.verdict === 'PASS' && (v.status !== 'COMPLETED' || verification.supported_claims !== v.claims.length || !v.claims.length)) return invalid()
  if (v.status === 'COMPLETED') {
    if (!record(verification) || !v.claims.length || verification.supported_claims !== v.claims.length) return invalid()
    if (verification.verdict === 'PASS') {
      if (verification.total_claims !== v.claims.length || verification.label !== 'Verified' || (verification.errors as string[]).length) return invalid()
    } else if (verification.verdict === 'NEEDS_REVISION') {
      if (!['Supported subset returned', 'Verified with limitations'].includes(String(verification.label)) || !(verification.errors as string[]).length) return invalid()
    } else return invalid()
  } else if (v.claims.length) return invalid()
  // Additive approved-UI fields are also untrusted wire data, not a safe cast.
  const units = ['EUR_million', 'percentage_point', 'percent', 'vehicle']
  const fact = (f: unknown) => {
    if (!record(f) || !count(f.fact_id) || !decimal(f.value) || !units.includes(String(f.unit)) || !provenance.includes(String(f.provenance)) ||
        !['company_id', 'metric_id', 'label', 'business_scope', 'period', 'period_grain'].every(k => typeof f[k] === 'string') ||
        !optionalString(f.bridge_role) || (f.component_order != null && !count(f.component_order))) return invalid()
    // If a released claim names this fact's exact value, the display cannot contradict it.
    for (const c of v.claims as Record<string, unknown>[]) {
      if ((c.fact_ids as number[]).includes(f.fact_id as number) && c.provenance !== 'CALCULATED' && c.value != null &&
          (c.value !== f.value || c.unit !== f.unit || c.metric_id !== f.metric_id || c.company_id !== f.company_id || c.business_scope !== f.business_scope || !(c.periods as string[]).includes(String(f.period)))) return invalid()
    }
  }
  if (v.analytics != null) {
    const a = v.analytics
    if (v.status !== 'COMPLETED' || !record(a) || !['RETRIEVE', 'PERIOD_COMPARISON', 'DECOMPOSITION', 'RANKING', 'RECONCILIATION'].includes(String(a.operation)) ||
        !['changes', 'components', 'supporting', 'ranked', 'reconciliations'].every(k => Array.isArray(a[k])) ||
        !strings(a.calculation_run_ids) || !strings(a.warnings) || !strings(a.limitations)) return invalid()
    fact(a.primary); if (a.comparison != null) fact(a.comparison)
    for (const f of [...a.components as unknown[], ...a.supporting as unknown[]]) fact(f)
    for (const c of a.changes as unknown[]) {
      if (!record(c) || !['absolute', 'percent', 'percentage_point'].includes(String(c.kind)) || !decimal(c.value) || !units.includes(String(c.unit)) || !optionalString(c.calculation_run_id)) return invalid()
      const bound = (v.claims as Record<string, unknown>[]).filter(claim => (claim.calculation_run_ids as string[]).includes(String(c.calculation_run_id)))
      if (!bound.some(claim => claim.value === c.value && claim.unit === c.unit)) return invalid()
    }
    for (const r of a.ranked as unknown[]) {
      if (!record(r) || !count(r.rank) || !count(r.fact_id) || !decimal(r.value) || !units.includes(String(r.unit)) ||
          !provenance.includes(String(r.provenance)) || typeof r.metric_id !== 'string' || typeof r.label !== 'string') return invalid()
    }
    for (const r of a.reconciliations as unknown[]) {
      if (!record(r) || typeof r.rule_id !== 'string' || typeof r.calculation_run_id !== 'string' || typeof r.passed !== 'boolean' ||
          !['expected_value', 'calculated_value', 'absolute_difference', 'tolerance'].every(k => decimal(r[k])) ||
          !Array.isArray(r.source_fact_ids) || !r.source_fact_ids.every(count)) return invalid()
    }
  }
  if (v.fact_sources != null) {
    if (!Array.isArray(v.fact_sources) || (v.status !== 'COMPLETED' && v.fact_sources.length)) return invalid()
    for (const f of v.fact_sources) {
      if (!record(f) || !count(f.fact_id) || !['source_id', 'source_title', 'official_url', 'source_type', 'location', 'page_or_sheet', 'evidence_type'].every(k => typeof f[k] === 'string') || !optionalString(f.cell_or_range)) return invalid()
      try { if (!['https:', 'http:'].includes(new URL(String(f.official_url)).protocol)) return invalid() } catch { return invalid() }
    }
  }
  // This assertion follows exhaustive structural and release-invariant validation.
  return v as QueryResponse
}
