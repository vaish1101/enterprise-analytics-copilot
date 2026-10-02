import type { Analytics, AnalyticsFact, CatalogLabels, Citation, Claim, FactSource, QueryResponse } from '../types'
import { METRIC_DE, periodLabel, strings, type Lang } from '../i18n/strings'
import { formatValue, isGovernedDecimal, magnitude, unitName } from './format'
import { plainOutcome, type PlainOutcome } from './plain'
import { deriveVerification, type VerificationView } from './verification'
import { buildInterpretation, type InterpretationItem } from './interpretation'
import { buildWorkflow, type Workflow } from './workflow'

/**
 * The single boundary between API transport and visual components.
 *
 * Every field is a deterministic mapping of explicit response fields. Nothing here
 * parses prose, guesses structure from claim order, or computes new analytics.
 */

export type SupportKind = 'fact' | 'calculation' | 'document' | 'management' | 'interpretation' | 'limitation'

/** How the result is composed for this kind of question. Empty regions are never rendered. */
export type Composition = 'fact' | 'comparison' | 'decomposition' | 'document' | 'findings' | 'none'

export type CitationView = Citation & { index: number; claimIds: string[] }

export type FindingView = {
  id: string
  index: number
  text: string
  provenance: string
  support: SupportKind[]
  citationIndexes: number[]
  factIds: number[]
  value?: string | null
  unit?: string | null
  company?: string
  scope?: string
  metric?: string
  periods: string[]
}

export type KpiView = {
  key: string
  label: string
  period: string
  value: string
  unit: string
  support: SupportKind
  factId?: number
  /** Calculated figures open their calculation lineage instead of a fact source. */
  calcKey?: string
  role: 'primary' | 'secondary'
  signed: boolean
}

export type BarView = { key: string; factId: number; label: string; value: string; unit: string; order: number; provenance: string }

export type VisualView =
  | { kind: 'bridge'; unit: string; start: BarView; end: BarView; components: BarView[]; periodLabel: string; startLabel: string; endLabel: string; reconciled: boolean }
  | { kind: 'decomposition'; unit: string; total: BarView; components: BarView[]; periodLabel: string; reconciliation: Analytics['reconciliations'][number] | null }
  | { kind: 'ranking'; unit: string; bars: (BarView & { rank: number })[]; periodLabel: string }
  | { kind: 'comparison'; unit: string; bars: BarView[]; change: Analytics['changes'][number] | null; metricLabel: string }

export type ContextView = { company?: string; scope?: string; metric?: string; period?: string; unit?: string; route: string }
export type LimitationView = { key: string; text: string }
export type FactView = { factId: number; label: string; value: string; unit: string; period: string; provenance: string; scope?: string }
export type CalculationView = {
  key: string; title: string; expression: string; unit: string; runId: string
  /** Reconciliation checks carry a reported value to compare with; changes do not. */
  expected?: string; calculated: string; tolerance?: string; passed?: boolean
  inputs: number[]
}

/**
 * The kind of question, read from explicit response fields (operation, route, cited
 * evidence types). Drives which instrument channels animate and which visual is used.
 */
export type Family = 'driver' | 'breakdown' | 'ranking' | 'comparison' | 'fact' | 'definition' | 'document' | 'findings'
  | 'clarification' | 'unsupported' | 'failure'

/** Deterministic, plain-language lead built only from governed values in the response. */
export type KeyRow = { label: string; value: string; factId?: number }
export type Lead = {
  changed: string | null; contributed: string | null; attribution: boolean; answerFindings: boolean
  /** The few values that carry the answer (largest reported items, components). */
  rows: KeyRow[]
  /** Period comparison: the governed change is the headline. */
  delta: { abs: string; pct: string | null; calcKey?: string } | null
  periods: KeyRow[]
  /** A documentary answer that only points at where the reporting covers the topic. */
  located: boolean
}

