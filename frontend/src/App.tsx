import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ApiError, askQuestion, fetchMetadata, fetchSession, isPublicDemo } from './api'
import { AskGuide } from './landing/AskGuide'
import { focusInstrument, Landing, type Depicted, type LandingApi } from './landing/Landing'
import { CATEGORY_EXAMPLES } from './lib/examples'
import { LanguageProvider, useStrings } from './i18n'
import type { InstrumentFocus } from './scene/PrecisionEngine'
import { SAMPLE_LABELS, SAMPLE_QUESTION, SAMPLE_RESPONSE } from './lib/sample'
import { useTheme } from './lib/theme'
import { buildResultView } from './lib/viewModel'
import { explain } from './lib/explain'
import { ExplainPanel } from './workspace/ExplainPanel'
import type { QueryResponse } from './types'
import { HistorySheet, HowItWorksSheet, type HistoryEntry } from './shell/Sheets'
import { TopBar } from './shell/TopBar'
import type { Metadata } from './types'
import { Composer, LoadingState, Result } from './workspace/Workspace'

/** Validated questions offered when an answer cannot be given; all are checked against the planner. */
export const EXAMPLES = [SAMPLE_QUESTION, CATEGORY_EXAMPLES[3][0], CATEGORY_EXAMPLES[4][0], CATEGORY_EXAMPLES[1][0]]

/** Which subassembly an example question exercises (hero hint only; the planner decides for real). */
function focusFor(question: string): InstrumentFocus {
  const q = question.toLowerCase()
  if (q.includes('define') || q.includes('definition')) return 'metric'
  if (q.includes('management') || q.includes('say') || q.includes('report')) return 'evidence'
  return 'analytics'
}

/* Application state. Presentation (scroll, camera, WebGL) never reads or writes this. */
type Live =
  | { kind: 'idle' }
  | { kind: 'loading'; question: string; startedAt: number }
  | { kind: 'result'; id: number; question: string; response: QueryResponse; interpretedAs: string | null; fromHistory?: 'resumed' | 'fresh' }
  | { kind: 'error'; question: string; error: ApiError }

export default function App() {
  return <LanguageProvider><Experience /></LanguageProvider>
}

