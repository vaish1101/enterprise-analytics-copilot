import { useEffect, useId, useState, type FormEvent, type KeyboardEvent as ReactKeyboardEvent, type ReactNode, type RefObject } from 'react'
import { useStrings } from '../i18n'
import { spokenValue, valueParts } from '../lib/format'
import type { FindingView, KpiView, ResultView } from '../lib/viewModel'
import { AnalyticalVisual } from './charts'
import { EvidenceProvider, useEvidence } from './evidenceContext'
import { GlyphFact, IconArrowRight, IconArrowUp, IconChevron, IconCopy, SUPPORT_META, VerificationMark } from './glyphs'
import { ExecutionPath } from './ExecutionPath'
import { Inspector } from './Inspector'
import { WorkflowDiagram } from './WorkflowDiagram'
import { pendingWorkflow } from '../lib/workflow'

export function useEvidenceType() {
  const { s } = useStrings()
  return (value?: string | null) => (value && s.evidenceType[value]) ?? s.passage
}
const pad = (n: number) => String(n).padStart(2, '0')

/* ---- Header ------------------------------------------------------------------------ */

function ContextHeader({ view }: { view: ResultView }) {
  const { s } = useStrings()
  const parts = [view.context.company, view.context.scope, view.context.metric, view.context.period].filter(Boolean) as string[]
  return <div className="context-header" data-anatomy="context">
    <ol className="context-path" aria-label={s.workspace.context}>
      {parts.map((part, i) => <li key={part + i} data-anatomy-node={i}>{part}</li>)}
      {view.context.unit && view.verification.outcome === 'answer' && <li className="unit">{view.context.unit}</li>}
    </ol>
    <p className="context-meta"><span>{view.context.route}</span>
      {/* The internal test state is kept in the view but not badged: it is not a reader-facing concept. */}
      {view.kind !== 'test' && <span className={`kind-tag kind-${view.kind}`} title={view.kindNote}>{view.kindLabel}</span>}</p>
    {view.interpretedAs && <p className="interpreted">{s.workspace.interpreted} <q>{view.interpretedAs}</q></p>}
  </div>
}

export function QuestionHeading({ question }: { question: string }) {
  return <h2 className="question-heading" data-anatomy="question">{question}</h2>
}

/* ---- Support row: checks, sources, Evidence ------------------------------------------ */

