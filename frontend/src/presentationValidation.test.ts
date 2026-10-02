import { describe, expect, it } from 'vitest'
import { SAMPLE_RESPONSE } from './lib/sample'
import { validateQueryResponse } from './validateResponse'

describe('approved display payload boundary', () => {
  it('accepts the recorded governed bridge', () => expect(validateQueryResponse(structuredClone(SAMPLE_RESPONSE)).verification?.verdict).toBe('PASS'))
  it('rejects contradictory display numbers despite PASS claims', () => {
    const r = structuredClone(SAMPLE_RESPONSE); r.analytics!.primary.value = '999'
    expect(() => validateQueryResponse(r)).toThrow()
  })
  it('rejects malformed optional analytics arrays', () => {
    const r = structuredClone(SAMPLE_RESPONSE) as unknown as Record<string, unknown>
    r.analytics = { ...SAMPLE_RESPONSE.analytics, components: null }
    expect(() => validateQueryResponse(r)).toThrow()
  })
  it('rejects executable source URLs', () => {
    const r = structuredClone(SAMPLE_RESPONSE); r.fact_sources![0].official_url = 'javascript:alert(1)'
    expect(() => validateQueryResponse(r)).toThrow()
  })
  it('rejects wrong units on displayed facts', () => {
    const r = structuredClone(SAMPLE_RESPONSE); r.analytics!.primary.unit = 'UNSUPPORTED'
    expect(() => validateQueryResponse(r)).toThrow()
  })
})