export type ResultView = {
  /** sample: recorded demo; test: deterministic test provider; live: configured model provider. */
  kind: 'sample' | 'test' | 'live'
  kindLabel: string
  kindNote: string
  lang: Lang
  family: Family
  /** Both governed analytics and company reporting contributed to the answer. */
  hybrid: boolean
  lead: Lead
  plain: PlainOutcome | null
  question: string
  interpretedAs: string | null
  sessionId?: string
  composition: Composition
  documentary: boolean
  context: ContextView
  summary: string | null
  message: string | null
  options: { label: string; detail: string; question: string }[]
  alternatives: { label: string; question: string }[]
  kpis: KpiView[]
  visual: VisualView | null
  partialNote: string | null
  findings: FindingView[]
  limitations: LimitationView[]
  /** Passages cited by at least one released finding. */
  citations: CitationView[]
  /** Passages retrieved for context but not cited by any released finding. */
  contextPassages: CitationView[]
  sourceCount: number
  factSources: Record<number, FactSource>
  facts: Record<number, FactView>
  calculations: CalculationView[]
  verification: VerificationView
  trace: QueryResponse['execution']['stages'] | null
  execution: ExecutionView | null
  /** The route this response took through the roles, read from its own metadata. */
  workflow: Workflow
  /** How to read the result; empty when nothing needs qualifying. */
  interpretation: InterpretationItem[]
}

/** Actual recorded execution for a live response: only branches that ran. */
export type ExecutionView = {
  analytics: boolean; retrieval: boolean; synthesis: boolean; verification: boolean; revised: boolean
  outcome: 'released' | 'subset' | 'clarification' | 'refused' | 'conflict' | 'failed'
}

function buildExecution(response: QueryResponse, verification: VerificationView): ExecutionView {
  const labels = new Set(response.execution.stages.map(stage => stage.label))
  const outcome: ExecutionView['outcome'] = labels.has('Workflow failed safely') || verification.state === 'system_failure' ? 'failed'
    : verification.state === 'clarification' ? 'clarification' : verification.state === 'refused' ? 'refused'
    : verification.state === 'evidence_conflict' ? 'conflict' : verification.state === 'subset' ? 'subset' : 'released'
  return {
    analytics: response.execution.analytics_used, retrieval: response.execution.retrieval_used,
    synthesis: labels.has('Structured draft generated'), verification: labels.has('Independent verification completed'),
    revised: response.execution.revision_used, outcome,
  }
}

const PROVENANCE_SUPPORT: Record<string, string> = {
  REPORTED: 'fact', CALCULATED: 'calculation', MANAGEMENT_ATTRIBUTED: 'management', INTERPRETATION: 'interpretation', LIMITATION: 'limitation',
}
export const provenanceLabel = (provenance: string, lang: Lang = 'en') => strings(lang).support[PROVENANCE_SUPPORT[provenance] ?? 'fact'][0]

const CALCULATION_TITLE: Record<Lang, Record<string, string>> = {
  en: { MERCEDES_EBIT_BRIDGE_V1: 'Bridge reconciliation', HENKEL_ORGANIC_RECONCILIATION_V1: 'Organic growth = price + volume', HENKEL_NOMINAL_BRIDGE_V1: 'Nominal change = FX + portfolio + organic' },
  de: { MERCEDES_EBIT_BRIDGE_V1: 'Abstimmung der Überleitung', HENKEL_ORGANIC_RECONCILIATION_V1: 'Organisches Wachstum = Preis + Volumen', HENKEL_NOMINAL_BRIDGE_V1: 'Nominale Veränderung = Währung + Portfolio + organisch' },
}
const CALC_TEXT: Record<Lang, { change: string; changePct: string; changePp: string; later: string; ratio: string; rate: string; bridge: string; sum: string; partial: string; figure: string }> = {
  en: { change: 'Change', changePct: 'Change (%)', changePp: 'Change (pp)', later: 'Later period minus earlier period', ratio: 'Change divided by the earlier period', rate: 'Later rate minus earlier rate',
    bridge: 'Starting value plus the seven reported items', sum: 'Sum of the reported items',
    partial: 'Only findings that passed the checks are shown. The chart is left out because some of its figures are not among them.', figure: 'Reported figure' },
  de: { change: 'Veränderung', changePct: 'Veränderung (%)', changePp: 'Veränderung (Pp.)', later: 'Späterer minus früherer Zeitraum', ratio: 'Veränderung geteilt durch den früheren Zeitraum', rate: 'Späterer minus früherer Satz',
    bridge: 'Ausgangswert plus die sieben berichteten Posten', sum: 'Summe der berichteten Posten',
    partial: 'Gezeigt werden nur Aussagen, die die Prüfung bestanden haben. Das Diagramm fehlt, weil einige seiner Kennzahlen nicht darunter sind.', figure: 'Berichtete Kennzahl' },
}

