import { strings, type Lang } from '../i18n/strings'
import type { QueryResponse } from '../types'
import { CATEGORY_EXAMPLES } from './examples'

/*
 * Plain-language presentation of the system's own clarification and refusal messages.
 *
 * The backend phrases these for operators ("Which governed metric should be used?"). Here
 * they are recognised by their fixed templates and shown in everyday words. Nothing is
 * reinterpreted: the choices offered are exactly the backend's options, the refusal is the
 * same refusal, and the original message stays available under Technical details.
 */

export type PlainOutcome = {
  kind: 'clarification' | 'unsupported'
  title: string
  line: string
  options: { label: string; detail: string; question: string }[]
  alternatives: { label: string; question: string }[]
  /** The system's original wording, for Technical details. */
  original: string | null
}

export function plainOutcome(response: QueryResponse, lang: Lang): PlainOutcome | null {
  const t = strings(lang).plain
  const detail = (d: string) => t.details[d] ?? d
  const options = (response.clarification_options ?? []).map(o => ({ ...o, label: t.labels[o.label] ?? o.label, detail: detail(o.detail) }))
  if (response.status === 'NEEDS_CLARIFICATION') {
    const q = response.clarification_question ?? response.answer ?? ''
    const term = q.match(/does '([^']+)' mean/i)?.[1]
    // Two concrete choices read better as the question itself: "Do you mean revenue or vehicles sold?"
    const lower = (x: string) => (lang === 'en' ? x.charAt(0).toLowerCase() + x.slice(1) : x)
    const [title, line] = term && options.length === 2 ? [t.orChoice(lower(options[0].label), lower(options[1].label)), t.meanLine]
      : term ? [t.meanTerm(term), t.meanLine]
      : /which governed metric/i.test(q) ? [t.whichMeasure, t.whichMeasureLine]
      : /which other governed company/i.test(q) ? [t.whichOther, t.whichOtherLine]
      : /should this question use/i.test(q) ? [t.whichCompany, t.whichCompanyLine]
      : /which two supported periods/i.test(q) ? [t.whichTwo, t.whichTwoLine]
      : /\b(Q[1-4]|H[12]) \d{4}\b.*\bor\b/.test(q) || /period/i.test(q) ? [t.whichPeriod, t.whichPeriodLine]
      : [t.generic, t.genericLine]
    // With no choices from the system, offer validated starting points instead of a dead end.
    const starters = options.length === 0 && /which governed metric/i.test(q) ? CATEGORY_EXAMPLES[0].concat(CATEGORY_EXAMPLES[2]).slice(0, 3).map(question => ({ label: question, question })) : []
    return { kind: 'clarification', title, line, options, alternatives: starters, original: q || null }
  }
  if (response.status === 'REFUSED' && !response.refusal_reason?.startsWith('WORKFLOW_FAILURE')) {
    const reason = response.refusal_reason ?? response.answer ?? ''
    const [title, line] = /price contribution|net pricing/i.test(reason) ? t.price
      : /period .* not available|planning scope/i.test(reason) ? t.period
      : /forecast|future|predict/i.test(reason) ? t.forecast
      : /metric is not present/i.test(reason) ? t.figure
      : /outside the governed|not (in|within) (the )?(governed )?scope|unsupported company|not covered/i.test(reason) ? t.scope
      : t.generic2
    const alternatives = (response.alternatives ?? []).map(a => ({ ...a, label: /reported bridge/i.test(a.label) ? t.viewBridge : a.label }))
    return { kind: 'unsupported', title, line, options: [], alternatives, original: reason || null }
  }
  return null
}