function StatusRow({ view, steps, onSteps }: { view: ResultView; steps: boolean; onSteps: () => void }) {
  const { s } = useStrings()
  const v = view.verification
  const { openInspector, citations, factSources, activeClaim, activeCitation, setActiveCitation } = useEvidence()
  const activeIndexes = new Set(view.findings.find(f => f.id === activeClaim)?.citationIndexes ?? [])
  const figures = Object.keys(factSources).length
  return <section className={`status-row tone-${view.lead.located ? 'neutral' : v.tone}`} data-anatomy="verification" aria-label={s.status.label}>
    <div className="status-main">
      {!view.lead.located && <span data-anatomy-mark><VerificationMark state={v.state} released={v.released} checked={v.checked || v.released} size={22} /></span>}
      <div>
        <p className="status-title">{view.lead.located ? s.x.locatedStatus(citations.length) : v.title}</p>
        {!view.lead.located && <p className="status-line">{v.line}{v.revised ? <span className="revised"> {s.status.revised}</span> : null}</p>}
      </div>
    </div>
    <div className="status-support" data-anatomy="evidence">
      {citations.length > 0 && <div className="marker-row" role="group" aria-label={s.inspector.sources}>
        {citations.map(citation => <button type="button" key={citation.evidence_unit_id} data-anatomy-leaf={citation.index - 1}
          className={`cite-marker ${activeIndexes.has(citation.index) || activeCitation === citation.index ? 'is-lit' : ''}`}
          onMouseEnter={() => setActiveCitation(citation.index)} onMouseLeave={() => setActiveCitation(null)}
          onFocus={() => setActiveCitation(citation.index)} onBlur={() => setActiveCitation(null)}
          onClick={event => openInspector({ kind: 'citation', index: citation.index }, event.currentTarget)}
          aria-label={s.status.source(citation.index, citation.source_title, String(citation.page_number))}>{citation.index}</button>)}
      </div>}
      <span className="support-counts">{[
        citations.length ? `${s.status.sources(citations.length)}${view.sourceCount > 1 ? ` ${s.status.reports(view.sourceCount)}` : ''}` : null,
        figures ? s.status.figures(figures) : null].filter(Boolean).join(' · ')}</span>
    </div>
    {/* Three trust questions: where it came from, how to read it, how it was produced. */}
    <div className="trust-controls" role="group" aria-label={s.status.label}>
      <button type="button" className="inspect-button" onClick={event => openInspector({ kind: 'overview' }, event.currentTarget)}>{s.status.evidence}<IconChevron size={13} /></button>
      {view.interpretation.length > 0 && <button type="button" className="inspect-button" onClick={() => {
        const target = document.getElementById('interpretation')
        target?.scrollIntoView({ block: 'center', behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' })
        target?.focus({ preventScroll: true })
      }}>{s.interp.title}</button>}
      <button type="button" className="inspect-button" aria-expanded={steps} aria-controls="analysis-steps" onClick={onSteps}>{steps ? s.wf.hideSteps : s.wf.steps}</button>
    </div>
  </section>
}

/* ---- Direct answer --------------------------------------------------------------------- */

/**
 * The answer first, in the form the question calls for: a sentence and the few values that
 * carry it. Every value here comes from the response's reported figures or recorded
 * calculations; nothing is calculated in the interface.
 */
function DirectAnswer({ view }: { view: ResultView }) {
  const { s } = useStrings()
  const { openInspector } = useEvidence()
  const { lead } = view
  const rows = (items: typeof lead.rows) => <dl className="key-rows">{items.map(row => <div key={row.label}>
    <dt>{row.label}</dt>
    <dd>{row.factId !== undefined
      ? <button type="button" className="value-link num" onClick={event => openInspector({ kind: 'figure', factId: row.factId! }, event.currentTarget)} aria-label={`${row.label}: ${row.value}. ${s.chart.inspect}`}>{row.value}</button>
      : <span className="num">{row.value}</span>}</dd>
  </div>)}</dl>
  if (lead.delta) return <section className="direct" data-anatomy="summary" aria-label={s.answer.answer}>
    <h3 className="section-title">{s.x.change}</h3>
    <p className="delta num">{lead.delta.calcKey
      ? <button type="button" className="value-link" onClick={event => openInspector({ kind: 'calculation', key: lead.delta!.calcKey! }, event.currentTarget)}>{lead.delta.abs}</button>
      : lead.delta.abs}{lead.delta.pct && <span className="delta-pct"> · {lead.delta.pct}</span>}</p>
    {rows(lead.periods)}
  </section>
  if (lead.changed) return <section className="direct" data-anatomy="summary" aria-label={s.answer.answer}>
    <h3 className="section-title">{s.answer.answer}</h3>
    <p className="direct-text">{lead.changed}</p>
    {lead.rows.length > 0 && <><h3 className="section-title sub">{view.family === 'driver' ? s.x.largest : s.answer.contributed}</h3>{rows(lead.rows)}</>}
    {/* The material limit sits with the answer itself, not only in the section further down. */}
    {view.limitations.some(l => l.key === 'COMBINED_COMPONENT_NOT_SPLIT') && <p className="direct-note" role="note">{s.ex.combinedNote}</p>}
  </section>
  if (lead.located) return <section className="direct is-located" data-anatomy="summary" aria-label={s.answer.answer}>
    <h3 className="section-title">{s.answer.answer}</h3>
    <p className="direct-text">{s.x.located[0]}</p>
    <p className="direct-note">{s.x.located[1]}</p>
  </section>
  if (lead.answerFindings) return <section className="direct is-prose" data-anatomy="summary" aria-label={s.answer.answer}>
    <h3 className="section-title">{s.answer.answer}</h3>
    <ol className="answer-findings">{view.findings.slice(0, 3).map(f => <AnswerFinding key={f.id} finding={f} />)}</ol>
  </section>
  if (view.summary) return <section className="direct is-prose" data-anatomy="summary" aria-label={s.answer.answer}>
    <h3 className="section-title">{s.answer.answer} <span className="ai-tag">{view.kind === 'sample' ? s.wf.d.byRecorded : view.kind === 'test' ? s.wf.d.byTest : s.answer.writtenLabel}</span></h3>
    <p className="direct-text">{view.summary}</p>
  </section>
  return <div className="direct is-empty" data-anatomy="summary" />
}

/** A single reported figure: the value, what it is, and where it was published. */
function FactAnswer({ view }: { view: ResultView }) {
  const { s } = useStrings()
  const kpi = view.kpis[0]
  if (!kpi) return <DirectAnswer view={view} />
  return <section className="direct is-fact" aria-label={s.answer.answer}>
    <KpiStrip kpis={[kpi]} lead />
    <p className="direct-note">{s.x.factSentence(kpi.label, view.context.scope ?? view.context.company, kpi.period)}</p>
  </section>
}

/** A verified finding used as the answer itself (definitions, company reporting). */
function AnswerFinding({ finding }: { finding: FindingView }) {
  const { s } = useStrings()
  const { openInspector, citations, setActiveCitation, activeCitation } = useEvidence()
  return <li>
    <p>{finding.text}</p>
    <span className="answer-sources">{finding.citationIndexes.map(i => {
      const c = citations.find(x => x.index === i)
      return <button type="button" key={i} className={`cite-marker small ${activeCitation === i ? 'is-lit' : ''}`}
        onMouseEnter={() => setActiveCitation(i)} onMouseLeave={() => setActiveCitation(null)}
        onClick={event => openInspector({ kind: 'citation', index: i }, event.currentTarget)}
        aria-label={c ? s.status.source(i, c.source_title, String(c.page_number)) : String(i)}>{i}</button>
    })}</span>
  </li>
}

function WrittenSummary({ text, kind }: { text: string; kind: ResultView['kind'] }) {
  const { s } = useStrings()
  const [copied, setCopied] = useState(false)
  async function copy() {
    try { await navigator.clipboard.writeText(text); setCopied(true); window.setTimeout(() => setCopied(false), 1600) } catch { /* clipboard unavailable */ }
  }
  return <details className="written">
    <summary>{s.answer.written} <span className="ai-tag">{kind === 'sample' ? s.wf.d.byRecorded : kind === 'test' ? s.wf.d.byTest : s.answer.writtenLabel}</span></summary>
    <p className="written-text">{text}</p>
    <p className="written-note">{kind === 'sample' ? s.kind.sampleNote : kind === 'test' ? s.kind.testNote : s.answer.writtenNote}</p>
    <button type="button" className="note-button" onClick={copy} aria-live="polite"><IconCopy size={13} />{copied ? s.answer.copied : s.answer.copy}</button>
  </details>
}

/* ---- Figures ------------------------------------------------------------------------ */

function Kpi({ kpi, index }: { kpi: KpiView; index: number }) {
  const { s } = useStrings()
  const { factSources, openInspector } = useEvidence()
  const source = kpi.factId !== undefined ? factSources[kpi.factId] : undefined
  const parts = valueParts(kpi.value, kpi.unit, kpi.signed)
  const Meta = SUPPORT_META[kpi.support]
  const [supportLabel] = s.support[kpi.support]
  const label = `${kpi.label}, ${kpi.period}: ${spokenValue(kpi.value, kpi.unit)}. ${supportLabel}.`
  return <li className={`kpi kpi-${kpi.role}`} data-anatomy-kpi={index}>
    <button type="button" className="kpi-button" aria-label={`${label} ${s.chart.inspect}`} disabled={kpi.factId === undefined && !kpi.calcKey}
      onClick={event => kpi.calcKey ? openInspector({ kind: 'calculation', key: kpi.calcKey }, event.currentTarget)
        : kpi.factId !== undefined && openInspector({ kind: 'figure', factId: kpi.factId }, event.currentTarget)}>
      <span className="kpi-label"><span>{kpi.label}</span><span className="kpi-period">{kpi.period}</span></span>
      <span className="kpi-value" aria-hidden="true"><span className="kpi-sign">{parts.sign}</span>{parts.prefix}<span className="kpi-digits">{parts.digits}</span><span className="kpi-unit">{parts.unit}</span></span>
      <span className={`kpi-support support-${kpi.support}`} aria-hidden="true"><Meta.Glyph size={13} />{supportLabel}</span>
      {source && <span className="kpi-source" aria-hidden="true"><GlyphFact size={12} />{source.source_title} · {source.page_or_sheet}</span>}
    </button>
  </li>
}

function KpiStrip({ kpis, lead = false }: { kpis: KpiView[]; lead?: boolean }) {
  const { s } = useStrings()
  if (!kpis.length) return null
  return <ul className={`kpi-strip n-${kpis.length} ${lead ? 'is-lead' : ''}`} data-anatomy="kpi" aria-label={s.chart.eyebrow}>
    {kpis.map((kpi, i) => <Kpi key={kpi.key} kpi={kpi} index={i} />)}
  </ul>
}

/* ---- Sources ------------------------------------------------------------------------------ */

function Sources({ view }: { view: ResultView }) {
  const { s } = useStrings()
  const evidenceType = useEvidenceType()
  const { openInspector, activeCitation, setActiveCitation, activeClaim } = useEvidence()
  const lit = new Set(view.findings.find(f => f.id === activeClaim)?.citationIndexes ?? [])
  if (!view.citations.length && !view.contextPassages.length) return null
  return <section className="passages" aria-label={s.answer.sources}>
    <h3 className="section-title">{s.answer.sources}</h3>
    <ol className="passage-list">
      {view.citations.map(citation => {
        const findings = view.findings.filter(f => f.citationIndexes.includes(citation.index))
        return <li key={citation.evidence_unit_id} className={activeCitation === citation.index || lit.has(citation.index) ? 'is-lit' : ''}
          onMouseEnter={() => setActiveCitation(citation.index)} onMouseLeave={() => setActiveCitation(null)}>
          <span className="cite-marker static" aria-hidden="true">{citation.index}</span>
          <div>
            <button type="button" className="passage-title" onClick={event => openInspector({ kind: 'citation', index: citation.index }, event.currentTarget)}>{citation.source_title}</button>
            <p>{s.answer.page(String(citation.page_number))}{citation.section ? ` · ${citation.section}` : ''} · {evidenceType(citation.evidence_type)}</p>
            {findings.length > 0 && !view.lead.answerFindings && <p className="relation">{s.answer.supportsFinding(findings.map(f => pad(f.index)).join(', '))}</p>}
          </div>
        </li>
      })}
    </ol>
    {view.contextPassages.length > 0 && <button type="button" className="text-button context-link" onClick={event => openInspector({ kind: 'overview' }, event.currentTarget)}>
      {s.answer.morePassages(view.contextPassages.length)}</button>}
  </section>
}

/* ---- Key findings ------------------------------------------------------------------------- */

function Finding({ finding }: { finding: FindingView }) {
  const { s } = useStrings()
  const { activeClaim, activeCitation, setActiveClaim, openInspector, setActiveCitation, citations } = useEvidence()
  const [expanded, setExpanded] = useState(false)
  const lit = activeClaim === finding.id || (activeCitation !== null && finding.citationIndexes.includes(activeCitation))
  const long = finding.text.length > 190
  return <li className={`finding ${lit ? 'is-lit' : ''}`} onMouseEnter={() => setActiveClaim(finding.id)} onMouseLeave={() => setActiveClaim(null)}
    onFocus={() => setActiveClaim(finding.id)} onBlur={() => setActiveClaim(null)}>
    <span className="finding-index" aria-hidden="true">{pad(finding.index)}</span>
    <div className="finding-body">
      <p className={`finding-text ${long && !expanded ? 'clamped' : ''}`}>{finding.text}</p>
      {long && <button type="button" className="text-button" aria-expanded={expanded} onClick={() => setExpanded(v => !v)}>{expanded ? s.answer.less : s.answer.full}</button>}
      <div className="finding-support">
        {finding.support.filter(kind => kind !== 'document').map(kind => {
          const Meta = SUPPORT_META[kind]
          const [label, description] = s.support[kind]
          return <span key={kind} className={`support support-${kind}`} title={description}><Meta.Glyph size={13} />{label}</span>
        })}
        {finding.citationIndexes.map(i => {
          const citation = citations.find(c => c.index === i)
          return <button type="button" key={i} className={`cite-marker small ${activeCitation === i ? 'is-lit' : ''}`}
            onMouseEnter={() => setActiveCitation(i)} onMouseLeave={() => setActiveCitation(null)} onFocus={() => setActiveCitation(i)} onBlur={() => setActiveCitation(null)}
            onClick={event => openInspector({ kind: 'citation', index: i }, event.currentTarget)}
            aria-label={citation ? s.status.source(i, citation.source_title, String(citation.page_number)) : String(i)}>{i}</button>
        })}
        <button type="button" className="finding-inspect" onClick={event => openInspector({ kind: 'finding', id: finding.id }, event.currentTarget)}
          aria-label={s.answer.findingSourceLabel(finding.index)}>{s.answer.findingSource}<IconChevron size={12} /></button>
      </div>
    </div>
  </li>
}

function Findings({ view }: { view: ResultView }) {
  const { s } = useStrings()
  const [all, setAll] = useState(false)
  if (!view.findings.length || view.lead.answerFindings) return null
  const shown = all ? view.findings : view.findings.slice(0, 3)
  return <section className="findings" aria-label={s.answer.findings}>
    <h3 className="section-title">{s.answer.findings}</h3>
    <ol className="finding-list">{shown.map(f => <Finding key={f.id} finding={f} />)}</ol>
    {view.findings.length > 3 && <button type="button" className="text-button more" aria-expanded={all} onClick={() => setAll(v => !v)}>{all ? s.answer.fewer : s.answer.showAll(view.findings.length)}</button>}
  </section>
}

/** What the company's own reporting says: the checked findings that rest on a cited source. */
function ManagementReported({ view }: { view: ResultView }) {
  const { s } = useStrings()
  const cited = view.findings.filter(f => f.citationIndexes.length > 0).slice(0, 2)
  if (!cited.length || view.lead.answerFindings) return null
  return <section className="reported" aria-label={s.answer.management}>
    <h3 className="section-title">{s.answer.management}</h3>
    <ol className="answer-findings compact">{cited.map(f => <AnswerFinding key={f.id} finding={f} />)}</ol>
  </section>
}

/** How to read the result. Every line is backed by the state of this response; nothing is filler. */
function Interpretation({ view }: { view: ResultView }) {
  const { s } = useStrings()
  if (!view.interpretation.length) return null
  return <section className="interpretation" id="interpretation" tabIndex={-1} aria-label={s.interp.title}>
    <h3 className="section-title">{s.interp.title}</h3>
    <dl>{view.interpretation.map((item, i) => <div key={`${item.kind}-${i}`} className={`interp-${item.kind}`}><dt>{item.label}</dt><dd>{item.text}</dd></div>)}</dl>
  </section>
}

/** The route this request took. Supporting information: collapsed until asked for. */
function AnalysisSteps({ view }: { view: ResultView }) {
  const { s } = useStrings()
  return <section className="wf-panel" id="analysis-steps" aria-label={s.wf.stepsTitle}>
    <h3 className="section-title">{s.wf.stepsTitle}<span>{s.wf.short}</span></h3>
    <WorkflowDiagram workflow={view.workflow} />
  </section>
}

/* ---- Outcomes without an answer ------------------------------------------------------------ */

function Outcome({ view, onAsk, onEdit, examples }: { view: ResultView; onAsk: (q: string) => void; onEdit?: (q: string) => void; examples: string[] }) {
  const { s } = useStrings()
  const v = view.verification
  const plain = view.plain
  const [title, line] = plain ? [plain.title, plain.line]
    : v.state === 'evidence_conflict' ? s.outcome.conflict : v.state === 'unverifiable' ? s.outcome.unverifiable : s.outcome.failure
  const eyebrow = plain?.kind === 'clarification' ? s.outcome.clarifyEyebrow : plain?.kind === 'unsupported' ? s.outcome.refusedEyebrow : null
  const retry = v.state === 'system_failure' || v.state === 'evidence_conflict' || v.state === 'unverifiable'
  return <section className={`outcome outcome-${plain?.kind ?? v.state}`} data-anatomy="verification" aria-labelledby="outcome-title" role="status">
    {eyebrow && <p className="outcome-eyebrow">{eyebrow}</p>}
    <h3 id="outcome-title" className="outcome-title">{title}</h3>
    <p className="outcome-message">{line}</p>
    {plain && plain.options.length > 0 && <div className="choice-grid" role="group" aria-label={title}>
      {plain.options.map(option => <button type="button" key={option.question} className="choice" onClick={() => onAsk(option.question)}>
        <span className="choice-label">{option.label}</span><span className="choice-detail">{option.detail}</span><IconArrowRight size={15} />
      </button>)}
    </div>}
    {plain && plain.alternatives.length > 0 && <div className="choice-grid">
      {plain.alternatives.map(alt => <button type="button" key={alt.question} className="choice primary" onClick={() => onAsk(alt.question)}>
        <span className="choice-label" lang={alt.label === alt.question ? 'en' : undefined}>{alt.label}</span>{alt.label !== alt.question && <span className="choice-detail" lang="en">{alt.question}</span>}<IconArrowRight size={15} />
      </button>)}
    </div>}
    {plain?.kind === 'unsupported' && plain.alternatives.length === 0 && examples.length > 0 && <div className="try-instead">
      <p className="outcome-eyebrow">{s.outcome.tryInstead}</p>
      <div className="example-row">{examples.slice(0, 3).map(q => <button type="button" key={q} className="example-chip" onClick={() => onAsk(q)}>{q}</button>)}</div>
    </div>}
    {plain?.kind === 'unsupported' && onEdit && <button type="button" className="text-button outcome-edit" onClick={() => onEdit(view.question)}>{s.x.editQuestion}</button>}
    {retry && <button type="button" className="btn-secondary small" onClick={() => onAsk(view.question)}>{s.outcome.retry}</button>}
    {(plain?.original || view.execution) && <details className="outcome-exec"><summary>{s.outcome.technical}</summary>
      {plain?.original && <p className="outcome-original"><span>{s.outcome.backend}:</span> {plain.original}</p>}
      {view.execution && <ExecutionPath execution={view.execution} />}
    </details>}
  </section>
}

/* ---- Composer ------------------------------------------------------------------------------ */

export function Composer({ value, onChange, onSubmit, loading, examples, placeholder, inputRef, variant = 'dock', onExample, label, examplesLabel, onFieldFocus, onExampleHover, note }: {
  value: string; onChange: (v: string) => void; onSubmit: () => void; loading: boolean; examples?: string[]
  placeholder?: string; inputRef?: RefObject<HTMLTextAreaElement | null>; variant?: 'dock' | 'hero'; onExample?: (q: string) => void; label?: string
  examplesLabel?: string; onFieldFocus?: (focused: boolean) => void; onExampleHover?: (q: string | null) => void; note?: ReactNode
}) {
  const { s } = useStrings()
  const id = useId()
  const disabled = loading || value.trim().length < 3
  function submit(event?: FormEvent) { event?.preventDefault(); if (!disabled) onSubmit() }
  function keyDown(event: ReactKeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey || (!event.shiftKey && variant === 'hero'))) { event.preventDefault(); submit() }
  }
  return <form className={`composer composer-${variant}`} data-anatomy={variant === 'dock' ? 'composer' : undefined} onSubmit={submit}>
    <label htmlFor={id} className="composer-label">{label ?? s.composer.followLabel}</label>
    <div className="composer-field">
      <textarea id={id} ref={inputRef} rows={variant === 'hero' ? 2 : 1} value={value} maxLength={1000}
        placeholder={placeholder ?? s.composer.followUp} onChange={event => onChange(event.target.value)} onKeyDown={keyDown}
        onFocus={() => onFieldFocus?.(true)} onBlur={() => onFieldFocus?.(false)} />
      <button type="submit" className="btn-primary composer-send" disabled={disabled} aria-label={loading ? s.composer.workingLabel : s.composer.ask}>
        <span className="btn-edge" aria-hidden="true" /><span aria-hidden="true">{loading ? s.composer.working : s.composer.ask}</span><IconArrowUp size={15} />
      </button>
    </div>
    {examples && examples.length > 0 && <div className="composer-examples" role="group" aria-label={examplesLabel ?? s.hero.examples}>
      {examplesLabel && <span className="examples-label" aria-hidden="true">{examplesLabel}</span>}
      {examples.map(example => <button type="button" key={example} className="example-chip" lang="en" onClick={() => (onExample ?? onChange)(example)}
        onMouseEnter={() => onExampleHover?.(example)} onMouseLeave={() => onExampleHover?.(null)}
        onFocus={() => onExampleHover?.(example)} onBlur={() => onExampleHover?.(null)}>{example}</button>)}
    </div>}
    {note}
  </form>
}