export const COMPANY_NAME: Record<string, string> = {
  henkel: 'Henkel', mercedes_benz_group: 'Mercedes-Benz Group', siemens: 'Siemens',
}

export class Labels {
  constructor(private readonly catalog: CatalogLabels | null | undefined, private readonly lang: Lang = 'en') {}
  metric(id?: string | null): string | undefined { return id ? (this.lang === 'de' ? METRIC_DE[id] : undefined) ?? this.catalog?.metrics[id]?.label : undefined }
  metricUnit(id?: string | null): string | undefined { return id ? this.catalog?.metrics[id]?.unit : undefined }
  scope(id?: string | null): string | undefined { return id ? this.catalog?.scopes[id]?.label : undefined }
  /** Grain-aware period label; claim periods carry no grain, so the non-YoY grain is used. */
  period(company?: string | null, periodId?: string | null, grain?: string | null): string | undefined {
    if (!company || !periodId || !this.catalog) return undefined
    const rows = this.catalog.periods.filter(item => item.company_id === company && item.period_id === periodId)
    const exact = grain ? rows.find(item => item.period_grain === grain) : undefined
    const label = (exact ?? rows.find(item => item.period_grain !== 'QUARTER_YOY') ?? rows[0])?.label
    return label ? periodLabel(label, this.lang) : undefined
  }
}

function supportFor(claim: Claim, citedIds: Set<string>): SupportKind[] {
  if (claim.provenance === 'LIMITATION') return ['limitation']
  const kinds: SupportKind[] = []
  if (claim.fact_ids.length) kinds.push('fact')
  if (claim.calculation_run_ids.length) kinds.push('calculation')
  if (claim.evidence_ids.some(id => citedIds.has(id))) kinds.push('document')
  if (claim.provenance === 'MANAGEMENT_ATTRIBUTED') kinds.push('management')
  if (claim.provenance === 'INTERPRETATION') kinds.push('interpretation')
  return kinds
}

const bar = (fact: AnalyticsFact, labels: Labels): BarView => ({
  key: `f${fact.fact_id}`, factId: fact.fact_id, label: labels.metric(fact.metric_id) ?? fact.label,
  value: fact.value, unit: fact.unit, order: fact.component_order ?? 0, provenance: fact.provenance,
})

const role = (analytics: Analytics, name: string) => analytics.supporting.find(item => item.bridge_role === name)

function kpi(fact: AnalyticsFact, labels: Labels, kind: KpiView['role']): KpiView {
  return {
    key: `k${fact.fact_id}`, factId: fact.fact_id, role: kind, signed: false,
    label: labels.metric(fact.metric_id) ?? fact.label,
    period: labels.period(fact.company_id, fact.period, fact.period_grain) ?? fact.period,
    value: fact.value, unit: fact.unit,
    support: fact.provenance === 'MANAGEMENT_ATTRIBUTED' ? 'management' : 'fact',
  }
}

