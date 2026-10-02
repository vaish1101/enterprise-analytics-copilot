import type { Metadata, QueryResponse } from '../types'
import { validateQueryResponse } from '../validateResponse'
import fixtures from './recorded.json'
import { SAMPLE_LABELS, SAMPLE_QUESTION, SAMPLE_RESPONSE } from './sample'

/** Exact-question recorded replay only. No fuzzy intent, arithmetic or network fallback. */
export function recordedMetadata(): Metadata {
  return { ...fixtures.metadata, provider_mode: 'test', labels: SAMPLE_LABELS }
}

export function recordedResponse(question: string): QueryResponse {
  const normalize = (q: string) => q.trim().toLowerCase().replace(/\s+/g, ' ')
  if (normalize(question) === normalize(SAMPLE_QUESTION)) return validateQueryResponse(structuredClone(SAMPLE_RESPONSE))
  const match = Object.entries(fixtures.responses).find(([q]) => normalize(q) === normalize(question))
  if (match) return validateQueryResponse(structuredClone(match[1]))
  // An unknown question never borrows the recorded example's figures or invokes a paid service.
  return validateQueryResponse({
    request_id: 'recorded', session_id: 'recorded', status: 'REFUSED', route: 'UNSUPPORTED',
    answer: 'This public demonstration replays selected examples only. Choose an example question; no live analysis was run.',
    claims: [], citations: [], limitations: ['PUBLIC_DEMO_RECORDED_ONLY'], verification: null,
    provenance_summary: [], execution: { analytics_used: false, retrieval_used: false, revision_used: false,
      provider_calls: 0, verifier_interventions: 0, input_tokens: 0, output_tokens: 0, cost_usd: '0', stages: [] },
    latency_ms: 0, provider: 'sample', model: 'recorded', analytics: null, fact_sources: [],
    clarification_question: null, refusal_reason: 'PUBLIC_DEMO_RECORDED_ONLY',
  })
}
