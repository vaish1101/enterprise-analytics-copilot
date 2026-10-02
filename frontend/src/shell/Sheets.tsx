import { useState } from 'react'
import { useStrings } from '../i18n'
import { deriveVerification } from '../lib/verification'
import type { QueryResponse } from '../types'
import { VerificationMark } from '../workspace/glyphs'
import { WorkflowDiagram } from '../workspace/WorkflowDiagram'
import { SCENARIOS, scenarioWorkflow, type Scenario } from '../lib/workflow'
import { Sheet } from './Sheet'

export type HistoryEntry = { id: number; question: string; response: QueryResponse; interpretedAs: string | null; at: Date; sessionId: string }

export function HistorySheet({ open, onClose, entries, onOpen, returnFocus }: {
  open: boolean; onClose: () => void; entries: HistoryEntry[]; onOpen: (entry: HistoryEntry) => void; returnFocus: HTMLElement | null
}) {
  const { s, lang } = useStrings()
  return <Sheet open={open} onClose={onClose} eyebrow={s.history.eyebrow} title={s.history.title} returnFocus={returnFocus}>
    <p className="sheet-lede">{s.history.lede}</p>
    {entries.length === 0 ? <p className="empty-note">{s.history.empty}</p>
      : <ol className="history-list">
        {[...entries].reverse().map(entry => {
          const v = deriveVerification(entry.response, lang)
          return <li key={entry.id}>
            <button type="button" onClick={() => onOpen(entry)}>
              <VerificationMark state={v.state} released={v.released} checked={v.checked || v.released} size={20} />
              <span className="history-q" lang="en">{entry.question}</span>
              <span className="history-meta">{v.title} · {entry.at.toLocaleTimeString(lang === 'de' ? 'de-DE' : 'en-GB', { hour: '2-digit', minute: '2-digit' })}</span>
            </button>
          </li>
        })}
      </ol>}
  </Sheet>
}

/* Small drawings in the instrument's own language, one per step. */
const STEP_ART = [
  // Understand: rail, carriage, registration plate with index blocks.
  <svg key="u" viewBox="0 0 96 56" aria-hidden="true"><path className="a-line" d="M6 44h54" /><rect className="a-accent" x="16" y="39" width="12" height="6" rx="1.5" />
    <rect className="a-body" x="60" y="12" width="6" height="34" rx="1.5" />
    {[0, 1, 2, 3].map(i => <rect key={i} className="a-accent" x="70" y={13 + i * 8} width="12" height="5" rx="1" />)}</svg>,
  // Trusted figures: contribution blocks on one scale.
  <svg key="f" viewBox="0 0 96 56" aria-hidden="true"><path className="a-line" d="M8 48h80" />
    {[[10, 62], [42, 30], [44, 10], [54, 12], [30, 8]].map(([x, w], i) => <rect key={i} className={i === 1 ? 'a-down' : 'a-accent'} x={x} y={10 + i * 7} width={w} height="5" rx="1" />)}</svg>,
  // Reporting: source leaves, one cited.
  <svg key="r" viewBox="0 0 96 56" aria-hidden="true"><path className="a-line" d="M8 50h80" />
    {[0, 1, 2, 3].map(i => <g key={i} transform={`translate(${14 + i * 18} 12) skewY(-8)`}><rect className={i === 0 ? 'a-leaf is-cited' : 'a-leaf'} width="14" height="34" rx="1" />{i === 0 && <rect className="a-tab" x="8" y="-4" width="5" height="4" />}</g>)}</svg>,
  // Check: the aperture passes a supported finding.
  <svg key="c" viewBox="0 0 96 56" aria-hidden="true"><path className="a-line" d="M6 28h84" /><ellipse className="a-ring" cx="48" cy="28" rx="10" ry="22" /><ellipse className="a-mint" cx="48" cy="28" rx="6" ry="16" />
    <rect className="a-claim" x="22" y="18" width="4" height="20" rx="1" /><rect className="a-claim is-passed" x="68" y="18" width="4" height="20" rx="1" /></svg>,
  // Only what can be supported: the answer plane; an unsupported draft stays outside.
  <svg key="a" viewBox="0 0 96 56" aria-hidden="true"><rect className="a-plane" x="26" y="6" width="62" height="44" rx="3" /><path className="a-line" d="M34 15h30M34 22h44" />
    {[0, 1, 2, 3].map(i => <rect key={i} className="a-accent" x={36 + i * 11} y={44 - (6 + (i % 3) * 5)} width="6" height={6 + (i % 3) * 5} />)}
    <rect className="a-claim is-dim" x="8" y="32" width="4" height="16" rx="1" transform="rotate(-18 10 40)" /></svg>,
]

type Tab = 'overview' | 'workflow' | 'technical'
const TABS: Tab[] = ['overview', 'workflow', 'technical']