function buildKpis(analytics: Analytics | null | undefined, claims: Claim[], labels: Labels, lang: Lang): KpiView[] {
  const c = CALC_TEXT[lang]
  if (analytics) {
    const out: KpiView[] = [kpi(analytics.primary, labels, 'primary')]
    const start = role(analytics, 'START')
    if (analytics.comparison) out.push(kpi(analytics.comparison, labels, 'secondary'))
    if (start) out.push(kpi(start, labels, 'secondary'))
    for (const change of analytics.changes) {
      out.push({
        key: `c${change.kind}`, role: 'secondary', signed: true, support: 'calculation', calcKey: change.calculation_run_id ?? undefined,
        label: change.kind === 'absolute' ? c.change : change.kind === 'percent' ? c.changePct : c.changePp,
        period: [analytics.comparison, analytics.primary].filter((f): f is AnalyticsFact => !!f)
          .map(fact => labels.period(fact.company_id, fact.period, fact.period_grain) ?? fact.period).join(' → '),
        value: change.value, unit: change.unit,
      })
    }
    // Small decompositions (e.g. price + volume) read best as figures, not a chart alone.
    if (!start && !analytics.comparison && analytics.components.length && analytics.components.length <= 3) {
      for (const component of analytics.components) out.push({ ...kpi(component, labels, 'secondary'), signed: true })
    }
    return out.slice(0, 4)
  }
  return claims
    .filter(claim => isGovernedDecimal(claim.value) && claim.unit)
    .slice(0, 3)
    .map((claim, index) => ({
      key: `q${claim.claim_id}`, role: index === 0 ? 'primary' : 'secondary', signed: false,
      label: labels.metric(claim.metric_id) ?? c.figure,
      period: claim.periods.map(p => labels.period(claim.company_id, p) ?? p).join(', '),
      value: claim.value!, unit: claim.unit!,
      support: claim.provenance === 'CALCULATED' ? 'calculation' : claim.provenance === 'MANAGEMENT_ATTRIBUTED' ? 'management' : 'fact',
      factId: claim.fact_ids[0],
    }))
}

function visualFactIds(visual: VisualView): number[] {
  switch (visual.kind) {
    case 'bridge': return [visual.start.factId, ...visual.components.map(c => c.factId), visual.end.factId]
    case 'decomposition': return [visual.total.factId, ...visual.components.map(c => c.factId)]
    case 'ranking': return visual.bars.map(b => b.factId)
    case 'comparison': return visual.bars.map(b => b.factId)
  }
}

function buildVisual(analytics: Analytics | null | undefined, labels: Labels): VisualView | null {
  if (!analytics) return null
  const components = [...analytics.components].sort((a, b) => (a.component_order ?? 0) - (b.component_order ?? 0))
  const start = role(analytics, 'START')
  const end = role(analytics, 'ADJUSTED_ENDPOINT')
  const units = new Set(components.map(item => item.unit))
  const periodLabel = components[0] ? labels.period(components[0].company_id, components[0].period, components[0].period_grain) ?? '' : ''

  if (analytics.operation === 'RANKING' && analytics.ranked.length) {
    return {
      kind: 'ranking', unit: analytics.ranked[0].unit, periodLabel,
      bars: analytics.ranked.map(item => ({
        key: `f${item.fact_id}`, factId: item.fact_id, label: labels.metric(item.metric_id) ?? item.label,
        value: item.value, unit: item.unit, order: item.rank, provenance: item.provenance, rank: item.rank,
      })),
    }
  }
  if (start && end && components.length && units.size === 1 && units.has(start.unit)) {
    // A waterfall is drawn only when the backend's own bridge reconciliation passed.
    const reconciled = analytics.reconciliations.some(item => item.passed && item.expected_value === end.value)
    if (reconciled) {
      return {
        kind: 'bridge', unit: start.unit, periodLabel, reconciled,
        start: bar(start, labels), end: bar(end, labels), components: components.map(item => bar(item, labels)),
        startLabel: labels.period(start.company_id, start.period, start.period_grain) ?? start.period,
        endLabel: labels.period(end.company_id, end.period, end.period_grain) ?? end.period,
      }
    }
  }
  if (components.length && units.size === 1) {
    return {
      kind: 'decomposition', unit: components[0].unit,
      periodLabel: labels.period(analytics.primary.company_id, analytics.primary.period, analytics.primary.period_grain) ?? analytics.primary.period,
      total: bar(analytics.primary, labels), components: components.map(item => bar(item, labels)),
      reconciliation: analytics.reconciliations[0] ?? null,
    }
  }
  if (analytics.operation === 'PERIOD_COMPARISON' && analytics.comparison && analytics.comparison.unit === analytics.primary.unit) {
    const make = (fact: AnalyticsFact) => ({ ...bar(fact, labels), label: labels.period(fact.company_id, fact.period, fact.period_grain) ?? fact.period })
    return {
      kind: 'comparison', unit: analytics.primary.unit, metricLabel: labels.metric(analytics.primary.metric_id) ?? analytics.primary.label,
      bars: [make(analytics.comparison), make(analytics.primary)],
      change: analytics.changes.find(item => item.unit === analytics.primary.unit) ?? analytics.changes[0] ?? null,
    }
  }
  return null
}

