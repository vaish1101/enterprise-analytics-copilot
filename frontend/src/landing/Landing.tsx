import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { ScrollToPlugin } from 'gsap/ScrollToPlugin'
import type { BarSpec, InstrumentFocus, PrecisionEngine, Study, Subject, SubjectFamily, Theme } from '../scene/PrecisionEngine'
import { BEATS, QUESTION_TOKENS, beatAt, buildStory, stageAt, type BeatId } from '../scene/story'
import type { ResultView } from '../lib/viewModel'
import { formatValue, magnitude } from '../lib/format'
import { useStrings } from '../i18n'
import { explain } from '../lib/explain'
import { ExplainPanel } from '../workspace/ExplainPanel'

gsap.registerPlugin(ScrollTrigger, ScrollToPlugin)

/** 'plain' is the same product without the instrument: small screens, reduced motion, no WebGL. */
type Mode = 'pending' | 'webgl' | 'plain'
const clamp01 = (v: number) => Math.min(1, Math.max(0, v))
const smooth = (a: number, b: number, v: number) => { const t = clamp01((v - a) / (b - a)); return t * t * (3 - 2 * t) }
const inOut = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2)
/** The question takes this long to reach the registration head; a response never waits longer. */
const RECEIVE_MS = 450
/** Story progress where a presentation that does not start in the hero begins: intake, nothing opened. */
const P_IN = 0.105
const INTERRUPT_KEYS = new Set(['ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', 'Home', 'End', ' '])

function supportsWebGL(): boolean {
  try { const c = document.createElement('canvas'); return !!(c.getContext('webgl2') || c.getContext('webgl')) } catch { return false }
}

/** Hero-only instrument response, triggered by the composer and example questions. */
export function focusInstrument(focus: InstrumentFocus) {
  window.dispatchEvent(new CustomEvent<InstrumentFocus>('eac-instrument', { detail: focus }))
}

const bar = (key: string, kind: BarSpec['kind'], from: number, to: number, land: BarSpec['land'], target: string): BarSpec => ({ key, kind, from, to, land, target })
const dataBar = (key: string) => `[data-bar="${key}"]`

/**
 * The governed figures the instrument moves for this answer, and how each lands in the
 * workspace. Only values present in the answer's own visual or headline figure are used;
 * a question without figures moves no blocks at all.
 */
export function barSpecsFor(view: ResultView): BarSpec[] {
  const visual = view.visual
  if (view.family === 'fact' && view.kpis[0]) return [bar('headline', 'endpoint', 0, magnitude(view.kpis[0].value), 'underline', '.kpi-primary .kpi-value')]
  if (!visual) return []
  switch (visual.kind) {
    case 'bridge': {
      const out: BarSpec[] = []
      let running = magnitude(visual.start.value)
      out.push(bar(visual.start.key, 'endpoint', 0, running, 'stand', dataBar(visual.start.key)))
      for (const c of visual.components) {
        const next = running + magnitude(c.value)
        out.push(bar(c.key, magnitude(c.value) < 0 ? 'down' : 'up', running, next, 'stand', dataBar(c.key)))
        running = next
      }
      out.push(bar(visual.end.key, 'endpoint', 0, magnitude(visual.end.value), 'stand', dataBar(visual.end.key)))
      return out
    }
    case 'comparison': {
      const [a, b] = visual.bars
      const out = visual.bars.map(x => bar(x.key, 'endpoint', 0, magnitude(x.value), 'stand', dataBar(x.key)))
      if (a && b && visual.change) out.push(bar('delta', 'delta', magnitude(a.value), magnitude(b.value), 'dissolve', '.cmp-change'))
      return out
    }
    case 'decomposition':
      return [...visual.components.map(c => bar(c.key, magnitude(c.value) < 0 ? 'down' : 'up', 0, magnitude(c.value), 'lie', dataBar(c.key))),
        bar(visual.total.key, 'endpoint', 0, magnitude(visual.total.value), 'dissolve', '.hbar-total')]
    case 'ranking':
      return visual.bars.map(x => bar(x.key, magnitude(x.value) < 0 ? 'down' : 'up', 0, magnitude(x.value), 'lie', dataBar(x.key)))
  }
}

const SUBJECT_FAMILIES: SubjectFamily[] = ['driver', 'breakdown', 'ranking', 'comparison', 'fact', 'definition', 'document']

/**
 * Everything the instrument shows comes from the depicted answer. The recorded sample may
 * show one illustrative failing draft (labelled as an example); a returned answer shows
 * exactly the failures its checks reported, and only the channels that ran.
 */
export function subjectFor(view: ResultView, sample: boolean): Subject {
  const cited = Math.min(5, view.citations.length)
  const bars = barSpecsFor(view)
  return {
    family: SUBJECT_FAMILIES.includes(view.family as SubjectFamily) ? view.family as SubjectFamily : 'findings',
    bars,
    analytics: bars.length > 0,
    evidence: sample || (view.execution?.retrieval ?? (view.citations.length + view.contextPassages.length) > 0),
    cited, leaves: Math.min(5, cited + view.contextPassages.length),
    supported: Math.min(6, view.verification.released),
    failed: sample ? 1 : Math.min(2, view.verification.removed),
    nodes: [view.context.company, view.context.scope, view.context.metric, view.context.period].filter(Boolean).length,
  }
}

