import { describe, expect, it } from 'vitest'
import { SAMPLE_RESPONSE } from './sample'
import { plainOutcome } from './plain'
import type { QueryResponse } from '../types'

const clarify = (question: string, options: QueryResponse['clarification_options'] = []) =>
  plainOutcome({ ...structuredClone(SAMPLE_RESPONSE), status: 'NEEDS_CLARIFICATION', claims: [], clarification_question: question, clarification_options: options } as QueryResponse, 'en')!
const refuse = (reason: string) =>
  plainOutcome({ ...structuredClone(SAMPLE_RESPONSE), status: 'REFUSED', claims: [], refusal_reason: reason } as QueryResponse, 'en')!

describe('plain-language clarification and limits', () => {
  it('never shows the system wording for a missing figure, and offers validated starting points', () => {
    const p = clarify('Which governed metric should be used?')
    expect(p.title).toBe('Which figure do you want to investigate?')
    expect(p.alternatives.length).toBe(3)
    expect(`${p.title} ${p.line}`).not.toMatch(/governed|metric/i)
    expect(p.original).toBe('Which governed metric should be used?')
  })

  it('asks for the company, the period or the comparison in everyday words', () => {
    const companies = [{ label: 'Henkel', detail: 'Company', question: 'x' }]
    expect(clarify('Should this question use Henkel or Mercedes-Benz Group?', companies).title).toBe('Which company should we use?')
    expect(clarify('Should the plan use Q2 2026, H1 2026, Q2 2025, or H1 2025?').title).toBe('Which period do you mean?')
    expect(clarify('Which other governed company should be compared?').title).toBe('Which company do you want to compare with?')
    expect(clarify("For Mercedes-Benz, does 'sales' mean revenue or vehicle unit sales?").title).toBe('What do you mean by “sales”?')
  })

  it('explains limits without system vocabulary', () => {
    expect(refuse('Predictive forecasts and projections are outside the governed reported-information scope.').title).toBe('Forecasts aren’t part of the reported data')
    expect(refuse('The requested metric is not present in the governed metric catalog.').title).toBe('That figure isn’t in the demo data')
    expect(refuse('The requested company is outside the governed Henkel and Mercedes-Benz scope.').title).toBe('That isn’t covered by the demo data')
    expect(refuse('Period FY2026 is not available in the governed Q2/H1 2025-2026 planning scope.').title).toBe('That period isn’t in the demo data')
  })

  it('has a German version of every message', () => {
    const p = plainOutcome({ ...structuredClone(SAMPLE_RESPONSE), status: 'NEEDS_CLARIFICATION', claims: [], clarification_question: 'Which governed metric should be used?' } as QueryResponse, 'de')!
    expect(p.title).toBe('Welche Kennzahl möchten Sie untersuchen?')
  })
})