function composition(response: QueryResponse, answered: boolean): Composition {
  if (!answered) return 'none'
  switch (response.analytics?.operation) {
    case 'RETRIEVE': return 'fact'
    case 'PERIOD_COMPARISON': return 'comparison'
    case 'DECOMPOSITION': case 'RANKING': case 'RECONCILIATION': return 'decomposition'
  }
  if (response.route === 'KNOWLEDGE_ONLY' || response.citations.length) return 'document'
  return 'findings'
}

function routeLabel(response: QueryResponse, kind: Composition, lang: Lang): string {
  const r = strings(lang).route
  const operation = response.analytics?.operation
  const base = operation === 'RANKING' ? r.ranked : operation === 'RECONCILIATION' ? r.reconciliation
    : kind === 'decomposition' ? r.driver : kind === 'comparison' ? r.comparison
    : kind === 'fact' ? r.fact : kind === 'document' ? r.document
    : response.status === 'NEEDS_CLARIFICATION' ? r.clarification : response.route === 'UNSUPPORTED' ? r.unsupported : r.answer
  return kind !== 'document' && kind !== 'none' && response.citations.length ? `${base} · ${r.withReporting}` : base
}

function buildContext(response: QueryResponse, labels: Labels, kind: Composition, lang: Lang): ContextView {
  const analytics = response.analytics
  const first = analytics?.primary
  const claim = response.claims.find(item => item.company_id)
  const company = first?.company_id ?? claim?.company_id ?? undefined
  const scopeId = first?.business_scope ?? claim?.business_scope ?? undefined
  const metricId = first?.metric_id ?? claim?.metric_id ?? undefined
  const bridgeFact = analytics?.components[0]
  const period = bridgeFact && kind === 'decomposition'
    ? labels.period(bridgeFact.company_id, bridgeFact.period, bridgeFact.period_grain)
    : first ? labels.period(first.company_id, first.period, first.period_grain) : claim ? labels.period(claim.company_id, claim.periods[0]) : undefined
  const unit = first?.unit ?? labels.metricUnit(metricId)
  if (kind === 'document') {
    // Passage metadata (periods, scopes) describes the source, not the question: show only
    // what the answer is about.
    return { company: company ? COMPANY_NAME[company] ?? company : undefined, metric: labels.metric(metricId), route: routeLabel(response, kind, lang) }
  }
  return {
    company: company ? COMPANY_NAME[company] ?? company : undefined,
    scope: labels.scope(scopeId),
    metric: labels.metric(metricId),
    period,
    unit: unit ? unitName(unit) : undefined,
    route: routeLabel(response, kind, lang),
  }
}

function buildFacts(analytics: Analytics | null | undefined, labels: Labels): Record<number, FactView> {
  if (!analytics) return {}
  const all = [analytics.primary, analytics.comparison, ...analytics.components, ...analytics.supporting].filter((f): f is AnalyticsFact => !!f)
  return Object.fromEntries(all.map(fact => [fact.fact_id, {
    factId: fact.fact_id, label: labels.metric(fact.metric_id) ?? fact.label, value: fact.value, unit: fact.unit,
    period: labels.period(fact.company_id, fact.period, fact.period_grain) ?? fact.period, provenance: fact.provenance,
    scope: labels.scope(fact.business_scope),
  }]))
}

