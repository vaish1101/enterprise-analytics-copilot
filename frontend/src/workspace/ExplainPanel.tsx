import { useStrings } from '../i18n'
import type { Explanation } from '../lib/explain'

/**
 * The one explanation of a request: what went in, what was done, what came out. The same
 * panel sits beside the instrument while it plays and, where there is no instrument (small
 * screens, reduced motion, no WebGL), above the result.
 */
export function ExplainPanel({ explanation, active = null }: { explanation: Explanation; active?: 0 | 1 | 2 | null }) {
  const { s } = useStrings()
  const on = (i: number) => (active === null ? '' : active === i ? 'is-active' : active > i ? 'is-past' : '')
  return <section className="io-panel" aria-label={explanation.title}>
    <p className="io-title">{explanation.title}</p>
    <dl>
      <div className={on(0)}><dt>{s.ex.input}</dt><dd>{explanation.input.map((line, i) => <span key={line + i}>{line}</span>)}</dd></div>
      <div className={on(1)}><dt>{s.ex.operation}</dt><dd>{explanation.operation}</dd></div>
      <div className={on(2)}><dt>{s.ex.output}</dt><dd>{explanation.output}</dd></div>
    </dl>
  </section>
}
