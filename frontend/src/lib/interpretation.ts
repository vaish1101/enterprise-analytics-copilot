import { strings, type Lang } from '../i18n/strings'
import { formatValue } from './format'
import type { VerificationView } from './verification'
import type { Family, Lead, LimitationView, VisualView } from './viewModel'

export type InterpretationKind = 'numerical' | 'explanation' | 'documentary' | 'limitation' | 'cannot' | 'attribution' | 'checks'
export type InterpretationItem = { kind: InterpretationKind; label: string; text: string }

/** Limitation codes that are expressed by a dedicated dimension rather than repeated verbatim. */
const HANDLED = new Set(['MANAGEMENT_ATTRIBUTION_NOT_CAUSAL', 'COMBINED_COMPONENT_NOT_SPLIT', 'RECONCILIATION_FAILED'])

/**
 * How the result should be read, built only from the state of this response: reconciliation
 * results, released sources, limitation codes and the verification outcome. Nothing is
 * generated to fill the panel; a dimension with no backing state is left out.
 */
export function buildInterpretation(input: {
  family: Family; lead: Lead; visual: VisualView | null; codes: string[]; limitations: LimitationView[]
  citations: number; verification: VerificationView; lang: Lang
}): InterpretationItem[] {
  const { family, lead, visual, codes, citations, verification: v, lang } = input
  const t = strings(lang).interp
  const has = (code: string) => codes.includes(code)
  const items: InterpretationItem[] = []
  const add = (kind: InterpretationKind, text: string) => items.push({ kind, label: t.label[kind], text })

  if (has('RECONCILIATION_FAILED')) add('numerical', t.bridgeFailed)
  else if (visual?.kind === 'bridge' && visual.reconciled) add('numerical', t.bridge(formatValue(visual.start.value, visual.unit), formatValue(visual.end.value, visual.unit)))
  else if (visual?.kind === 'decomposition' && visual.reconciliation?.passed) add('numerical', t.parts)
  else if (visual?.kind === 'comparison' && lead.delta) add('numerical', t.change)

  const negative = family === 'driver' ? lead.rows.find(row => /^[−-]/.test(row.value)) : undefined
  if (negative) add('explanation', t.largestNeg(negative.label))

  if (lead.located) add('documentary', t.located)
  else if (family === 'definition' && citations > 0) add('documentary', t.definition)
  else if (citations > 0 && visual) add('documentary', t.sources(citations))

  if (has('COMBINED_COMPONENT_NOT_SPLIT')) { add('limitation', t.combined); add('cannot', t.priceAlone) }
  for (const item of input.limitations) if (!HANDLED.has(item.key)) add('limitation', item.text)
  if (has('MANAGEMENT_ATTRIBUTION_NOT_CAUSAL')) add('attribution', t.attribution)
  if (v.state === 'subset' || v.state === 'verified_with_limitations') add('checks', v.line)

  // A lone "numerical support" line on a plain figure adds nothing; qualification is the point.
  return items.some(item => item.kind !== 'numerical' && item.kind !== 'documentary') || items.length > 1 ? items : []
}
