import { afterEach, describe, expect, it, vi } from 'vitest'
import { askQuestion, fetchMetadata, fetchSession } from '../api'
import { recordedResponse } from './recordedDemo'
import fixtures from './recorded.json'
import { SAMPLE_QUESTION } from './sample'

afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals() })
describe('credential-free recorded public demo', () => {
  it('validates every reviewed fixture, including refusals and clarification', () => {
    for (const q of Object.keys(fixtures.responses)) expect(recordedResponse(q).status).toBeTruthy()
    expect(recordedResponse(SAMPLE_QUESTION).verification?.verdict).toBe('PASS')
    expect(recordedResponse(SAMPLE_QUESTION).execution.provider_calls).toBe(0)
  })
  it('fails closed for arbitrary questions without borrowing sample numbers', () => {
    const response = recordedResponse('Explain confidential customer churn')
    expect(response.status).toBe('REFUSED'); expect(response.claims).toEqual([])
    expect(response.analytics).toBeNull(); expect(response.answer).not.toContain('909')
    expect(response.execution.provider_calls).toBe(0)
  })
  it('never fetches a backend, provider or session in public demo mode', async () => {
    vi.stubEnv('VITE_PUBLIC_DEMO', '1')
    const network = vi.fn(() => { throw new Error('Public demo must not fetch') })
    vi.stubGlobal('fetch', network)
    expect((await fetchMetadata()).demo_mode).toBe(true)
    expect((await askQuestion(SAMPLE_QUESTION)).provider).toBe('sample')
    expect((await askQuestion('an unsupported question')).status).toBe('REFUSED')
    expect((await fetchSession('recorded')).interactions).toEqual([])
    expect(network).not.toHaveBeenCalled()
  })
})
