import { describe, expect, it } from 'vitest'
import { formatValue, valueParts } from './format'
import { SAMPLE_LABELS, SAMPLE_QUESTION, SAMPLE_RESPONSE } from './sample'
import { deriveVerification } from './verification'
import { buildResultView } from './viewModel'
import type { QueryResponse } from '../types'

const sample = () => structuredClone(SAMPLE_RESPONSE) as QueryResponse
const view = (response: QueryResponse = sample()) => buildResultView(response, SAMPLE_LABELS, SAMPLE_QUESTION, 'live')

describe('governed value formatting', () => {
  it('only groups digits and swaps in a true minus; digits are never altered', () => {
    expect(valueParts('-602', 'EUR_million', true)).toEqual({ sign: '−', digits: '602', unit: 'm', prefix: '€' })
    expect(formatValue('1228', 'EUR_million')).toBe('€1,228m')
    expect(formatValue('482', 'EUR_million', true)).toBe('+€482m')
    expect(formatValue('4.5', 'percentage_point')).toBe('4.5 pp')
    expect(formatValue('-0.10', 'percent')).toBe('−0.10%')
    expect(formatValue('417765', 'vehicle')).toBe('417,765 units')
  })
})

describe('verification state model', () => {
  const withStatus = (patch: Partial<QueryResponse>) => deriveVerification({ ...sample(), ...patch })

  it('follows the fixed status priority', () => {
    expect(withStatus({ status: 'NEEDS_CLARIFICATION' }).state).toBe('clarification')
    expect(withStatus({ status: 'REFUSED', refusal_reason: 'WORKFLOW_FAILURE:AuthenticationError' }).state).toBe('system_failure')
    expect(withStatus({ status: 'REFUSED', refusal_reason: 'The request is outside governed scope.' }).state).toBe('refused')
    expect(withStatus({ status: 'EVIDENCE_CONFLICT' }).state).toBe('evidence_conflict')
    expect(withStatus({}).state).toBe('verified')
    expect(withStatus({}).title).toBe('5 checked findings')
    expect(withStatus({ claims: sample().claims.slice(0, 4), verification: { verdict: 'NEEDS_REVISION', label: 'Supported subset returned', supported_claims: 4, total_claims: 6, errors: ['CAUSAL_OVERSTATEMENT'] } }).state).toBe('subset')
    expect(withStatus({ verification: { verdict: 'NEEDS_REVISION', label: 'Verified with limitations', supported_claims: 5, total_claims: 5, errors: ['HENKEL_ROUNDING_CAVEAT_OMITTED'] } }).state).toBe('verified_with_limitations')
  })

  it('reads status before the verifier label, so a refusal is never shown as verified', () => {
    const refused = withStatus({ status: 'REFUSED', refusal_reason: 'x', verification: { verdict: 'PASS', label: 'Verified', supported_claims: 1, total_claims: 1, errors: [] } })
    expect(refused.state).toBe('refused')
    expect(refused.outcome).toBe('refusal')
  })

  it('counts removed claims without inventing their text and translates error codes', () => {
    const subset = withStatus({ verification: { verdict: 'NEEDS_REVISION', label: 'Supported subset returned', supported_claims: 4, total_claims: 6, errors: ['CAUSAL_OVERSTATEMENT', 'NEW_CODE'] } })
    expect(subset.removed).toBe(2)
    expect(subset.issues).toEqual(['A claim used causal wording for a management-attributed figure.', 'NEW_CODE'])
  })
})

