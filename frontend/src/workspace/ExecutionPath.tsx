import { useStrings } from '../i18n'
import type { ExecutionView } from '../lib/viewModel'

const TEXT = {
  en: {
    label: 'Recorded steps', question: 'Question', understood: 'Question understood', figures: 'Reported figures', reporting: 'Company reporting',
    drafted: 'Findings drafted', revised: ' · corrected once', checked: 'Findings checked',
    outcome: { released: 'Answer shown', subset: 'Supported findings shown', clarification: 'Asked for one detail', refused: 'Stopped at the limit of the reporting', conflict: 'Held back: sources disagree', failed: 'Stopped safely before showing anything' },
  },
  de: {
    label: 'Protokollierte Schritte', question: 'Frage', understood: 'Frage verstanden', figures: 'Berichtete Kennzahlen', reporting: 'Unternehmensberichte',
    drafted: 'Aussagen formuliert', revised: ' · einmal korrigiert', checked: 'Aussagen geprüft',
    outcome: { released: 'Antwort gezeigt', subset: 'Belegte Aussagen gezeigt', clarification: 'Nach einer Angabe gefragt', refused: 'An der Grenze der Berichterstattung gestoppt', conflict: 'Zurückgehalten: Quellen widersprechen sich', failed: 'Sicher gestoppt, bevor etwas gezeigt wurde' },
  },
}

/**
 * The steps that actually ran for one live answer, in the same two-channel language as the
 * instrument. Built only from the response's recorded stages and flags; a branch that did
 * not run is not drawn.
 */
export function ExecutionPath({ execution }: { execution: ExecutionView }) {
  const { lang } = useStrings()
  const t = TEXT[lang]
  const both = execution.analytics && execution.retrieval
  const branch = execution.analytics || execution.retrieval
  return <ol className={`exec-map ${both ? 'is-split' : ''}`} aria-label={t.label}>
    <li className="em-node">{t.question}</li>
    <li className="em-node">{t.understood}</li>
    {branch && <li className="em-branches">
      {execution.analytics && <span className="em-channel accent">{t.figures}</span>}
      {execution.retrieval && <span className="em-channel evidence">{t.reporting}</span>}
    </li>}
    {execution.synthesis && <li className="em-node">{t.drafted}{execution.revised ? t.revised : ''}</li>}
    {execution.verification && <li className="em-node verify">{t.checked}</li>}
    <li className={`em-node outcome outcome-${execution.outcome}`}>{t.outcome[execution.outcome]}</li>
  </ol>
}
