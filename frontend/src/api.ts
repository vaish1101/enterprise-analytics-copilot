import type { Metadata, QueryResponse } from './types'
import { validateQueryResponse } from './validateResponse'
import { recordedMetadata, recordedResponse } from './lib/recordedDemo'

export const isPublicDemo = () => import.meta.env.VITE_PUBLIC_DEMO === '1'

export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number) { super(message) }
}

async function decode<T>(response: Response): Promise<T> {
  const body = await response.json()
  if (!response.ok) {
    const error = body?.error
    throw new ApiError(error?.code ?? 'NETWORK_ERROR', error?.message ?? 'The governed service is unavailable.', response.status)
  }
  return body as T
}

export async function fetchMetadata(): Promise<Metadata> {
  if (isPublicDemo()) return recordedMetadata()
  return decode(await fetch('/api/v1/metadata'))
}

export async function askQuestion(question: string, sessionId?: string): Promise<QueryResponse> {
  if (isPublicDemo()) return validateQueryResponse(recordedResponse(question))
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), 95_000)
  try {
    const body = await decode<unknown>(await fetch('/api/v1/query', {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...(sessionId ? { 'X-Session-ID': sessionId } : {}) },
      body: JSON.stringify({ question, session_id: sessionId }), signal: controller.signal,
    }))
    try { return validateQueryResponse(body) }
    catch { throw new ApiError('INVALID_VERIFICATION_RESPONSE', 'The service returned an invalid verification result. No answer was released.', 502) }
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError('REQUEST_TIMEOUT', 'The governed workflow exceeded its bounded request time.', 504)
    }
    if (error instanceof ApiError) throw error
    if (error instanceof SyntaxError) throw new ApiError('INVALID_VERIFICATION_RESPONSE', 'The service returned a malformed response. No answer was released.', 502)
    throw new ApiError('NETWORK_ERROR', 'The service could not be reached. Check your connection and try again.', 0)
  } finally { window.clearTimeout(timeout) }
}

export async function deleteSession(sessionId: string): Promise<void> {
  if (isPublicDemo()) return
  const response = await fetch(`/api/v1/sessions/${encodeURIComponent(sessionId)}`, { method: 'DELETE' })
  if (!response.ok) throw new ApiError('SESSION_DELETE_FAILED', 'The session could not be cleared safely.', response.status)
}

export type SessionSummary = { session_id: string; interaction_count: number; interactions: { request_id?: string; question?: string; resolved_question?: string; status?: string }[] }

/** Safe session history (question, resolved question, status). Used to show carried-forward context. */
export async function fetchSession(sessionId: string): Promise<SessionSummary> {
  if (isPublicDemo()) return { session_id: 'recorded', interaction_count: 0, interactions: [] }
  return decode(await fetch(`/api/v1/sessions/${encodeURIComponent(sessionId)}`))
}