function Experience() {
  const { s, lang } = useStrings()
  const { resolved, setPreference } = useTheme()
  const [metadata, setMetadata] = useState<Metadata | null>(null)
  const [live, setLive] = useState<Live>({ kind: 'idle' })
  const [heroQuestion, setHeroQuestion] = useState(SAMPLE_QUESTION)
  const [dockQuestion, setDockQuestion] = useState('')
  const [sessionId, setSessionId] = useState<string | undefined>()
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [sheet, setSheet] = useState<{ kind: 'history' | 'how'; trigger: HTMLElement | null } | null>(null)
  const [announcement, setAnnouncement] = useState('')
  const [navSolid, setNavSolid] = useState(false)
  const sequence = useRef(0)
  const dockRef = useRef<HTMLTextAreaElement>(null)
  const landingApi = useRef<LandingApi | null>(null)
  // Views are rebuilt from the stored response in the current language; nothing is re-run.
  const sampleView = useMemo(() => buildResultView(SAMPLE_RESPONSE, SAMPLE_LABELS, SAMPLE_QUESTION, 'sample', null, lang), [lang])
  const liveView = useMemo(() => live.kind === 'result' ? buildResultView(live.response, metadata?.labels, live.question, isPublicDemo() ? 'sample' : 'live', live.interpretedAs, lang) : null, [live, metadata, lang])

  useEffect(() => { fetchMetadata().then(setMetadata).catch(() => undefined) }, [])
  useEffect(() => {
    const onScroll = () => setNavSolid(window.scrollY > 16)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const submit = useCallback(async (raw: string, fresh = false) => {
    const question = raw.trim()
    if (question.length < 3) return
    const id = ++sequence.current
    setLive({ kind: 'loading', question, startedAt: Date.now() })
    setAnnouncement(s.announce.processing)
    // From the hero, the instrument takes the question in and waits in a neutral state; what
    // it shows next depends on what actually comes back. Elsewhere, go straight to the workspace.
    // Every submission is presented, wherever it comes from; a follow-up gets the shorter form.
    // A question asked from the hero is a fresh analysis; anything asked from the workspace is a follow-up.
    const followUp = !fresh
    const token = landingApi.current?.present(question, { followUp }) ?? 0
    if (!token) landingApi.current?.toProduct()
    try {
      const response = await askQuestion(question, sessionId)
      if (id !== sequence.current) return // superseded by a newer request or a new analysis
      const view = buildResultView(response, metadata?.labels, question, isPublicDemo() ? 'sample' : 'live', null, lang)
      if (token) landingApi.current?.resolve(token, view)
      setSessionId(response.session_id)
      setLive({ kind: 'result', id, question, response, interpretedAs: null })
      setHistory(items => [...items, { id, question, response, interpretedAs: null, at: new Date(), sessionId: response.session_id }])
      setAnnouncement(s.announce.ready(view.lead.located ? s.x.located[0] : view.verification.title))
      setDockQuestion('')
      // Show any context the backend carried forward from the previous question.
      fetchSession(response.session_id).then(session => {
        if (id !== sequence.current) return
        const last = session.interactions.filter(item => item.request_id === response.request_id).pop()
        const resolvedQuestion = typeof last?.resolved_question === 'string' ? last.resolved_question : null
        if (resolvedQuestion && resolvedQuestion.trim() !== question) {
          setLive(current => current.kind === 'result' && current.id === id ? { ...current, interpretedAs: resolvedQuestion } : current)
          setHistory(items => items.map(item => item.id === id ? { ...item, interpretedAs: resolvedQuestion } : item))
        }
      }).catch(() => undefined)
    } catch (caught) {
      if (id !== sequence.current) return
      if (token) landingApi.current?.resolve(token, null)
      setLive({ kind: 'error', question, error: caught as ApiError })
      setAnnouncement(s.announce.failed)
    }
  }, [sessionId, metadata, lang, s])

  const newAnalysis = useCallback(() => {
    sequence.current++
    setLive({ kind: 'idle' })
    setSessionId(undefined)
    setDockQuestion('')
    landingApi.current?.toProduct()
    window.setTimeout(() => dockRef.current?.focus({ preventScroll: true }), 450)
  }, [])

  /** "Edit question": put the question back in the composer; nothing is submitted. */
  const editQuestion = useCallback((question: string) => {
    setDockQuestion(question)
    window.setTimeout(() => { dockRef.current?.focus(); dockRef.current?.scrollIntoView({ block: 'center' }) }, 0)
  }, [])

  const [animated, setAnimated] = useState(false)
  const onLandingReady = useCallback((api: LandingApi) => { landingApi.current = api; setAnimated(api.animated) }, [])
  const showingSample = live.kind === 'idle'
  // The instrument depicts a returned answer whenever it was answered; otherwise the recorded sample.
  // A clarification or a limit is depicted as itself: it never borrows the sample's figures.
  const depicted = useMemo<Depicted>(() => liveView
    ? { view: liveView, question: liveView.question, sample: false }
    : { view: sampleView, question: SAMPLE_QUESTION, sample: true }, [liveView, sampleView])

  const t = s.outcome.transport
  const content = live.kind === 'loading' ? <LoadingState question={live.question} startedAt={live.startedAt} />
    : live.kind === 'error' ? <section className="outcome outcome-transport" role="alert" aria-labelledby="transport-title">
        <p className="outcome-eyebrow">{live.error.status === 429 ? t.limit : live.error.code === 'REQUEST_TIMEOUT' ? t.timeout : live.error.status === 0 ? t.connection : t.service}</p>
        <h3 id="transport-title" className="outcome-title">{t.title}</h3>
        <p className="outcome-message">{live.error.message}</p>
        <p className="outcome-line">{t.kept}</p>
        <button type="button" className="btn-secondary small" onClick={() => submit(live.question)}>{s.outcome.retry}</button>
      </section>
    : live.kind === 'result' && liveView ? <>
        {live.fromHistory && <p className="history-note" role="note">{live.fromHistory === 'resumed' ? s.workspace.historyResumed : s.workspace.historyFresh}</p>}
        {!animated && <ExplainPanel explanation={explain(liveView, lang)} />}
        <Result view={liveView} onAsk={submit} onEdit={editQuestion} examples={EXAMPLES} />
      </>
    : <>
        {!animated && <ExplainPanel explanation={explain(sampleView, lang)} />}
        <Result view={sampleView} onAsk={submit} examples={EXAMPLES} />
      </>

  const hero = <div className="hero-ask">
    <Composer variant="hero" label={s.hero.askLabel} value={heroQuestion} onChange={setHeroQuestion} onSubmit={() => submit(heroQuestion, true)}
      loading={live.kind === 'loading'} placeholder={s.hero.placeholder}
      onFieldFocus={focused => focusInstrument(focused ? 'wake' : null)}
      note={isPublicDemo() ? <p className="language-hint">{lang === 'de' ? 'Aufgezeichnete Beispiele, keine Live-KI. Wählen Sie eine Beispielfrage; andere Fragen werden nicht analysiert.' : 'Recorded examples, not live AI. Choose an example question; other questions are not analysed.'}</p> : lang === 'de' ? <p className="language-hint">{s.x.englishOnly}</p> : null} />
    <AskGuide onPick={setHeroQuestion} onHover={q => focusInstrument(q ? focusFor(q) : null)} />
  </div>

  return <>
    <TopBar solid={navSolid} resolved={resolved} onTheme={setPreference} historyCount={history.length} showNew={live.kind !== 'idle'}
      onHistory={trigger => setSheet({ kind: 'history', trigger })} onHowItWorks={trigger => setSheet({ kind: 'how', trigger })} onNew={newAnalysis} />
    <Landing depicted={depicted} mapped={showingSample || (liveView !== null && liveView.verification.outcome === 'answer')} theme={resolved} hero={hero} onReady={onLandingReady}
      request={live.kind === 'loading' ? 'loading' : live.kind === 'idle' ? 'idle' : 'ready'}
      product={<div className="workspace">
        <div className="workspace-tools">
          {live.kind !== 'idle' && <button type="button" className="text-button back-to-sample" onClick={() => { sequence.current++; setLive({ kind: 'idle' }) }}>{s.workspace.back}</button>}
          {animated && live.kind !== 'loading' && live.kind !== 'error' && <button type="button" className="text-button replay-explanation" onClick={() => landingApi.current?.replay()}>{s.ex.replay}</button>}
        </div>
        {content}
        <div className="dock">
          <Composer label={s.composer.followLabel} value={live.kind === 'error' && !dockQuestion ? live.question : dockQuestion} onChange={setDockQuestion}
            onSubmit={() => submit(live.kind === 'error' && !dockQuestion ? live.question : dockQuestion)} loading={live.kind === 'loading'} inputRef={dockRef}
            placeholder={live.kind === 'result' ? s.composer.followUp : s.hero.placeholder}
            note={lang === 'de' ? <p className="language-hint">{s.x.englishOnly}</p> : null} />
        </div>
      </div>}
      footer={<footer className="site-footer">
        <p>{s.footer.data}</p>
        <p>{s.footer.reuse}</p>
        <div className="footer-owner"><p>{s.footer.owner} · <a href="https://www.linkedin.com/in/vaishnavi-iyer-60b9141b1/" target="_blank" rel="noopener noreferrer">LinkedIn<span className="sr-only"> {s.inspector.opens}</span></a></p><p>{s.footer.built}</p></div>
      </footer>} />
    <HistorySheet open={sheet?.kind === 'history'} onClose={() => setSheet(null)} returnFocus={sheet?.trigger ?? null} entries={history}
      onOpen={entry => {
        sequence.current++
        // Follow-up context lives in the backend session and follows its latest question.
        // Restore the session only when this entry is that latest question; otherwise the
        // next question starts a new analysis instead of silently using other context.
        const latest = [...history].reverse().find(item => item.sessionId === entry.sessionId)
        const resumable = latest?.id === entry.id
        setSessionId(resumable ? entry.sessionId : undefined)
        setLive({ kind: 'result', id: entry.id, question: entry.question, response: entry.response, interpretedAs: entry.interpretedAs, fromHistory: resumable ? 'resumed' : 'fresh' })
        setSheet(null); landingApi.current?.toProduct()
      }} />
    <HowItWorksSheet open={sheet?.kind === 'how'} onClose={() => setSheet(null)} returnFocus={sheet?.trigger ?? null} />
    <div className="sr-only" role="status" aria-live="polite">{announcement}</div>
  </>
}