describe('result view model', () => {
  it('draws a bridge only from the governed analytics payload, in governed order', () => {
    const v = view()
    expect(v.visual?.kind).toBe('bridge')
    if (v.visual?.kind !== 'bridge') return
    expect(v.visual.start.value).toBe('1228')
    expect(v.visual.end.value).toBe('909')
    expect(v.visual.components.map(c => c.value)).toEqual(['-602', '17', '482', '-194', '-28', '143', '-137'])
    expect(v.visual.components[0].label).toBe('Volume / structure / net pricing')
    expect(v.visual.startLabel).toBe('Q2 2025')
    expect(v.visual.periodLabel).toBe('Q2 2026 vs Q2 2025')
  })

  it('never draws a chart from claims alone', () => {
    const noAnalytics = { ...sample(), analytics: null }
    const v = view(noAnalytics)
    expect(v.visual).toBeNull()
  })

  it('does not draw a waterfall when the governed reconciliation is missing or failed', () => {
    const response = sample()
    response.analytics!.reconciliations = response.analytics!.reconciliations.map(r => ({ ...r, passed: false }))
    expect(view(response).visual?.kind).not.toBe('bridge')
  })

  it('derives figures from governed facts with catalog labels, without mixing in the reported-EBIT reconciliation', () => {
    const v = view()
    expect(v.kpis.map(k => [k.label, k.period, k.value])).toEqual([['Adjusted EBIT', 'Q2 2026', '909'], ['Adjusted EBIT', 'Q2 2025', '1228']])
    expect(v.context).toMatchObject({ company: 'Mercedes-Benz Group', scope: 'Mercedes-Benz Cars', metric: 'Adjusted EBIT', period: 'Q2 2026 vs Q2 2025', unit: '€ million' })
    expect(v.calculations.map(c => c.title)).toEqual(['Bridge reconciliation'])
    expect(v.composition).toBe('decomposition')
  })

  it('withholds the chart for a supported subset whose figures were not all released', () => {
    const response = sample()
    response.claims = response.claims.filter(c => c.claim_id !== 'claim_003')
    response.verification = { verdict: 'NEEDS_REVISION', label: 'Supported subset returned', supported_claims: 4, total_claims: 5, errors: [] }
    const v = view(response)
    expect(v.visual).toBeNull()
    expect(v.partialNote).toMatch(/chart is left out/)
    expect(v.kpis.every(k => k.factId === undefined || response.claims.some(c => c.fact_ids.includes(k.factId!)))).toBe(true)
    expect(v.verification.title).toBe('4 of 5 findings passed the checks')
  })

  it('chooses a composition per question type', () => {
    const fact = { ...sample(), citations: [], analytics: { ...sample().analytics!, operation: 'RETRIEVE', components: [], supporting: [], reconciliations: [] } }
    expect(view(fact).composition).toBe('fact')
    expect(view({ ...sample(), analytics: null, route: 'KNOWLEDGE_ONLY' }).composition).toBe('document')
    expect(view({ ...sample(), status: 'NEEDS_CLARIFICATION' }).composition).toBe('none')
  })

  it('never shows internal enums in labels', () => {
    const v = view()
    const text = JSON.stringify([v.context, v.kpis.map(k => [k.label, k.period]), v.limitations.map(l => l.text), v.verification.title, v.verification.line])
    expect(text).not.toMatch(/MANAGEMENT_ATTRIBUTED|DECOMPOSITION_EXPLANATION|percentage_point|EUR_million|_NOT_/)
  })

  it('keeps claim text verbatim and distinguishes support mechanisms', () => {
    const v = view()
    const response = sample()
    expect(v.findings.map(f => f.text)).toEqual(response.claims.map(c => c.text))
    expect(v.findings[0].support).toEqual(['fact'])
    expect(v.findings[2].support).toEqual(['fact', 'management'])
    expect(v.findings[4].support).toEqual(['document'])
    expect(v.findings[4].citationIndexes).toEqual([1])
    // Fact-level evidence ids never borrow a retrieved citation.
    expect(v.findings[0].citationIndexes).toEqual([])
  })

  it('shows the prose answer only as a summary, and not at all for a supported subset', () => {
    expect(view().summary).toBe(SAMPLE_RESPONSE.answer)
    const subset = { ...sample(), verification: { verdict: 'NEEDS_REVISION', label: 'Supported subset returned', supported_claims: 4, total_claims: 5, errors: [] } }
    expect(view(subset).summary).toBeNull()
  })

  it('releases nothing numeric for withheld outcomes', () => {
    for (const status of ['REFUSED', 'NEEDS_CLARIFICATION', 'EVIDENCE_CONFLICT']) {
      const v = view({ ...sample(), status, claims: [], refusal_reason: 'x', clarification_question: 'Which company?' })
      expect(v.kpis).toEqual([])
      expect(v.visual).toBeNull()
      expect(v.findings).toEqual([])
    }
    expect(view({ ...sample(), status: 'NEEDS_CLARIFICATION', clarification_question: 'Which company?' }).message).toBe('Which company?')
  })

  it('translates known limitation codes and keeps unknown text verbatim', () => {
    const v = view({ ...sample(), limitations: ['COMBINED_COMPONENT_NOT_SPLIT', 'Figures are unaudited.'] })
    const texts = v.limitations.map(l => l.text)
    expect(texts).toContain('Price is not disclosed separately: volume, structure and net pricing are reported as one combined item.')
    expect(texts).toContain('Figures are unaudited.')
  })

  it('exposes recorded stages only for live responses', () => {
    expect(buildResultView(sample(), SAMPLE_LABELS, SAMPLE_QUESTION, 'sample').trace).toBeNull()
  })
})