function buildCalculations(analytics: Analytics | null | undefined, visual: VisualView | null, lang: Lang): CalculationView[] {
  if (!analytics) return []
  const c = CALC_TEXT[lang]
  const CHANGE_TITLE = { absolute: c.change, percent: c.changePct, percentage_point: c.changePp }
  const endpoints = [analytics.comparison, analytics.primary].filter((f): f is AnalyticsFact => !!f).map(f => f.fact_id)
  const changes: CalculationView[] = analytics.changes.filter(change => change.calculation_run_id).map(change => ({
    key: change.calculation_run_id!, runId: change.calculation_run_id!, title: CHANGE_TITLE[change.kind],
    expression: change.kind === 'absolute' ? c.later : change.kind === 'percent' ? c.ratio : c.rate,
    calculated: change.value, unit: change.unit, inputs: endpoints,
  }))
  // Only reconciliations that belong to the displayed analysis. The Mercedes adjusted-to-
  // reported EBIT reconciliation is a separate question and is not mixed into the bridge.
  const checks: CalculationView[] = analytics.reconciliations
    .filter(item => CALCULATION_TITLE.en[item.rule_id])
    .filter(item => visual?.kind !== 'bridge' || item.rule_id === 'MERCEDES_EBIT_BRIDGE_V1')
    .map(item => ({
      key: item.calculation_run_id, runId: item.calculation_run_id, title: CALCULATION_TITLE[lang][item.rule_id], passed: item.passed,
      expression: item.rule_id === 'MERCEDES_EBIT_BRIDGE_V1' ? c.bridge : c.sum,
      expected: item.expected_value, calculated: item.calculated_value, tolerance: item.tolerance,
      unit: analytics.primary.unit, inputs: item.source_fact_ids,
    }))
  return [...changes, ...checks]
}