export function HowItWorksSheet({ open, onClose, returnFocus }: { open: boolean; onClose: () => void; returnFocus: HTMLElement | null }) {
  const { s, lang } = useStrings()
  const [tab, setTab] = useState<Tab>('overview')
  const [scenario, setScenario] = useState<Scenario | null>(null)
  const de = lang === 'de'
  const onKey = (event: React.KeyboardEvent) => {
    const step = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0
    if (!step) return
    event.preventDefault()
    const next = TABS[(TABS.indexOf(tab) + step + TABS.length) % TABS.length]
    setTab(next)
    document.getElementById(`how-tab-${next}`)?.focus()
  }
  return <Sheet open={open} onClose={() => { setTab('overview'); setScenario(null); onClose() }} eyebrow={s.how.eyebrow} title={s.how.title} returnFocus={returnFocus} className={tab === 'workflow' ? 'sheet-wide sheet-xl' : 'sheet-wide'}>
    <div className="how-tabs" role="tablist" aria-label={s.how.title} onKeyDown={onKey}>
      {TABS.map((id, i) => <button key={id} id={`how-tab-${id}`} type="button" role="tab" aria-selected={tab === id} aria-controls={`how-panel-${id}`} tabIndex={tab === id ? 0 : -1} onClick={() => setTab(id)}>{s.wf.tabs[i]}</button>)}
    </div>
    {tab === 'overview' && <div id="how-panel-overview" role="tabpanel" aria-labelledby="how-tab-overview">
      <ol className="how-steps">
        {s.how.steps.map(([title, text], i) => <li key={title}>
          <div className="how-art">{STEP_ART[i]}</div>
          <div><p className="how-n">{i + 1}</p><h4>{title}</h4><p>{text}</p></div>
        </li>)}
      </ol>
      <section className="how-block">
        <h4>{s.how.data}</h4>
        <p>{s.how.dataText}</p>
      </section>
    </div>}
    {tab === 'workflow' && <div id="how-panel-workflow" role="tabpanel" aria-labelledby="how-tab-workflow" className="how-workflow">
      <h4>{s.wf.title}</h4>
      <p className="what-checked">{s.wf.lede}</p>
      <div className="wf-scenarios" role="group" aria-label={s.wf.scenarioLabel}>
        <span>{s.wf.scenarioLabel}</span>
        <button type="button" aria-pressed={scenario === null} onClick={() => setScenario(null)}>{s.wf.all}</button>
        {SCENARIOS.map(id => <button key={id} type="button" aria-pressed={scenario === id} onClick={() => setScenario(id)}>{s.wf.scenario[id]}</button>)}
      </div>
      <WorkflowDiagram workflow={scenarioWorkflow(scenario)} defaultTechnical />
    </div>}
    {tab === 'technical' && <section id="how-panel-technical" role="tabpanel" aria-labelledby="how-tab-technical" className="how-tech" aria-label={s.how.techTitle}>
      <h4>{s.wf.short}</h4>
      <p className="what-checked">{de
        ? 'Getrennte Rollen koordinieren Fragen-Routing, freigegebene Analysen, Berichts-Retrieval, Synthese und unabhängige Prüfung. Zahlen stammen ausschließlich aus der deterministischen Analyse; das Sprachmodell formuliert, entscheidet aber nicht über Werte.'
        : 'Separate roles coordinate question routing, governed analytics, reporting retrieval, synthesis and independent verification. Numbers come only from deterministic analysis; the language model writes, it does not decide values.'}</p>
      <ol className="exec-map is-split">
        <li className="em-node">Supervisor / Router · {de ? 'regelbasierter Plan, deterministisch' : 'rule-based plan, deterministic'}</li>
        <li className="em-branches"><span className="em-channel accent">Analytics · {de ? 'numerische Autorität' : 'numerical authority'}</span><span className="em-channel evidence">Knowledge / Retrieval · {de ? 'Dokumentpassagen' : 'document passages'}</span></li>
        <li className="em-node">Synthesis · {de ? 'ein strukturierter Modellaufruf' : 'one structured model call'}</li>
        <li className="em-node verify">Verifier / Critic · {de ? 'deterministische Prüfungen, höchstens eine Revision' : 'deterministic checks, at most one revision'}</li>
      </ol>
      <dl className="tech-stack">
        <dt>{de ? 'Orchestrierung' : 'Orchestration'}</dt><dd>LangGraph ({de ? 'begrenzter Analyse-Workflow, Checkpointing' : 'bounded analytical workflow, checkpointing'})</dd>
        <dt>API / {de ? 'Verträge' : 'contracts'}</dt><dd>Python · FastAPI · Pydantic</dd>
        <dt>Analytics</dt><dd>{de ? 'Freigegebener Kennzahlenkatalog · deterministische Berechnungswerkzeuge' : 'Governed metric catalogue · deterministic calculation tools'}</dd>
        <dt>Retrieval</dt><dd>PostgreSQL · pgvector (HNSW) · sentence-transformers (all-MiniLM-L6-v2)</dd>
        <dt>AI</dt><dd>OpenAI Responses {de ? 'mit' : 'with'} Structured Outputs ({de ? 'nur für die Synthese' : 'synthesis only'})</dd>
        <dt>Runtime</dt><dd>Docker · Docker Compose</dd>
        <dt>Frontend</dt><dd>React · TypeScript · Vite · Three.js ({de ? 'nur das Instrument' : 'the instrument only'})</dd>
        <dt>Motion</dt><dd>GSAP · SVG</dd>
      </dl>
      <p className="what-checked">{de
        ? 'Schrittdauern werden nach einem Lauf protokolliert; es gibt keinen Live-Fortschritt. Animationen zeigen daher nie Zwischenstände, bevor die Antwort vorliegt.'
        : 'Step timings are recorded after a run; there is no live progress stream. Animations therefore never show intermediate progress before the answer has returned.'}</p>
    </section>}
  </Sheet>
}
