import { useRef, useState } from 'react'
import { useStrings } from '../i18n'
import { CATEGORY_EXAMPLES } from '../lib/examples'
import { Sheet } from '../shell/Sheet'
import { IconArrowRight } from '../workspace/glyphs'

/** Three things the product does, each with one question it is known to answer. */
const ROWS = [CATEGORY_EXAMPLES[1][0], CATEGORY_EXAMPLES[2][0], CATEGORY_EXAMPLES[3][0]]

/**
 * Capability rows under the composer, and a "What can I ask?" panel with the wider supported
 * coverage. Choosing a question fills the composer; submitting stays a deliberate action.
 */
export function AskGuide({ onPick, onHover }: { onPick: (question: string) => void; onHover?: (question: string | null) => void }) {
  const { s } = useStrings()
  const [open, setOpen] = useState(false)
  const trigger = useRef<HTMLButtonElement>(null)
  const pick = (question: string) => { setOpen(false); onPick(question) }
  return <div className="ask-guide">
    <ul className="ask-rows">
      {ROWS.map((question, i) => <li key={question}>
        <button type="button" onClick={() => onPick(question)}
          onMouseEnter={() => onHover?.(question)} onMouseLeave={() => onHover?.(null)} onFocus={() => onHover?.(question)} onBlur={() => onHover?.(null)}>
          <span className="ask-cap">{s.x.capabilities[i]}</span><span className="ask-q" lang="en">{question}</span><IconArrowRight size={14} />
        </button>
      </li>)}
    </ul>
    <button ref={trigger} type="button" className="text-button ask-more" onClick={() => setOpen(true)}>{s.hero.examples}</button>
    <Sheet open={open} onClose={() => setOpen(false)} title={s.hero.examples} returnFocus={trigger.current}>
      <div className="coverage">
        {s.hero.categories.map((label, i) => <section key={label}>
          <h4>{label}</h4>
          <ul className="ask-rows compact">{CATEGORY_EXAMPLES[i].map(question => <li key={question}>
            <button type="button" onClick={() => pick(question)}><span className="ask-q" lang="en">{question}</span><IconArrowRight size={14} /></button>
          </li>)}</ul>
        </section>)}
        <p className="sheet-lede">{s.hero.affiliation}</p>
      </div>
    </Sheet>
  </div>
}