export function buildResultView(
  response: QueryResponse,
  catalog: CatalogLabels | null | undefined,
  question: string,
  kind: ResultView['kind'] = 'live',
  interpretedAs: string | null = null,
  lang: Lang = 'en',
): ResultView {
  const labels = new Labels(catalog, lang)
  const t = strings(lang)
  const verification = deriveVerification(response, lang)
  const answered = verification.outcome === 'answer'
  const partial = verification.state === 'subset'
  const layout = composition(response, answered)

  // Cited passages are numbered; retrieved-but-uncited passages are context, never counted as citations.
  const withClaims = response.citations.map(citation => ({
    ...citation, index: 0,
    claimIds: response.claims.filter(claim => claim.evidence_ids.includes(citation.evidence_unit_id)).map(claim => claim.claim_id),
  }))
  const citations: CitationView[] = withClaims.filter(c => c.claimIds.length).map((c, i) => ({ ...c, index: i + 1 }))
  const context: CitationView[] = withClaims.filter(c => !c.claimIds.length)
  const citationIndex = new Map(citations.map(item => [item.evidence_unit_id, item.index]))
  const citationIds = new Set(citations.map(item => item.evidence_unit_id))
  const findings: FindingView[] = response.claims
    .filter(claim => claim.provenance !== 'LIMITATION')
    .map((claim, index) => ({
      id: claim.claim_id, index: index + 1, text: claim.text, provenance: claim.provenance,
      support: supportFor(claim, citationIds),
      citationIndexes: claim.evidence_ids.map(id => citationIndex.get(id)).filter((i): i is number => i !== undefined),
      factIds: claim.fact_ids, value: claim.value, unit: claim.unit,
      company: claim.company_id ? COMPANY_NAME[claim.company_id] ?? claim.company_id : undefined,
      scope: labels.scope(claim.business_scope), metric: labels.metric(claim.metric_id),
      periods: claim.periods.map(p => labels.period(claim.company_id, p) ?? p),
    }))

  // A supported subset shows only what was released: numbers and charts are limited to
  // figures that released findings actually reference. No fixture data fills the gaps.
  const releasedFacts = new Set(response.claims.flatMap(claim => claim.fact_ids))
  const releasedRuns = new Set(response.claims.flatMap(claim => claim.calculation_run_ids))
  let kpis = answered ? buildKpis(response.analytics, response.claims, labels, lang) : []
  let visual = answered ? buildVisual(response.analytics, labels) : null
  let partialNote: string | null = null
  if (partial) {
    kpis = kpis.filter(item => item.factId !== undefined ? releasedFacts.has(item.factId)
      : response.analytics?.changes.some(change => change.calculation_run_id && releasedRuns.has(change.calculation_run_id) && `c${change.kind}` === item.key))
    if (visual && !visualFactIds(visual).every(id => releasedFacts.has(id))) {
      visual = null
      partialNote = CALC_TEXT[lang].partial
    }
  }

  const limitationCodes = [...response.limitations, ...(response.analytics?.limitations ?? []), ...(response.analytics?.warnings ?? [])]
  const limitations = [...new Set(limitationCodes)]
    .map(code => ({ key: code, text: t.limitation[code] ?? code.replaceAll('_', ' ').toLowerCase().replace(/^./, c => c.toUpperCase()) }))
    .concat(response.claims.filter(claim => claim.provenance === 'LIMITATION').map(claim => ({ key: claim.claim_id, text: claim.text })))
    .filter((item, index, all) => all.findIndex(other => other.text === item.text) === index)

  // For a supported subset the backend's answer is the joined claim texts; a separate
  // summary would duplicate the findings.
  const summary = answered && !partial && response.answer.trim() ? response.answer : null
  const message = verification.outcome === 'clarification'
    ? response.clarification_question ?? response.answer
    : answered ? null : response.refusal_reason && !response.refusal_reason.startsWith('WORKFLOW_FAILURE') && response.refusal_reason !== response.answer
      ? response.refusal_reason : response.answer

  const runtime: ResultView['kind'] = kind === 'sample' ? 'sample' : response.provider === 'deterministic_fake' ? 'test' : 'live'
  const family = familyOf(response, verification, visual, citations)
  const hybrid = answered && (response.analytics !== null && response.analytics !== undefined) && citations.length > 0
  const lead = answered ? { ...buildLead(family, visual, response.analytics, labels, lang, findings.length), located: family === 'document' && runtime === 'test' && findings.length > 0 && findings.every(f => /section covers this metric/.test(f.text)) } : EMPTY_LEAD
  const contextView = buildContext(response, labels, layout, lang)
  const calculations = answered ? buildCalculations(response.analytics, visual, lang) : []
  const facts = answered ? buildFacts(response.analytics, labels) : {}
  return {
    workflow: buildWorkflow({
      response, verification, kind: runtime, lang, context: contextView, figures: Object.keys(facts).length, calculations,
      citations: answered ? citations : [], alsoRead: answered ? context.length : 0, findings: answered ? findings.length : 0,
      supportKinds: answered ? [...new Set(findings.flatMap(f => f.support))].map(k => t.support[k][0]) : [],
    }),
    interpretation: answered ? buildInterpretation({ family, lead, visual, codes: [...new Set(limitationCodes)], limitations, citations: citations.length, verification, lang }) : [],
    kind: runtime,
    kindLabel: t.kind[runtime],
    kindNote: runtime === 'sample' ? t.kind.sampleNote : runtime === 'test' ? t.kind.testNote : t.kind.liveNote,
    lang, family, hybrid,
    lead,
    plain: plainOutcome(response, lang),
    question, interpretedAs: interpretedAs && interpretedAs.trim() !== question.trim() ? interpretedAs : null,
    sessionId: response.session_id,
    composition: layout,
    documentary: answered && layout !== 'document' && (citations.length > 0 || context.length > 0),
    context: contextView,
    summary, message,
    options: response.clarification_options ?? [],
    alternatives: response.alternatives ?? [],
    kpis, visual, partialNote,
    findings: answered ? findings : [],
    limitations: answered ? limitations : [],
    citations: answered ? citations : [],
    contextPassages: answered ? context : [],
    sourceCount: answered ? new Set(citations.map(c => c.source_id)).size : 0,
    factSources: Object.fromEntries((response.fact_sources ?? []).map(item => [item.fact_id, item])),
    facts, calculations,
    verification,
    trace: runtime !== 'sample' ? response.execution.stages : null,
    execution: runtime !== 'sample' ? buildExecution(response, verification) : null,
  }
}