export type Plan = 'full' | 'clarify' | 'boundary' | 'failure'
/**
 * What the instrument shows once the response is known, decided only by what came back.
 * Every outcome gets a presentation; none of them depicts work the response does not contain.
 */
export function planFor(view: ResultView | null): Plan {
  if (!view) return 'failure'
  if (view.family === 'clarification') return 'clarify'
  if (view.family === 'unsupported') return 'boundary'
  return view.verification.outcome === 'answer' ? 'full' : 'failure'
}

/**
 * How long the whole transformation takes once the response is known, by what it has to show.
 * One uninterrupted phrase: the explanation panel stays on screen, so nothing waits to be read.
 */
export function durationFor(view: ResultView, followUp: boolean): number {
  if (followUp) return 3.1
  switch (view.family) {
    case 'driver': case 'breakdown': case 'ranking': return 6.2
    case 'comparison': return 4.8
    default: return 4.2
  }
}
/** Where in the phrase the story ends and where the hand-off to the page begins: they overlap. */
const STORY_END = 0.84, HANDOFF_START = 0.66

/** Split the sample question into plain text and the phrases that resolve into its context. */
function questionParts(question: string, tokens: boolean) {
  if (!tokens) return [{ text: question }]
  const parts: { text: string; token?: number }[] = []
  const order = QUESTION_TOKENS.map((t, i) => ({ ...t, i, at: question.indexOf(t.phrase) })).filter(t => t.at >= 0).sort((a, b) => a.at - b.at)
  let cursor = 0
  for (const token of order) {
    if (token.at > cursor) parts.push({ text: question.slice(cursor, token.at) })
    parts.push({ text: token.phrase, token: token.i })
    cursor = token.at + token.phrase.length
  }
  if (question.slice(cursor)) parts.push({ text: question.slice(cursor) })
  return parts
}

export type StageKey = 'question' | 'figures' | 'evidence' | 'analysis' | 'checks' | 'answer' | 'pending' | 'clarify' | 'limit'
/**
 * Which stage of the explanation is on screen. It follows the same progress as the object and
 * names only what this response contains: a definition never shows "Figures", and a question
 * that stopped early says why instead of walking through stages that did not happen.
 */
export function stageFor(beat: BeatId, subject: Subject, view: ResultView, pending: boolean): StageKey {
  if (pending) return 'pending'
  if (beat === 'ask' || beat === 'register') return 'question'
  if (view.family === 'clarification') return 'clarify'
  if (view.verification.outcome !== 'answer') return 'limit'
  const data: StageKey = subject.analytics ? 'figures' : subject.evidence ? 'evidence' : 'question'
  switch (beat) {
    case 'analytics': return subject.analytics ? 'figures' : 'question'
    case 'evidence': return subject.evidence ? 'evidence' : data
    case 'converge': return subject.analytics && subject.evidence ? 'analysis' : subject.evidence ? 'evidence' : data
    case 'verify': return 'checks'
    default: return 'answer'
  }
}

/**
 * What each object label says under its name: the actual figures, source and check result of
 * the depicted response. Nothing is shown for a part the response does not contain.
 */
export function labelDetails(view: ResultView): Record<'figures' | 'evidence' | 'checks', string | null> {
  const v = view.visual
  // The bridge as it was reported: start, each contribution in published order, end.
  const plain = (value: string, signed: boolean) => { const n = magnitude(value); return `${signed ? (n < 0 ? '−' : '+') : ''}${Math.abs(n).toLocaleString(view.lang === 'de' ? 'de-DE' : 'en-GB')}` }
  const figures = v?.kind === 'bridge' ? [plain(v.start.value, false), ...v.components.map(c => plain(c.value, true)), plain(v.end.value, false)].join(' · ')
    : v?.kind === 'comparison' && v.bars.length === 2 ? `${formatValue(v.bars[0].value, v.bars[0].unit)} · ${formatValue(v.bars[1].value, v.bars[1].unit)}`
    : v?.kind === 'decomposition' ? formatValue(v.total.value, v.unit)
    : view.family === 'fact' && view.kpis[0] ? formatValue(view.kpis[0].value, view.kpis[0].unit) : null
  const c = view.citations[0]
  const title = c ? (c.source_title.length > 30 ? `${c.source_title.slice(0, 29)}…` : c.source_title) : null
  const evidence = c ? `${title} · p. ${c.page_number}${view.citations.length > 1 ? ` +${view.citations.length - 1}` : ''}` : null
  const checks = view.verification.outcome === 'answer' && !view.lead.located ? view.verification.title : view.plain?.kind === 'unsupported' ? view.plain.title : null
  return { figures, evidence, checks }
}

