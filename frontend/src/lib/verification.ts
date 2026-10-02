import { strings, type Lang } from '../i18n/strings'
import type { QueryResponse } from '../types'

/**
 * Verification describes the released *structured claims*. It never describes
 * the prose summary, which the deterministic verifier does not check.
 *
 * Priority order is fixed: the workflow status is read before the verifier label,
 * because the label alone can mislead (e.g. a refusal can carry a label).
 */
export type VerificationState =
  | 'clarification'
  | 'system_failure'
  | 'refused'
  | 'evidence_conflict'
  | 'verified'
  | 'subset'
  | 'verified_with_limitations'
  | 'unavailable'
  | 'unverifiable'

export type Outcome = 'answer' | 'clarification' | 'refusal' | 'conflict' | 'failure'

export type VerificationView = {
  state: VerificationState
  outcome: Outcome
  tone: 'mint' | 'amber' | 'neutral' | 'warm'
  title: string
  /** One line, suitable for the compact state. */
  line: string
  released: number
  checked: number
  removed: number
  revised: boolean
  issues: string[]
}

const ERROR_TEXT: Record<string, string> = {
  // Plain-language descriptions of verifier codes.
  UNKNOWN_FACT_LINEAGE: 'A claim referenced a fact outside the governed evidence bundle.',
  WRONG_OR_UNSUPPORTED_NUMBER: 'A number did not match any governed fact or calculation.',
  WRONG_COMPANY: 'A claim named the wrong company for its facts.',
  WRONG_METRIC: 'A claim used the wrong metric for its facts.',
  WRONG_SCOPE: 'A claim used the wrong business scope.',
  WRONG_PERIOD: 'A claim used a period its facts do not cover.',
  WRONG_UNIT: 'A claim used a unit that does not match its facts.',
  PROVENANCE_RELABELING: 'A claim was labelled with the wrong provenance.',
  CAUSAL_OVERSTATEMENT: 'A claim used causal wording for a management-attributed figure.',
  CALCULATION_LINEAGE_MISSING: 'A calculated claim had no calculation lineage.',
  UNKNOWN_CALCULATION_RUN: 'A claim referenced an unknown calculation run.',
  CITATION_NOT_IN_RETRIEVED_TOP_K: 'A claim cited a document passage that was not retrieved.',
  CITATION_WRONG_COMPANY: 'A citation belonged to a different company.',
  CITATION_WRONG_METRIC: 'A citation covered a different metric.',
  CITATION_WRONG_SCOPE: 'A citation covered a different business scope.',
  CITATION_WRONG_PERIOD: 'A citation covered a different period.',
  DOCUMENT_CITATION_MISSING: 'A claim had neither fact lineage nor a document citation.',
  UNSUPPORTED_INTERPRETATION: 'An interpretation had no supporting document evidence.',
  HENKEL_ROUNDING_CAVEAT_OMITTED: 'The required rounding caveat was missing.',
  EVIDENCE_CONFLICT: 'Governed facts and document evidence disagreed.',
}

export function describeIssue(code: string): string {
  return ERROR_TEXT[code] ?? code
}

/**
 * A released answer must carry a coherent verification result. Anything missing,
 * malformed or internally inconsistent fails closed: no figures, charts or findings.
 */
export function verificationProblem(response: QueryResponse): string | null {
  const v = response.verification as QueryResponse['verification'] | undefined
  if (response.status !== 'COMPLETED') return null
  if (!v || typeof v !== 'object') return 'missing'
  const int = (n: unknown) => typeof n === 'number' && Number.isInteger(n) && n >= 0
  if (!['PASS', 'NEEDS_REVISION'].includes(v.verdict)) return 'verdict'
  if (!int(v.supported_claims) || !int(v.total_claims) || v.supported_claims > v.total_claims) return 'counts'
  if (!Array.isArray(response.claims) || response.claims.length === 0) return 'no-claims'
  if (response.claims.length !== v.supported_claims) return 'released-mismatch'
  if (v.verdict === 'PASS' && v.supported_claims !== v.total_claims) return 'pass-mismatch'
  return null
}

export function deriveVerification(response: QueryResponse, lang: Lang = 'en'): VerificationView {
  const t = strings(lang)
  const v = response.verification
  const revised = response.execution.revision_used
  const released = response.claims.length
  const checked = v?.total_claims ?? 0
  const supported = v?.supported_claims ?? 0
  const base = { released, checked, removed: Math.max(0, checked - supported), revised, issues: (v?.errors ?? []).map(describeIssue) }

  if (response.status === 'NEEDS_CLARIFICATION') {
    return { ...base, state: 'clarification', outcome: 'clarification', tone: 'neutral', title: t.outcome.clarifyEyebrow, line: t.outcome.clarifyLine }
  }
  if (response.status === 'REFUSED' && response.refusal_reason?.startsWith('WORKFLOW_FAILURE')) {
    return { ...base, state: 'system_failure', outcome: 'failure', tone: 'warm', title: t.outcome.failure[0], line: t.outcome.failure[1] }
  }
  if (response.status === 'REFUSED') {
    return { ...base, state: 'refused', outcome: 'refusal', tone: 'neutral', title: t.outcome.refusedEyebrow, line: '' }
  }
  if (response.status === 'EVIDENCE_CONFLICT') {
    return { ...base, state: 'evidence_conflict', outcome: 'conflict', tone: 'amber', title: t.outcome.conflict[0], line: t.outcome.conflict[1] }
  }
  if (!v || verificationProblem(response)) {
    // Fail closed: an answer without a coherent check result is not shown as an answer.
    return { ...base, released: 0, state: 'unverifiable', outcome: 'failure', tone: 'warm', title: t.outcome.unverifiable[0], line: t.outcome.unverifiable[1] }
  }
  if (v.verdict === 'PASS') {
    return { ...base, state: 'verified', outcome: 'answer', tone: 'mint', title: t.status.verified(released), line: t.status.line }
  }
  if (supported < checked) {
    return { ...base, state: 'subset', outcome: 'answer', tone: 'amber', title: t.status.subset(supported, checked), line: t.status.subsetLine(checked - supported) }
  }
  return { ...base, state: 'verified_with_limitations', outcome: 'answer', tone: 'amber', title: t.status.limitations(released), line: t.status.limitationsLine }
}