function familyOf(response: QueryResponse, verification: VerificationView, visual: VisualView | null, citations: CitationView[]): Family {
  if (verification.outcome === 'clarification') return 'clarification'
  if (verification.outcome === 'refusal') return 'unsupported'
  if (verification.outcome !== 'answer') return 'failure'
  switch (response.analytics?.operation) {
    case 'RETRIEVE': return 'fact'
    case 'PERIOD_COMPARISON': return 'comparison'
    case 'RANKING': return 'ranking'
    case 'DECOMPOSITION': case 'RECONCILIATION': return visual?.kind === 'bridge' ? 'driver' : 'breakdown'
  }
  if (citations.some(c => c.evidence_type === 'METRIC_DEFINITION')) return 'definition'
  return citations.length ? 'document' : 'findings'
}

const lowerFirst = (text: string, lang: Lang) => (lang === 'en' && !/^[A-Z]{2}/.test(text) ? text.charAt(0).toLowerCase() + text.slice(1) : text)

function listJoin(items: string[], lang: Lang): string {
  if (items.length < 2) return items.join('')
  return `${items.slice(0, -1).join(', ')} ${strings(lang).answer.and} ${items[items.length - 1]}`
}

/**
 * The plain-language lead: which measure moved from what to what, and which reported
 * items were largest. Only selects and formats governed values; it never calculates new
 * figures and never states causes.
 */
const EMPTY_LEAD: Lead = { changed: null, contributed: null, attribution: false, answerFindings: false, rows: [], delta: null, periods: [], located: false }

function buildLead(family: Family, visual: VisualView | null, analytics: Analytics | null | undefined, labels: Labels, lang: Lang, findings: number): Lead {
  const t = strings(lang)
  const a = t.answer
  const none = EMPTY_LEAD
  void labels
  if (family === 'definition' || family === 'document') return { ...none, answerFindings: findings > 0 }
  if (!visual || !analytics) return none
  if (visual.kind === 'bridge') {
    const signed = (v: string) => formatValue(v, visual.unit, true)
    const byValue = [...visual.components].sort((x, y) => magnitude(x.value) - magnitude(y.value))
    const neg = byValue[0] && magnitude(byValue[0].value) < 0 ? byValue[0] : null
    const pos = byValue.at(-1) && magnitude(byValue.at(-1)!.value) > 0 ? byValue.at(-1)! : null
    // Direction is a comparison of two reported values; no new figure is calculated.
    const start = magnitude(visual.start.value), end = magnitude(visual.end.value)
    const dir = end < start ? -1 : end > start ? 1 : 0
    return {
      ...none,
      changed: t.x.moved(visual.start.label, formatValue(visual.start.value, visual.unit), formatValue(visual.end.value, visual.unit), dir),
      contributed: neg && pos ? a.bridgeContributed(lowerFirst(neg.label, lang), signed(neg.value), lowerFirst(pos.label, lang), signed(pos.value)) : null,
      rows: [neg, pos].filter((x): x is BarView => !!x).map(x => ({ label: x.label, value: signed(x.value), factId: x.factId })),
      attribution: visual.components.some(c => c.provenance === 'MANAGEMENT_ATTRIBUTED'),
    }
  }
  if (visual.kind === 'comparison' && visual.bars.length === 2) {
    const absolute = analytics.changes.find(c => c.kind === 'absolute' || c.kind === 'percentage_point')
    const percent = analytics.changes.find(c => c.kind === 'percent')
    if (!absolute) return none
    return {
      ...none,
      delta: { abs: formatValue(absolute.value, absolute.unit, true), pct: percent ? formatValue(percent.value, percent.unit, true) : null, calcKey: absolute.calculation_run_id ?? undefined },
      periods: visual.bars.map(b => ({ label: b.label, value: formatValue(b.value, b.unit), factId: b.factId })),
    }
  }
  if (visual.kind === 'decomposition') {
    return {
      ...none,
      changed: a.breakdownChanged(visual.total.label, formatValue(visual.total.value, visual.unit), visual.periodLabel),
      rows: visual.components.map(c => ({ label: c.label, value: formatValue(c.value, c.unit, true), factId: c.factId })),
      attribution: visual.components.some(c => c.provenance === 'MANAGEMENT_ATTRIBUTED'),
    }
  }
  return none
}