/* ---- Honest loading ------------------------------------------------------------------------------ */

export function LoadingState({ question, startedAt }: { question: string; startedAt: number }) {
  const { s } = useStrings()
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => { const t = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(t) }, [])
  const seconds = Math.max(0, Math.floor((now - startedAt) / 1000))
  return <div className="loading" aria-busy="true">
    <QuestionHeading question={question} />
    <div className="loading-instrument" role="status" aria-live="polite">
      <span className="loading-line" aria-hidden="true"><span /></span>
      <p><span>{s.loading.working}</span><span className="loading-time" aria-hidden="true">{seconds}s</span></p>
      <p className="loading-note">{s.loading.note}{seconds > 20 ? s.loading.slow : ''}</p>
    </div>
    <details className="wf-progress"><summary>{s.wf.progress}</summary><WorkflowDiagram workflow={pendingWorkflow()} animate={false} /></details>
    <div className="skeleton" aria-hidden="true"><span className="sk w80" /><span className="sk w60" /><span className="sk block" /></div>
  </div>
}

/* ---- Result ---------------------------------------------------------------------------------------- */

/**
 * One answer layout, adapted to the question: the lead says what changed in plain words,
 * the visual is chosen by the kind of analysis (none for definitions and company reporting),
 * then the key findings and what the reporting cannot tell us.
 */