export type LandingApi = {
  /** The instrument can present (desktop, motion allowed, WebGL). Otherwise the page explains in text. */
  animated: boolean
  /** Go to the workspace without the walkthrough. */
  toProduct: () => void
  /**
   * A question was submitted, from anywhere. Takes ownership of the presentation and holds a
   * neutral pending state. Returns a token for `resolve`, or 0 when the instrument is not in use.
   */
  present: (question: string, options: { followUp: boolean }) => number
  /** The response arrived (or failed). Ignored unless `token` still owns the presentation. */
  resolve: (token: number, view: ResultView | null) => void
  /** Play the explanation of the answer on screen again. Uses the stored response only. */
  replay: () => void
}

export type Depicted = { view: ResultView; question: string; sample: boolean }

export function Landing({ depicted, mapped, theme, hero, product, footer, onReady, request }: {
  depicted: Depicted
  mapped: boolean
  theme: Theme
  hero: ReactNode; product: ReactNode; footer: ReactNode; onReady?: (api: LandingApi) => void
  request: 'idle' | 'loading' | 'ready'
}) {
  const { s, lang } = useStrings()
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const stageRef = useRef<HTMLElement>(null)
  const introRef = useRef<HTMLDivElement>(null)
  const figureRef = useRef<HTMLDivElement>(null)
  const productRef = useRef<HTMLElement>(null)
  const overlayRef = useRef<HTMLDivElement>(null)
  const stripRef = useRef<HTMLDivElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const stageCopyRef = useRef<HTMLDivElement>(null)
  const ghostRef = useRef<HTMLDivElement>(null)
  const tokenRefs = useRef<(HTMLSpanElement | null)[]>([])
  const sceneRef = useRef<PrecisionEngine | null>(null)
  const flattenRef = useRef<ScrollTrigger | null>(null)
  const pinRef = useRef<ScrollTrigger | null>(null)
  const veilRef = useRef<HTMLDivElement>(null)
  const labelRefs = useRef<Record<string, HTMLSpanElement | null>>({})
  const autoplay = useRef<gsap.core.Timeline | null>(null)
  // One owner at a time: a newer submission supersedes everything an older one scheduled.
  const owner = useRef(0)
  const pending = useRef<{ token: number; at: number; followUp: boolean } | null>(null)
  const timers = useRef<number[]>([])
  /**
   * The canonical presentation state. `p` is the story, `f` the hand-off to the page. Scrolling
   * sets the targets (`tp`, `tf`); autoplay writes `p` and `f` directly. Nothing else interpolates.
   */
  const pres = useRef({ p: 0, f: 0, tp: 0, tf: 0, auto: false })
  const rootRef = useRef<HTMLDivElement>(null)
  useEffect(() => { (window as unknown as { __pres?: unknown }).__pres = pres.current }, [])
  const submittedRef = useRef(false)
  /** idle: scroll owns the sequence. pending: waiting for the response. playing / paused: autoplay. */
  const [phase, setPhase] = useState<'idle' | 'pending' | 'playing' | 'paused'>('idle')
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null)
  const [mode, setMode] = useState<Mode>('pending')
  const [beat, setBeat] = useState(0)
  const reduced = useMemo(() => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false, [])
  const compact = useMemo(() => window.matchMedia?.('(max-width: 900px)').matches ?? false, [])
  const geometric = !compact
  const subject = useMemo(() => subjectFor(depicted.view, depicted.sample), [depicted])
  const tokens = depicted.sample && pendingQuestion === null
  const shownQuestion = pendingQuestion ?? depicted.question
  const parts = useMemo(() => questionParts(shownQuestion, tokens), [shownQuestion, tokens])
  // While a request is pending the panel claims nothing; afterwards it describes the response.
  const explanation = useMemo(() => explain(pendingQuestion !== null ? null : depicted.view, lang), [pendingQuestion, depicted, lang])
  const details = useMemo(() => labelDetails(depicted.view), [depicted])
  const depictedRef = useRef(depicted)
  depictedRef.current = depicted
  const langRef = useRef(lang)
  langRef.current = lang
  const mappedRef = useRef(mapped)
  mappedRef.current = mapped
  const subjectRef = useRef(subject)
  subjectRef.current = subject

  useEffect(() => { setMode(!reduced && !compact && supportsWebGL() ? 'webgl' : 'plain') }, [reduced, compact])
  useEffect(() => { sceneRef.current?.setTheme(theme) }, [theme])
  // The hero's entrance plays once. Pin refreshes re-insert the stage, which would otherwise replay it.
  const [entered, setEntered] = useState(false)
  useEffect(() => { const id = window.setTimeout(() => setEntered(true), 1700); return () => window.clearTimeout(id) }, [])

  // Presentation only: the depicted answer changes the instrument's data, never the reverse.
  useLayoutEffect(() => {
    const scene = sceneRef.current
    if (!scene) return
    scene.setSubject(subject)
    ScrollTrigger.refresh()
  }, [subject])
  useEffect(() => {
    if (sceneRef.current) sceneRef.current.mapToDom = mapped && geometric
    productRef.current?.classList.toggle('is-3d', mode === 'webgl' && mapped && geometric)
    if (!mapped || !geometric) productRef.current?.style.setProperty('--materialize', '1')
    requestAnimationFrame(() => { sceneRef.current?.refreshLayout(); ScrollTrigger.refresh() })
  }, [mapped, mode, geometric, depicted, lang])

  const productTop = () => (productRef.current?.getBoundingClientRect().top ?? 0) + window.scrollY

  // ---- The presentation controller: one for every composer, example, choice and replay. ----
  const controller = useMemo(() => {
    const story = () => sceneRef.current?.story
    const yAt = (p: number) => { const pin = pinRef.current!; return pin.start + p * (pin.end - pin.start) }
    const progressNow = () => { const pin = pinRef.current; return pin ? (window.scrollY - pin.start) / Math.max(1, pin.end - pin.start) : 0 }
    const later = (fn: () => void, ms: number) => { timers.current.push(window.setTimeout(fn, ms)) }
    /** Stop everything a previous presentation scheduled; leave the scroll-driven state as it is. */
    const cancel = () => {
      autoplay.current?.kill(); autoplay.current = null
      if (pres.current.auto) { pres.current.auto = false; rootRef.current?.removeAttribute('data-auto') }
      timers.current.forEach(id => window.clearTimeout(id)); timers.current = []
      if (ghostRef.current) { gsap.killTweensOf(ghostRef.current); gsap.set(ghostRef.current, { autoAlpha: 0 }) }
      if (veilRef.current) { gsap.killTweensOf(veilRef.current); gsap.set(veilRef.current, { autoAlpha: 0 }) }
      const st = story()
      if (st) { gsap.killTweensOf(st, 'receive,scan,hold,boundary,recede'); st.hold = 0; st.boundary = 0; st.recede = 0; st.scan = 0 }
      pending.current = null
    }
    const settle = () => { const st = story(); if (st) { st.receive = 0; st.scan = 0; st.hold = 0; st.boundary = 0; st.recede = 0 } }
    /** Take the state the current scroll position stands for, at once. */
    const snap = () => { ScrollTrigger.update(); const s = pres.current; s.p = s.tp; s.f = s.tf }
    const setAuto = (on: boolean) => { pres.current.auto = on; rootRef.current?.toggleAttribute('data-auto', on); if (on) sceneRef.current?.start() }
    /** A deliberate cut: the page dips out, the scroll position changes underneath, it returns. */
    const cut = (y: number, then?: () => void) => {
      const veil = veilRef.current
      if (!veil) { window.scrollTo(0, y); snap(); then?.(); return }
      gsap.killTweensOf(veil)
      gsap.timeline()
        .to(veil, { autoAlpha: 1, duration: 0.14, ease: 'none' })
        .add(() => { window.scrollTo(0, y); snap(); then?.() })
        .to(veil, { autoAlpha: 0, duration: 0.22, ease: 'none' }, '+=0.03')
    }
    const exit = () => { autoplay.current = null; cut(productTop(), () => { setAuto(false); settle(); snap(); setPhase('idle') }) }
    /**
     * The reader takes over. The scroll position is moved to the one that stands for what is on
     * screen, so the wheel continues the same sequence from exactly here.
     */
    const interrupt = () => {
      if (!autoplay.current) return
      autoplay.current.kill(); autoplay.current = null
      const st = story(), s = pres.current, pin = pinRef.current, flatten = flattenRef.current
      if (st) gsap.to(st, { hold: 0, boundary: 0, duration: 0.3, overwrite: 'auto' })
      if (pin && flatten) window.scrollTo(0, s.f > 0.001 ? flatten.start + s.f * (flatten.end - flatten.start) : yAt(s.p))
      setAuto(false)
      ScrollTrigger.update()
      if (s.f > 0.001) s.p = s.tp
      setPhase('idle')
    }
    /**
     * The response-specific transformation. It drives the canonical state directly, as one
     * phrase with no holds; the page is brought to its final position underneath, unseen, so
     * the parts can land on the real workspace.
     */
    const play = (view: ResultView | null, token: number, followUp: boolean) => {
      const st = story(), pin = pinRef.current, flatten = flattenRef.current
      const plan = planFor(view)
      if (!st || !pin || !flatten || !view || plan === 'failure') { exit(); return }
      const s = pres.current
      const p0 = s.p
      setAuto(true)
      const drive = { u: 0 }
      const tl = gsap.timeline()
      if (plan === 'full') {
        let under = false
        tl.to(drive, {
          u: 1, duration: durationFor(view, followUp), ease: 'none',
          onUpdate: () => {
            s.p = p0 + (1 - p0) * clamp01(drive.u / STORY_END)
            s.f = clamp01((drive.u - HANDOFF_START) / (1 - HANDOFF_START))
            // Once the hero has left, put the page where the answer will be. Everything on
            // screen is fixed, and the workspace stays unseen until the hand-off reaches it.
            if (!under && s.p > 0.14) { under = true; window.scrollTo(0, flatten.end); ScrollTrigger.update() }
          },
          onComplete: () => { if (owner.current !== token) return; autoplay.current = null; setAuto(false); settle(); snap(); setPhase('idle') },
        })
      } else {
        // A missing detail or a limit: a short controlled opening with nothing on the trays, then the page.
        if (plan === 'clarify') sceneRef.current?.setHold(view.plain?.options.some(o => /period|zeitraum/i.test(o.detail)) ? 3 : 2)
        tl.to(drive, { u: 1, duration: 1.25, ease: 'sine.out', onUpdate: () => { s.p = p0 + ((plan === 'clarify' ? 0.26 : 0.32) - p0) * drive.u } })
        tl.to(st, plan === 'clarify' ? { hold: 1, duration: 0.35, ease: 'expo.out' } : { boundary: 1, duration: 0.4, ease: 'expo.out' }, plan === 'clarify' ? 0.25 : 0.6)
        tl.add(exit, 1.55)
      }
      autoplay.current = tl
      setPhase('playing')
    }
    return { cancel, settle, cut, exit, interrupt, play, story, yAt, progressNow, later }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useLayoutEffect(() => {
    const c = controller
    const animated = mode === 'webgl' && !reduced
    onReady?.({
      animated,
      toProduct: () => {
        owner.current++
        c.cancel(); setPendingQuestion(null); setPhase('idle')
        if (!animated || !pinRef.current) { window.scrollTo({ top: productTop() }); return }
        if (Math.abs(productTop() - window.scrollY) < 4) return
        c.cut(productTop(), c.settle)
      },
      present: (question, { followUp }) => {
        const st = c.story()
        if (!animated || !st || !pinRef.current) return 0
        c.cancel()
        const token = ++owner.current
        pending.current = { token, at: performance.now(), followUp }
        submittedRef.current = true
        setPendingQuestion(question)
        setPhase('pending')
        // Neutral activation only: nothing registers, opens, computes or checks until the
        // answer has actually returned.
        const neutral = () => { gsap.to(st, { receive: 1, duration: RECEIVE_MS / 1000, ease: 'power2.out', overwrite: 'auto' }); gsap.to(st, { scan: 1, duration: 0.4, delay: 0.2, overwrite: 'auto' }) }
        if (c.progressNow() < 0.03) {
          // From the hero: the question travels from the composer into the instrument.
          const ghost = ghostRef.current, box = introRef.current?.querySelector('textarea')?.getBoundingClientRect()
          const scene = sceneRef.current
          if (ghost && box && scene) {
            ghost.textContent = question
            const to = scene.screenOf('carriage')
            gsap.fromTo(ghost, { x: box.left + 18, y: box.top + 14, scale: 1, autoAlpha: 1 },
              { x: to ? to.x - 10 : box.right, y: to ? to.y - 8 : box.top, scale: 0.18, autoAlpha: 0, duration: 0.45, ease: 'power2.inOut', transformOrigin: '0% 50%' })
          }
          neutral()
        } else {
          // From anywhere else: cut straight to the intake, never a rewind through the page.
          c.cut(c.yAt(P_IN), () => { st.receive = 1; neutral() })
        }
        return token
      },
      resolve: (token, view) => {
        const p = pending.current
        if (!p || p.token !== token || owner.current !== token) return
        pending.current = null
        const wait = Math.max(40, RECEIVE_MS - (performance.now() - p.at))
        c.later(() => requestAnimationFrame(() => requestAnimationFrame(() => {
          if (owner.current !== token) return
          const st = c.story()
          setPendingQuestion(null)
          if (st) gsap.to(st, { scan: 0, duration: 0.25, overwrite: 'auto' })
          c.play(view, token, p.followUp)
        })), wait)
      },
      replay: () => {
        if (!animated || !pinRef.current) return
        c.cancel()
        const token = ++owner.current
        setPendingQuestion(null)
        const view = depictedRef.current.view
        c.cut(c.yAt(P_IN), () => c.later(() => { if (owner.current === token) c.play(view, token, false) }, 260))
        setPhase('playing')
      },
    })
  }, [onReady, reduced, mode, controller])

  // Scrolling is the reader taking control: autoplay stops and the same sequence follows the wheel.
  useEffect(() => {
    if (phase !== 'playing' && phase !== 'paused') return
    const stop = () => controller.interrupt()
    const onKey = (event: KeyboardEvent) => { if (INTERRUPT_KEYS.has(event.key) && !(event.target as HTMLElement).closest?.('button, textarea, input')) stop() }
    window.addEventListener('wheel', stop, { passive: true })
    window.addEventListener('touchmove', stop, { passive: true })
    window.addEventListener('keydown', onKey)
    return () => { window.removeEventListener('wheel', stop); window.removeEventListener('touchmove', stop); window.removeEventListener('keydown', onKey) }
  }, [phase, controller])

  const skip = () => {
    owner.current++
    const answered = depictedRef.current.view.verification.outcome === 'answer' && pendingQuestion === null
    controller.cancel(); setPendingQuestion(null)
    controller.cut(answered && flattenRef.current ? flattenRef.current.end : productTop(), () => { controller.settle(); setPhase('idle') })
  }
  const skipRef = useRef(skip)
  skipRef.current = skip
  const togglePause = () => {
    const tl = autoplay.current
    if (!tl) return
    if (tl.paused()) { tl.resume(); setPhase('playing') } else { tl.pause(); setPhase('paused') }
  }

  useEffect(() => {
    if (mode !== 'webgl' || !canvasRef.current) return
    let disposed = false
    let cleanup = () => {}
    import('../scene/PrecisionEngine').then(({ PrecisionEngine }) => {
      if (disposed || !canvasRef.current) return
      let scene: PrecisionEngine
      try {
        const study = new URLSearchParams(window.location.search).get('study')?.toUpperCase()
        scene = new PrecisionEngine(canvasRef.current, { subject: subjectRef.current, compact, reducedMotion: reduced, theme, study: study === 'A' || study === 'B' || study === 'C' ? study as Study : undefined })
      } catch { setMode('plain'); return }
      sceneRef.current = scene
      ;(window as unknown as { __engine?: PrecisionEngine }).__engine = scene
      scene.onDegrade = () => setMode('plain')
      const onFocus = (event: Event) => scene.setFocus((event as CustomEvent<InstrumentFocus>).detail)
      window.addEventListener('eac-instrument', onFocus)
      const product = productRef.current!
      scene.heroAnchor = () => {
        const rect = figureRef.current?.getBoundingClientRect()
        return rect ? { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2, width: rect.width } : null
      }
      scene.mapToDom = mappedRef.current && geometric
      scene.setRoot(product)
      product.classList.toggle('is-3d', mappedRef.current && geometric)

      const story = buildStory(scene.story)
      story.to(introRef.current, { autoAlpha: 0, y: -28, duration: 0.05, ease: 'power2.in' }, 0.02)
      story.to(figureRef.current, { autoAlpha: 0, duration: 0.04 }, 0.01)
      story.to(scene.story, { hero: 0, duration: 0.1, ease: 'power2.inOut' }, 0)

      const stripOrigin = { x: 0, y: 0 }
      const measureStrip = () => {
        const strip = stripRef.current
        const composer = introRef.current?.querySelector('textarea')?.getBoundingClientRect()
        if (!composer || !strip || submittedRef.current) { stripOrigin.x = 0; stripOrigin.y = 0; return }
        strip.style.transform = 'none'
        const home = strip.getBoundingClientRect()
        stripOrigin.x = composer.left - home.left
        stripOrigin.y = composer.top - home.top
      }

      let progress = 0
      let flat = -1
      let settled = false
      let lastBeat = -1
      const overlay = overlayRef.current
      const state = pres.current
      /** Everything the hand-off progress controls, in one place. */
      const applyFlat = (p: number) => {
        if (p === flat) return
        flat = p
        scene.flat = p
        document.documentElement.style.setProperty('--calm', String(p))
        // The page starts materialising well before the instrument has landed: overlap,
        // never a blank interval between the two.
        if (geometric && mappedRef.current) product.style.setProperty('--materialize', String(clamp01((p - 0.06) / 0.7)))
        rootRef.current?.toggleAttribute('data-prehand', p <= 0.001)
        const done = p >= 0.999
        canvasRef.current?.classList.toggle('is-done', done)
        if (done && overlay) overlay.style.visibility = 'hidden'
        if (done && !state.auto) requestAnimationFrame(() => { if (flat >= 0.999 && !state.auto) scene.stop() })
      }
      // One canonical state, applied once per frame. Scrolling follows its target almost
      // directly (a ~80 ms settle, no long scrub); autoplay has already written it.
      scene.onTick = dt => {
        if (!state.auto) {
          const k = 1 - Math.exp(-dt / 0.08)
          state.p = Math.abs(state.tp - state.p) < 0.0004 ? state.tp : state.p + (state.tp - state.p) * k
          state.f = Math.abs(state.tf - state.f) < 0.0004 ? state.tf : state.f + (state.tf - state.f) * k
        }
        if (story.progress() !== state.p) story.progress(state.p)
        applyFlat(state.f)
        const b = beatAt(state.p)
        if (b !== lastBeat) { lastBeat = b; setBeat(b) }
      }
      scene.onFrame = sc => {
        if (!overlay) return
        progress = state.p
        const strip = stripRef.current, panel = panelRef.current
        const enter = smooth(0.05, 0.1, progress)
        const hand = inOut(clamp01((flat - 0.12) / 0.72))
        const visible = progress > 0.001 && flat < 0.999
        overlay.style.visibility = visible ? 'visible' : 'hidden'
        overlay.style.opacity = String(1 - sc.story.recede)
        if (strip && enter > 0 && enter < 1) measureStrip()
        if (strip) {
          strip.style.transform = `translate3d(${(stripOrigin.x * (1 - enter)).toFixed(1)}px, ${(stripOrigin.y * (1 - enter)).toFixed(1)}px, 0)`
          // One readable question at every frame. When the answer is mapped, this text travels onto
          // the workspace heading and the two swap at the instant they coincide; otherwise it
          // leaves before the workspace (with its own heading) scrolls into view.
          const flies = mappedRef.current && geometric && sc.mapToDom
          const landed = flies && hand >= 0.995
          // During autoplay the page already sits underneath; only a reader's own scroll moves it in.
          const gate = state.auto ? 1 : smooth(window.innerHeight * 0.84, window.innerHeight * 0.98, product.getBoundingClientRect().top)
          strip.style.opacity = String(flies ? (landed ? 0 : enter) : enter * gate)
          product.style.setProperty('--q', flies && !landed ? '0' : '1')
          const label = strip.querySelector<HTMLElement>('.q-label')
          if (label) label.style.opacity = String(1 - smooth(0, 0.3, hand))
          const text = strip.querySelector<HTMLElement>('.q-text')
          const heading = flies ? product.querySelector('[data-anatomy="question"]') : null
          if (text) {
            text.style.transform = 'none'
            if (!(heading && hand > 0)) text.style.width = ''
            if (heading && hand > 0) {
              const to = heading.getBoundingClientRect()
              const ratio = parseFloat(getComputedStyle(heading).fontSize) / parseFloat(getComputedStyle(text).fontSize)
              // Wrap like the heading it becomes, so the two coincide line for line.
              text.style.width = `${(to.width / ratio).toFixed(1)}px`
              const from = text.getBoundingClientRect()
              const lineShift = (parseFloat(getComputedStyle(heading).lineHeight) - parseFloat(getComputedStyle(text).lineHeight) * ratio) / 2
              text.style.transform = `translate3d(${((to.left - from.left) * hand).toFixed(1)}px, ${((to.top + lineShift - from.top) * hand).toFixed(1)}px, 0) scale(${(1 + (ratio - 1) * hand).toFixed(4)})`
            }
          }
        }
        // Narrative layer: steps aside as the workspace scrolls in, before it reaches it.
        const productTopNow = product.getBoundingClientRect().top
        const narrative = smooth(0.07, 0.11, progress) * (1 - smooth(0, 0.22, flat)) * (state.auto ? 1 : smooth(window.innerHeight * 0.72, window.innerHeight * 0.96, productTopNow))
        if (panel) {
          panel.style.opacity = String(narrative)
          if (stageCopyRef.current) stageCopyRef.current.style.opacity = String(narrative)
          // Sit under the question however many lines it takes.
          if (strip && enter >= 1) panel.style.top = `${Math.round(strip.offsetTop + strip.offsetHeight + 26)}px`
        }
        // Three labels on the object, each shown only while its part is doing something.
        const points = sc.labelPoints()
        for (const key of ['figures', 'evidence', 'checks'] as const) {
          const el = labelRefs.current[key], pt = points[key]
          if (!el) continue
          el.style.opacity = String(pt.o * narrative)
          el.style.transform = `translate3d(${pt.x.toFixed(1)}px, ${pt.y.toFixed(1)}px, 0)`
        }
        // The asked phrases are underlined while they are read, then the line settles.
        QUESTION_TOKENS.forEach((_, i) => {
          const span = tokenRefs.current[i]
          if (!span) return
          const appear = smooth(0.075 + i * 0.02, 0.09 + i * 0.02, progress)
          span.classList.toggle('is-reading', appear > 0.2 && progress < 0.2)
        })
      }

      const pin = ScrollTrigger.create({
        trigger: stageRef.current, start: () => (stageRef.current!.offsetHeight > window.innerHeight + 2 ? 'bottom bottom' : 'top top'),
        end: compact ? '+=140%' : '+=300%',
        pin: true, anticipatePin: 1, invalidateOnRefresh: true,
        // The trigger only reports where the reader is; the canonical state follows it.
        onUpdate: self => { state.tp = self.progress; scene.start() },
        onRefresh: self => { state.tp = self.progress; measureStrip() },
      })
      const flatten = ScrollTrigger.create({
        trigger: product, start: compact ? 'top bottom' : 'top 64%', invalidateOnRefresh: true,
        end: () => {
          const target = product.querySelector('[data-anatomy="visual"] .chart-svg') ?? product.querySelector('[data-anatomy="visual"]')
          if (!target || window.innerHeight < 820) return 'top top'
          const bottom = target.getBoundingClientRect().bottom - product.getBoundingClientRect().top
          return `top ${-Math.max(0, Math.round(bottom - (window.innerHeight - 100)))}px`
        },
        onUpdate: self => {
          // Hysteresis: once the page has taken over, small scrolls inside the workspace never
          // bring the instrument back over the answer; it reverses only well above it.
          if (self.progress >= 0.999) settled = true
          else if (self.progress < 0.4) settled = false
          state.tf = settled ? 1 : self.progress
          if (state.tf < 0.999) scene.start()
        },
        onRefresh: self => { if (self.progress >= 0.999) settled = true; state.tf = settled ? 1 : self.progress },
      })
      flattenRef.current = flatten
      pinRef.current = pin

      const onPointer = (event: PointerEvent) => scene.pointer.set(event.clientX / window.innerWidth * 2 - 1, -(event.clientY / window.innerHeight * 2 - 1))
      // Autoplay targets are measured positions: a resize ends it at the answer rather than chasing stale ones.
      const onResize = () => { scene.resize(); ScrollTrigger.refresh(); scene.refreshLayout(); if (autoplay.current) skipRef.current() }
      const onVisibility = () => { if (document.hidden) scene.stop(); else if (scene.flat < 0.999) scene.start() }
      window.addEventListener('pointermove', onPointer, { passive: true })
      window.addEventListener('resize', onResize)
      document.addEventListener('visibilitychange', onVisibility)
      canvasRef.current?.addEventListener('webglcontextlost', () => setMode('plain'))
      scene.start()
      measureStrip()
      ScrollTrigger.refresh()
      document.fonts?.ready?.then(() => { if (!disposed) { ScrollTrigger.refresh(); scene.refreshLayout() } }).catch(() => undefined)
      cleanup = () => {
        pin.kill(); flatten.kill(); story.kill()
        flattenRef.current = null; pinRef.current = null
        window.removeEventListener('pointermove', onPointer)
        window.removeEventListener('eac-instrument', onFocus)
        window.removeEventListener('resize', onResize)
        document.removeEventListener('visibilitychange', onVisibility)
        document.documentElement.style.removeProperty('--calm')
        scene.dispose(); sceneRef.current = null
      }
    }).catch(() => setMode('plain'))
    return () => { disposed = true; cleanup() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, compact, reduced])

  useEffect(() => { if (request === 'idle' && phase === 'idle') submittedRef.current = false }, [request, phase])

  // Which part of the explanation the sequence is currently showing.
  const stage = pendingQuestion !== null ? 0 : stageAt(beat)
  // The one line of process wording on screen, tied to the same progress as the object.
  const stageKey = stageFor(BEATS[beat].id, subject, depicted.view, pendingQuestion !== null)
  const [eyebrow, headline, sentence] = s.ex.stage[stageKey]
  return <div ref={rootRef} className={`experience mode-${mode} ${entered ? 'is-entered' : ''}`}>
    <div className="ambient" aria-hidden="true"><span className="pool pool-a" /></div>
    <canvas ref={canvasRef} className="scene-canvas" aria-hidden="true" />

    <main id="top">
      <section ref={stageRef} className="stage" aria-labelledby="hero-title">
        <div ref={introRef} className="intro">
          <p className="hero-context"><span>{s.hero.dataset}</span>{s.hero.datasetValue}</p>
          <h1 id="hero-title" className="hero-title">
            <span className="line"><span>{s.hero.title1}</span></span>{' '}
            <span className="line serif"><span>{s.hero.title2}</span></span>
          </h1>
          <p className="hero-sub">{s.hero.sub}</p>
          {hero}
          <p className="hero-status" role="status" aria-live="polite">{phase === 'pending' ? s.ex.preparing : ''}</p>
        </div>
        <div ref={figureRef} className="hero-figure" aria-hidden="true" />
      </section>

      <section ref={productRef} className="product" id="product" aria-label={s.workspace.label}>{product}</section>
      {footer}
    </main>

    {mode === 'webgl' && <div ref={overlayRef} className="story-overlay" aria-hidden="true">
      <div ref={stripRef} className="q-strip">
        <span className="q-label">{pendingQuestion !== null || !depicted.sample ? s.story.yourQuestion : s.story.demoQuestion}</span>
        <p className="q-text" lang="en">{parts.map((part, i) => part.token === undefined ? <span key={i}>{part.text}</span>
          : <span key={i} ref={el => { tokenRefs.current[part.token!] = el }} className="q-token">{part.text}</span>)}</p>
      </div>
      <div ref={panelRef} className="io-anchor"><ExplainPanel explanation={explanation} active={stage} /></div>
      <div ref={stageCopyRef} className="stage-copy"><div key={stageKey + lang} className={`stage-copy-in stage-${stageKey}`}>
        <p className="stage-eyebrow">{eyebrow}</p><p className="stage-headline">{headline}</p><p className="stage-sentence">{sentence}</p>
      </div></div>
      {(['figures', 'evidence', 'checks'] as const).map(key => <span key={key} ref={el => { labelRefs.current[key] = el }} className={`object-label label-${key}`}><b>{s.ex.labels[key]}</b>{pendingQuestion === null && details[key] && <i lang={key === 'evidence' ? 'en' : undefined}>{details[key]}</i>}</span>)}
    </div>}
    {mode === 'webgl' && <div ref={ghostRef} className="question-ghost" aria-hidden="true" lang="en" />}
    <div ref={veilRef} className="cut-veil" aria-hidden="true" />
    {phase !== 'idle' && <div className="play-controls" role="group" aria-label={s.ex.produced}>
      {phase !== 'pending' && <button type="button" onClick={togglePause}>{phase === 'paused' ? s.ex.resume : s.ex.pause}</button>}
      <button type="button" onClick={skip}>{s.story.skip}</button>
    </div>}
  </div>
}
