import { describe, expect, it } from 'vitest'
import { SAMPLE_LABELS, SAMPLE_QUESTION, SAMPLE_RESPONSE } from '../lib/sample'
import { buildResultView } from '../lib/viewModel'
import type { QueryResponse } from '../types'
import { explain } from '../lib/explain'
import { barSpecsFor, durationFor, labelDetails, planFor, stageFor, subjectFor } from './Landing'

const sample = () => structuredClone(SAMPLE_RESPONSE) as QueryResponse
const view = (r: QueryResponse = sample(), kind: 'sample' | 'live' = 'live') => buildResultView(r, SAMPLE_LABELS, SAMPLE_QUESTION, kind)

describe('the instrument depicts only what the answer contains', () => {
  it('lays out the authoritative Mercedes bridge in published order, combined component intact', () => {
    const bars = barSpecsFor(view(sample(), 'sample'))
    expect(bars.map(b => b.to - b.from)).toEqual([1228, -602, 17, 482, -194, -28, 143, -137, 909])
    expect(bars.every(b => b.land === 'stand')).toBe(true)
    const visual = view(sample(), 'sample').visual
    expect(visual?.kind === 'bridge' && visual.components[0].label).toBe('Volume / structure / net pricing')
  })

  it('never gives a non-bridge answer the waterfall', () => {
    const fact = sample()
    fact.analytics = { ...fact.analytics!, operation: 'RETRIEVE', components: [], supporting: [], reconciliations: [], changes: [] }
    const v = view(fact)
    expect(v.family).toBe('fact')
    const bars = barSpecsFor(v)
    expect(bars).toHaveLength(1)
    expect(bars[0].land).toBe('underline')

    const definition = sample()
    definition.analytics = null
    definition.citations = definition.citations.map(c => ({ ...c, evidence_type: 'METRIC_DEFINITION' }))
    const d = view(definition)
    expect(d.family).toBe('definition')
    expect(barSpecsFor(d)).toEqual([])
    expect(subjectFor(d, false).analytics).toBe(false)
  })

  it('shows one illustrative failing draft only for the labelled sample', () => {
    expect(subjectFor(view(sample(), 'sample'), true).failed).toBe(1)
    expect(subjectFor(view(), false).failed).toBe(0)
  })

  it('shows the failures a returned check actually reported', () => {
    const r = sample()
    r.claims = r.claims.slice(0, 4)
    r.verification = { ...r.verification!, verdict: 'NEEDS_REVISION', supported_claims: 4, total_claims: 6 }
    expect(subjectFor(view(r), false).failed).toBe(2)
  })

  it('leaves the reporting channel inactive when retrieval did not run', () => {
    const r = sample()
    r.execution = { ...r.execution, retrieval_used: false }
    r.citations = []
    const subject = subjectFor(view(r), false)
    expect(subject.evidence).toBe(false)
  })

  it('gives every outcome its own truthful presentation', () => {
    const clar = { ...sample(), status: 'NEEDS_CLARIFICATION' as const, clarification_question: "For Mercedes-Benz, does 'sales' mean revenue or vehicle unit sales?", claims: [] }
    expect(planFor(view(clar))).toBe('clarify')
    const refused = { ...sample(), status: 'REFUSED' as const, refusal_reason: 'Mercedes-Benz does not disclose a separate governed price contribution here.', claims: [] }
    expect(planFor(view(refused))).toBe('boundary')
    expect(planFor(view())).toBe('full')
    expect(planFor(null)).toBe('failure')
    // A clarification or a limit is depicted with nothing analysed: no figures, no sources, no passed findings.
    for (const r of [clar, refused]) {
      const subject = subjectFor(view({ ...r, analytics: null, citations: [], verification: null, execution: { ...r.execution, analytics_used: false, retrieval_used: false, stages: [] } }), false)
      expect([subject.bars.length, subject.analytics, subject.evidence, subject.supported, subject.cited]).toEqual([0, false, false, 0, 0])
    }
  })

  it('explains input, operation and output from the response, and claims nothing while pending', () => {
    const driver = explain(view(sample(), 'sample'), 'en')
    expect(driver.input).toEqual(['Mercedes-Benz Cars', 'Adjusted EBIT', 'Q2 2026 vs Q2 2025', 'Driver analysis'])
    expect(driver.operation).toBe('Reported figures + Reporting evidence + Supported synthesis + Checks')
    expect(driver.output).toMatch(/limitations/)
    expect(driver.title).toBe('How an answer is built')
    expect(explain(view(), 'en').title).toBe('How this answer was produced')
    const pending = explain(null, 'en')
    expect(pending.title).toBe('Preparing your analysis')
    expect(JSON.stringify(pending)).not.toMatch(/calculat|retriev|verif|checked|complete/i)
    const clar = { ...sample(), status: 'NEEDS_CLARIFICATION' as const, clarification_question: 'Which company?', claims: [], analytics: null }
    expect(explain(view(clar), 'en').operation).toBe('One detail is missing, so no analysis was run.')
    expect(explain(null, 'en', true).operation).toMatch(/could not be completed/)
  })

  it('words each stage from what the response contains, in step with the object', () => {
    const driver = view(sample(), 'sample'), subject = subjectFor(driver, true)
    expect((['ask', 'analytics', 'evidence', 'converge', 'verify', 'answer'] as const).map(b => stageFor(b, subject, driver, false))).toEqual(['question', 'figures', 'evidence', 'analysis', 'checks', 'answer'])
    expect(stageFor('verify', subject, driver, true)).toBe('pending')
    // A definition never shows a figures stage; a stop names itself instead of walking the stages.
    const definition = sample(); definition.analytics = null; definition.citations = definition.citations.map(c => ({ ...c, evidence_type: 'METRIC_DEFINITION' }))
    const d = view(definition), ds = subjectFor(d, false)
    expect((['analytics', 'evidence', 'converge'] as const).map(b => stageFor(b, ds, d, false))).toEqual(['question', 'evidence', 'evidence'])
    const clar = view({ ...sample(), status: 'NEEDS_CLARIFICATION', clarification_question: 'Which company?', claims: [], analytics: null })
    expect(stageFor('analytics', subjectFor(clar, false), clar, false)).toBe('clarify')
    // The figures label carries the bridge exactly as reported, combined component intact.
    expect(labelDetails(driver).figures).toBe('1,228 · −602 · +17 · +482 · −194 · −28 · +143 · −137 · 909')
  })

  it('plays one phrase per question type, shortest for a follow-up, with no reading holds', () => {
    expect(durationFor(view(), false)).toBe(6.2)
    const fact = sample()
    fact.analytics = { ...fact.analytics!, operation: 'RETRIEVE', components: [], supporting: [], reconciliations: [], changes: [] }
    expect(durationFor(view(fact), false)).toBe(4.2)
    expect(durationFor(view(), true)).toBe(3.1)
  })
})