describe('product truth (Step 8.9)', () => {
  it('fails closed when the verification payload is missing or inconsistent', () => {
    const missing = { ...sample(), verification: undefined } as unknown as QueryResponse
    expect(deriveVerification(missing).state).toBe('unverifiable')
    expect(deriveVerification(missing).outcome).toBe('failure')
    const overCount = sample(); overCount.verification = { ...overCount.verification!, supported_claims: 9, total_claims: 5 }
    expect(deriveVerification(overCount).state).toBe('unverifiable')
    const passButShort = sample(); passButShort.verification = { ...passButShort.verification!, verdict: 'PASS', supported_claims: 4, total_claims: 5 }
    expect(deriveVerification(passButShort).state).toBe('unverifiable')
    const noClaims = { ...sample(), claims: [] }
    expect(deriveVerification(noClaims).state).toBe('unverifiable')
    expect(view({ ...sample(), verification: undefined } as unknown as QueryResponse).findings).toHaveLength(0)
  })

  it('counts only cited passages as sources and keeps uncited passages as context', () => {
    const v = view()
    expect(v.citations.every(c => c.claimIds.length > 0)).toBe(true)
    expect(v.citations.map(c => c.index)).toEqual(v.citations.map((_, i) => i + 1))
    expect(v.citations.length + v.contextPassages.length).toBe(sample().citations.length)
    expect(v.sourceCount).toBe(new Set(v.citations.map(c => c.source_id)).size)
  })

  it('names the runtime honestly: recorded demo, test mode or live', () => {
    expect(buildResultView(sample(), SAMPLE_LABELS, SAMPLE_QUESTION, 'sample').kindLabel).toBe('Recorded demo')
    expect(view({ ...sample(), provider: 'deterministic_fake' }).kindLabel).toBe('Test mode')
    expect(view({ ...sample(), provider: 'openai' }).kindLabel).toBe('Live result')
  })

  it('rounds long calculated percentages for display only; reported precision is untouched', () => {
    expect(formatValue('-0.5190311418685121107266435986', 'percent')).toBe('−0.5%')
    expect(formatValue('-0.10', 'percent')).toBe('−0.10%')
    expect(formatValue('4.5', 'percentage_point')).toBe('4.5 pp')
  })

  it('exposes the bridge reconciliation as a calculation with its inputs', () => {
    const bridge = view().calculations.find(c => c.expression.startsWith('Starting value plus'))
    expect(bridge).toBeDefined()
    expect(bridge!.passed).toBe(true)
    expect(bridge!.inputs.length).toBeGreaterThan(2)
  })
})
