import { describe, expect, it } from 'vitest'
import { validateQueryResponse } from './validateResponse'

const valid = () => ({
  request_id: 'r', session_id: 's', status: 'COMPLETED', route: 'ANALYTICS_ONLY', answer: 'Value 1', provider: 'fake', model: 'fake', latency_ms: 1,
  claims: [{ claim_id: 'c', provenance: 'REPORTED', text: 'Value 1', periods: [], fact_ids: [1], calculation_run_ids: [], evidence_ids: [], value: '1', unit: 'EUR_million' }],
  citations: [], limitations: [], provenance_summary: [{ provenance: 'REPORTED', count: 1 }],
  verification: { verdict: 'PASS', label: 'Verified', supported_claims: 1, total_claims: 1, errors: [] as string[] },
  execution: { analytics_used: true, retrieval_used: false, revision_used: false, provider_calls: 1, verifier_interventions: 0, input_tokens: 1, output_tokens: 1, cost_usd: '0', stages: [] },
})
describe('release response boundary', () => {
  it('accepts a fully verified response', () => expect(validateQueryResponse(valid()).status).toBe('COMPLETED'))
  it.each([
    { verification: undefined }, { verification: null }, { verification: {} },
    { verification: { ...valid().verification, verdict: 'UNKNOWN' } },
    { verification: { ...valid().verification, verdict: 'REFUSE' } },
    { verification: { ...valid().verification, supported_claims: 2 } },
    { verification: { ...valid().verification, total_claims: 2 } },
    { verification: { ...valid().verification, errors: ['CONTRADICTION'] } },
    { claims: null }, { citations: [{}] }, { execution: {} }, { latency_ms: NaN },
    { provenance_summary: [{ provenance: 'REPORTED', count: 2 }] },
    { status: 'SOMETHING_NEW' },
    { claims: [{ ...valid().claims[0], unit: 'UNSUPPORTED_UNIT' }] },
    { claims: [valid().claims[0], valid().claims[0]] },
  ])('rejects malformed or inconsistent successful payload %j', patch => expect(() => validateQueryResponse({ ...valid(), ...patch })).toThrow())
  it('rejects malformed JSON values', () => { for (const v of [null, [], 'success', 1]) expect(() => validateQueryResponse(v)).toThrow() })
  it('accepts an explicitly verified partial release', () => {
    const v = valid(); v.verification = { verdict: 'NEEDS_REVISION', label: 'Supported subset returned', supported_claims: 1, total_claims: 2, errors: ['UNSUPPORTED_CLAIM'] }
    expect(validateQueryResponse(v).verification?.verdict).toBe('NEEDS_REVISION')
  })
})
