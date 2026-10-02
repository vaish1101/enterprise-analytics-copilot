import { strings, type Lang } from '../i18n/strings'
import type { ResultView } from './viewModel'

export type Explanation = { title: string; input: string[]; operation: string; output: string }

const lowerFirst = (text: string) => (/^[A-Z][a-z]/.test(text) ? text.charAt(0).toLowerCase() + text.slice(1) : text)

/**
 * Input / Operation / Output for one response, in plain language. Built only from the
 * response's own context and kind: nothing here describes work the response does not show.
 * `null` is the pending state, which claims nothing beyond the question having been asked.
 */
export function explain(view: ResultView | null, lang: Lang, failed = false): Explanation {
  const t = strings(lang)
  const e = t.ex
  if (failed) return { title: e.produced, input: [e.pendingInput], operation: e.op.failure(''), output: e.out.failure }
  if (!view) return { title: e.preparing, input: [e.pendingInput], operation: e.pendingOperation, output: e.pendingOutput }
  const c = view.context
  const family = view.family === 'ranking' ? 'breakdown' : view.family
  const kind = t.story.intent[family as keyof typeof t.story.intent] ?? c.route
  const input = [c.scope ?? c.company, c.metric, c.period, kind].filter((x): x is string => !!x)
  const metric = c.metric ? (lang === 'en' ? lowerFirst(c.metric) : c.metric) : ''
  // An answered question lists the parts that actually took part; a stop explains itself in a sentence.
  const answered = view.verification.outcome === 'answer'
  const figures = view.visual !== null || family === 'fact', evidence = view.citations.length > 0
  const parts = [figures && e.parts.figures, evidence && e.parts.evidence, figures && evidence && e.parts.synthesis, e.parts.checks].filter(Boolean) as string[]
  void metric
  return {
    title: view.kind === 'sample' ? e.illustration : e.produced,
    input: input.length > 1 ? input : [e.asAsked, ...input],
    operation: answered ? parts.join(' + ') : (e.op[family] ?? e.op.findings)(''),
    output: e.out[family] ?? e.out.findings,
  }
}
