import { describe, expect, it } from 'vitest'
import { SAMPLE_LABELS, SAMPLE_RESPONSE } from './sample'
import { buildResultView } from './viewModel'
import { scenarioWorkflow } from './workflow'
import type { QueryResponse } from '../types'

const sample = () => structuredClone(SAMPLE_RESPONSE) as QueryResponse
const stage = (label: string, order: number) => ({ order, label, status: 'completed' as const, duration_ms: 1 })
const FULL = ['Question classified', 'Governed route selected', 'Evidence assembled', 'Structured draft generated', 'Independent verification completed'].map(stage)
const live = (patch: Partial<QueryResponse>, flags: { analytics: boolean; retrieval: boolean; revision?: boolean }, stages = FULL) => {
  const r = { ...sample(), provider: 'openai', ...patch }
  r.execution = { ...r.execution, analytics_used: flags.analytics, retrieval_used: flags.retrieval, revision_used: !!flags.revision, stages }
  return buildResultView(r, SAMPLE_LABELS, 'q', 'live', null, 'en')
}
const states = (v: ReturnType<typeof live>) => Object.entries(v.workflow.nodes).filter(([, s]) => s !== 'skipped').map(([id, s]) => `${id}:${s}`).join(' ')

describe('workflow route is read from the response, never invented', () => {
  it('shows the recorded demo as a recorded workflow with both branches and its one revision', () => {
    const v = buildResultView(sample(), SAMPLE_LABELS, 'q', 'sample', null, 'en')
    expect(v.workflow.source).toBe('recorded')
    expect(v.workflow.steps).toEqual([['router-analytics', 'router-evidence'], ['analytics-synthesis', 'evidence-synthesis'], ['synthesis-verifier'], ['verifier-answer']])
    expect(v.workflow.revised).toBe(true)
  })

  it('leaves out a branch that did not run', () => {
    const figure = live({}, { analytics: true, retrieval: false })
    expect(states(figure)).toBe('router:done analytics:done synthesis:done verifier:done answer:done')
    expect(figure.workflow.revised).toBe(false)
    const definition = live({ analytics: null }, { analytics: false, retrieval: true })
    expect(states(definition)).toBe('router:done evidence:done synthesis:done verifier:done answer:done')
    expect(definition.workflow.details.analytics).toBeUndefined()
  })

  it('ends at clarification or the limit before any analysis when the router short-circuits', () => {
    const early = [stage('Question classified', 1), stage('Governed route selected', 2)]
    const none = { claims: [], citations: [], analytics: null, fact_sources: [], verification: null }
    const clar = live({ ...none, status: 'NEEDS_CLARIFICATION', clarification_question: 'Which company?' }, { analytics: false, retrieval: false }, early)
    expect(states(clar)).toBe('router:done clarify:stopped')
    expect(clar.workflow.steps).toEqual([['router-clarify']])
    const refused = live({ ...none, status: 'REFUSED', refusal_reason: 'Mercedes-Benz does not disclose a separate governed price contribution here.' }, { analytics: false, retrieval: false }, early)
    expect(states(refused)).toBe('router:done limit:stopped')
    expect(refused.workflow.steps).toEqual([['router-limit']])
  })

  it('exposes only safe artifacts: inputs and results, no prompts or reasoning', () => {
    const v = live({}, { analytics: true, retrieval: true })
    const text = JSON.stringify(v.workflow.details)
    expect(text).toMatch(/Adjusted EBIT/)
    expect(text).not.toMatch(/prompt|reasoning|system message|chain of thought/i)
    expect(v.workflow.details.synthesis?.find(d => d.label === 'Written by')?.value).toBe('Language model')
  })

  it('keeps the illustrated routes distinct from each other', () => {
    const routes = (['fact', 'definition', 'driver', 'clarification', 'unsupported'] as const).map(id => JSON.stringify(scenarioWorkflow(id).steps))
    expect(new Set(routes).size).toBe(5)
    expect(scenarioWorkflow('driver').source).toBe('overview')
    expect(scenarioWorkflow(null).steps).toEqual([])
  })
})

describe('interpretation and limits come from response state', () => {
  it('builds the driver dimensions from reconciliation, sources and limitation codes', () => {
    const v = buildResultView(sample(), SAMPLE_LABELS, 'q', 'sample', null, 'en')
    expect(v.interpretation.map(i => i.kind)).toEqual(['numerical', 'explanation', 'documentary', 'limitation', 'cannot', 'attribution'])
    expect(v.interpretation[0].text).toBe('The disclosed bridge reconciles from €1,228m to €909m.')
    expect(JSON.stringify(v.interpretation)).not.toMatch(/%|confidence|risk/i)
  })

  it('omits the section when nothing needs qualifying, and never repeats a handled code', () => {
    const fact = sample()
    fact.analytics = { ...fact.analytics!, operation: 'RETRIEVE', components: [], supporting: [], reconciliations: [], changes: [], limitations: [], warnings: [] }
    fact.limitations = []; fact.citations = []
    expect(buildResultView(fact, SAMPLE_LABELS, 'q', 'live', null, 'en').interpretation).toEqual([])
    const extra = sample(); extra.limitations = [...extra.limitations, 'Figures are unaudited.']
    const texts = buildResultView(extra, SAMPLE_LABELS, 'q', 'sample', null, 'en').interpretation.map(i => i.text)
    expect(texts).toContain('Figures are unaudited.')
    expect(texts.filter(t => /reported together/.test(t))).toHaveLength(1)
  })
})