export function Result({ view, onAsk, onEdit, examples }: { view: ResultView; onAsk: (q: string) => void; onEdit?: (q: string) => void; examples: string[] }) {
  const { s, lang } = useStrings()
  const answered = view.verification.outcome === 'answer'
  const f = view.family
  const prose = f === 'definition' || f === 'document'
  const detailed = !prose && f !== 'fact'
  const [steps, setSteps] = useState(false)
  useEffect(() => { setSteps(false) }, [view])
  return <EvidenceProvider citations={view.citations} factSources={view.factSources}>
    <article className={`result family-${f}`} aria-labelledby="result-question" data-anatomy="answer">
      <ContextHeader view={view} />
      <div id="result-question"><QuestionHeading question={view.question} /></div>
      {answered ? <>
        {f === 'fact' ? <FactAnswer view={view} /> : <DirectAnswer view={view} />}
        {view.partialNote && <p className="partial-note" role="note"><SUPPORT_META.limitation.Glyph size={13} />{view.partialNote}</p>}
        {view.visual && <AnalyticalVisual visual={view.visual} />}
        {f === 'findings' && view.kpis.length > 0 && <KpiStrip kpis={view.kpis} />}
        <Interpretation view={view} />
        <StatusRow view={view} steps={steps} onSteps={() => setSteps(v => !v)} />
        {steps && <AnalysisSteps view={view} />}
        {prose && <Sources view={view} />}
        {detailed && <div className="below">
          <div className="below-main"><Findings view={view} /></div>
          <div className="aside">
            <ManagementReported view={view} />
            {(view.citations.length > 0 || view.contextPassages.length > 0) && <Sources view={view} />}
            {view.summary && <WrittenSummary text={view.summary} kind={view.kind} />}
          </div>
        </div>}
        {lang === 'de' && s.answer.englishOnly && <p className="language-note" role="note">{s.answer.englishOnly}</p>}
        <Inspector view={view} />
      </> : <>
        <Outcome view={view} onAsk={onAsk} onEdit={onEdit} examples={examples} />
        <div className="outcome-steps"><button type="button" className="inspect-button" aria-expanded={steps} aria-controls="analysis-steps" onClick={() => setSteps(v => !v)}>{steps ? s.wf.hideSteps : s.wf.steps}</button></div>
        {steps && <AnalysisSteps view={view} />}
      </>}
    </article>
  </EvidenceProvider>
}
