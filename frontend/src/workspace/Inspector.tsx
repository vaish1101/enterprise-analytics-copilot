import { useStrings } from '../i18n'
import { formatValue, unitName } from '../lib/format'
import { provenanceLabel, type CitationView, type FindingView, type ResultView } from '../lib/viewModel'
import { Sheet } from '../shell/Sheet'
import type { FactSource } from '../types'
import { useEvidence } from './evidenceContext'
import { ExecutionPath } from './ExecutionPath'
import { GlyphCalculation, GlyphDocument, GlyphFact, IconArrowRight, IconExternal, SUPPORT_META, VerificationMark } from './glyphs'
import { useEvidenceType } from './Workspace'

const pad = (n: number) => String(n).padStart(2, '0')

function FactSourceLine({ source }: { source: FactSource }) {
  const { s } = useStrings()
  return <p className="source-line"><a href={source.official_url} target="_blank" rel="noreferrer">{source.source_title}<IconExternal size={12} /><span className="sr-only">{s.inspector.opens}</span></a>
    <span>{source.location} · {source.page_or_sheet}{source.cell_or_range ? ` · ${source.cell_or_range}` : ''}</span></p>
}

function FindingLinks({ findings }: { findings: FindingView[] }) {
  const { s } = useStrings()
  const { navigate } = useEvidence()
  if (!findings.length) return null
  return <div className="support-block"><h5>{s.inspector.supports}</h5>
    <ul className="link-list">{findings.map(f => <li key={f.id}>
      <button type="button" className="link-row" onClick={() => navigate({ kind: 'finding', id: f.id })}>
        <span className="link-index">{pad(f.index)}</span><span className="link-text">{f.text}</span><IconArrowRight size={13} />
      </button></li>)}</ul>
  </div>
}

function PassageRow({ passage, view, focus }: { passage: CitationView; view: ResultView; focus: boolean }) {
  const { s } = useStrings()
  const evidenceType = useEvidenceType()
  const { activeCitation, setActiveCitation, navigate } = useEvidence()
  const cited = passage.index > 0
  const findings = view.findings.filter(f => f.citationIndexes.includes(passage.index))
  return <li data-citation={cited ? passage.index : undefined} className={`source doc ${focus || (cited && activeCitation === passage.index) ? 'is-focus' : ''}`}
    onMouseEnter={() => cited && setActiveCitation(passage.index)} onMouseLeave={() => cited && setActiveCitation(null)}>
    {cited ? <span className="cite-marker static" aria-hidden="true">{passage.index}</span> : <span className="context-mark" aria-hidden="true" />}
    <div>
      <a href={passage.official_url} target="_blank" rel="noreferrer">{passage.source_title}<IconExternal size={13} /><span className="sr-only">{s.inspector.opens}</span></a>
      <p>{s.answer.page(String(passage.page_number))}{passage.section ? ` · ${passage.section}` : ''} · {evidenceType(passage.evidence_type)}</p>
      {findings.length > 0 && <p className="relation">{s.inspector.supports} {findings.map((f, i) => <span key={f.id}>{i > 0 && ', '}
        <button type="button" className="inline-link" onClick={() => navigate({ kind: 'finding', id: f.id })}>{s.inspector.supportsFinding(pad(f.index))}</button></span>)}</p>}
    </div>
  </li>
}

function Selected({ view }: { view: ResultView }) {
  const { s, lang } = useStrings()
  const i = s.inspector
  const { inspector, factSources, citations, navigate } = useEvidence()
  if (inspector?.kind === 'figure') {
    const fact = view.facts[inspector.factId]
    const source = factSources[inspector.factId]
    const findings = view.findings.filter(f => f.factIds.includes(inspector.factId))
    const management = fact?.provenance === 'MANAGEMENT_ATTRIBUTED'
    return <section className="inspector-section selected" data-focus aria-label={i.selectedFigure}>
      <p className="selected-kicker">{i.selectedFigure}</p>
      {fact ? <>
        <p className="selected-value">{formatValue(fact.value, fact.unit, management)}</p>
        <p className="selected-label">{fact.label}</p>
        <dl className="selected-meta">
          {fact.scope && <><dt>{i.scope}</dt><dd>{fact.scope}</dd></>}
          <dt>{i.period}</dt><dd>{fact.period}</dd>
          <dt>{i.unit}</dt><dd>{unitName(fact.unit)}</dd>
          <dt>{i.type}</dt><dd>{provenanceLabel(fact.provenance, lang)}</dd>
        </dl>
      </> : <p className="inspector-lede">{i.notReleased}</p>}
      {source && <div className="support-block"><h5><GlyphFact size={13} /> {i.published}</h5><FactSourceLine source={source} /></div>}
      <FindingLinks findings={findings} />
      {management && <p className="caveat"><SUPPORT_META.management.Glyph size={13} />{i.attribution}</p>}
    </section>
  }
  if (inspector?.kind === 'calculation') {
    const calc = view.calculations.find(c => c.key === inspector.key)
    if (!calc) return null
    return <section className="inspector-section selected" data-focus aria-label={i.calculated}>
      <p className="selected-kicker">{i.calculated}</p>
      <p className="selected-value">{formatValue(calc.calculated, calc.unit, !calc.expected)}</p>
      <p className="selected-label">{calc.title}</p>
      <dl className="selected-meta">
        <dt>{i.method}</dt><dd>{calc.expression}</dd>
        <dt>{i.exact}</dt><dd className="num">{calc.calculated} {unitName(calc.unit)}</dd>
        {calc.expected && <><dt>{i.reportedTotal}</dt><dd>{formatValue(calc.expected, calc.unit)} · {calc.passed ? i.reconciles(calc.tolerance ?? '') : i.notReconciles}</dd></>}
      </dl>
      <div className="support-block"><h5><GlyphCalculation size={13} /> {i.inputs}</h5>
        <ul className="link-list">{calc.inputs.filter(id => view.facts[id]).map(id => {
          const fact = view.facts[id]
          return <li key={id}><button type="button" className="link-row" onClick={() => navigate({ kind: 'figure', factId: id })}>
            <span className="link-text">{fact.label} · {fact.period}</span><span className="num">{formatValue(fact.value, fact.unit, fact.provenance === 'MANAGEMENT_ATTRIBUTED')}</span><IconArrowRight size={13} />
          </button></li>
        })}</ul>
      </div>
      <p className="inspector-lede">{i.calcNote}</p>
    </section>
  }
  if (inspector?.kind === 'finding') {
    const finding = view.findings.find(f => f.id === inspector.id)
    if (!finding) return null
    const sources = finding.factIds.map(id => factSources[id]).filter((x): x is FactSource => !!x)
    const passages = citations.filter(c => finding.citationIndexes.includes(c.index))
    return <section className="inspector-section selected" data-focus aria-label={i.finding(pad(finding.index))}>
      <p className="selected-kicker">{i.finding(pad(finding.index))}</p>
      <p className="selected-statement">{finding.text}</p>
      <dl className="selected-meta">
        {finding.company && <><dt>{i.company}</dt><dd>{finding.company}</dd></>}
        {finding.scope && <><dt>{i.scope}</dt><dd>{finding.scope}</dd></>}
        {finding.periods.length > 0 && <><dt>{i.period}</dt><dd>{finding.periods.join(', ')}</dd></>}
        {finding.value && finding.unit && <><dt>{i.value}</dt><dd>{formatValue(finding.value, finding.unit, finding.provenance === 'MANAGEMENT_ATTRIBUTED')}</dd></>}
        <dt>{i.type}</dt><dd>{provenanceLabel(finding.provenance, lang)}</dd>
      </dl>
      <div className="support-block"><h5>{i.checkedAgainst}</h5>
        <ul className="support-kinds">{finding.support.map(kind => { const M = SUPPORT_META[kind]; return <li key={kind}><M.Glyph size={13} />{s.support[kind][0]}</li> })}</ul>
      </div>
      {finding.factIds.length > 0 && <div className="support-block"><h5><GlyphFact size={13} /> {i.figureSource}</h5>
        {finding.factIds.filter(id => view.facts[id]).map(id => <button key={id} type="button" className="link-row" onClick={() => navigate({ kind: 'figure', factId: id })}>
          <span className="link-text">{view.facts[id].label} · {view.facts[id].period}</span><IconArrowRight size={13} /></button>)}
        {sources.map(x => <FactSourceLine key={x.fact_id} source={x} />)}
      </div>}
      {passages.length > 0 && <div className="support-block"><h5><GlyphDocument size={13} /> {i.citedSources}</h5>
        {passages.map(p => <button key={p.evidence_unit_id} type="button" className="link-row" onClick={() => navigate({ kind: 'citation', index: p.index })}>
          <span className="cite-marker static">{p.index}</span><span className="link-text">{p.source_title} · {s.answer.page(String(p.page_number))}</span><IconArrowRight size={13} /></button>)}
      </div>}
      {finding.provenance === 'MANAGEMENT_ATTRIBUTED' && <p className="caveat"><SUPPORT_META.management.Glyph size={13} />{i.attribution}</p>}
    </section>
  }
  return null
}

export function Inspector({ view }: { view: ResultView }) {
  const { s } = useStrings()
  const i = s.inspector
  const { inspector, closeInspector, citations, factSources, returnFocus, back } = useEvidence()
  const focusIndex = inspector?.kind === 'citation' ? inspector.index : null
  const figureIds = Object.keys(factSources).map(Number)
  const v = view.verification
  const focusSelector = inspector?.kind === 'citation' ? `[data-citation="${inspector.index}"]`
    : inspector?.kind === 'figure' || inspector?.kind === 'finding' || inspector?.kind === 'calculation' ? '[data-focus]'
    : inspector?.kind === 'execution' ? '[data-execution]' : undefined

  return <Sheet open={inspector !== null} onClose={closeInspector} title={i.title} returnFocus={returnFocus} focusSelector={focusSelector} focusKey={JSON.stringify(inspector)}
    lead={back ? <button type="button" className="text-button sheet-back" onClick={back}>{i.back}</button> : null}>
    <p className={`inspector-note kind-${view.kind}`}>{view.kind === 'test' ? '' : `${view.kindLabel}. `}{view.kindNote}</p>
    <Selected view={view} />

    <section className="inspector-section">
      <h4>{i.checks}</h4>
      <div className={`inspector-verification tone-${v.tone}`}>
        <VerificationMark state={v.state} released={v.released} checked={v.checked || v.released} size={22} />
        <div><strong>{view.lead.located ? s.x.locatedStatus(citations.length) : v.title}</strong><p>{view.lead.located ? s.x.located[1] : `${v.line}${v.revised ? ` ${s.status.revised}` : ''}`}</p></div>
      </div>
      <h5 className="what-checked-title">{s.x.whatChecked}</h5>
      <p className="what-checked">{s.x.whatCheckedText}</p>
    </section>

    {citations.length > 0 && <section className="inspector-section">
      <h4><GlyphDocument size={14} /> {i.sources} <span>{citations.length}</span></h4>
      <ol className="source-list">{citations.map(c => <PassageRow key={c.evidence_unit_id} passage={c} view={view} focus={focusIndex === c.index} />)}</ol>
    </section>}

    {view.contextPassages.length > 0 && <section className="inspector-section">
      <h4>{i.alsoRead} <span>{view.contextPassages.length}</span></h4>
      <p className="inspector-lede">{i.alsoReadNote}</p>
      <ol className="source-list">{view.contextPassages.map(c => <PassageRow key={c.evidence_unit_id} passage={c} view={view} focus={false} />)}</ol>
    </section>}
    {(citations.length > 0 || view.contextPassages.length > 0) && <p className="inspector-lede rights">{i.rights}</p>}

    {figureIds.length > 0 && <section className="inspector-section">
      <h4><GlyphFact size={14} /> {i.figures} <span>{figureIds.length}</span></h4>
      <p className="inspector-lede">{i.figuresNote}</p>
      <ol className="source-list">{figureIds.map(id => {
        const fact = view.facts[id]
        return <li key={id} className={`source fact ${inspector?.kind === 'figure' && inspector.factId === id ? 'is-focus' : ''}`}>
          <span className="fact-glyph" aria-hidden="true"><GlyphFact size={14} /></span>
          <div>
            {fact && <p className="fact-line"><strong>{fact.label}</strong><span>{fact.period}</span><span className="num">{formatValue(fact.value, fact.unit, fact.provenance === 'MANAGEMENT_ATTRIBUTED')}</span></p>}
            <FactSourceLine source={factSources[id]} />
          </div>
        </li>
      })}</ol>
    </section>}

    {view.calculations.length > 0 && <section className="inspector-section">
      <h4><GlyphCalculation size={14} /> {i.calculations}</h4>
      {view.calculations.map(calc => <div key={calc.key} className={`calc ${calc.passed === false ? 'is-failed' : ''}`}>
        <p className="calc-title">{calc.title}</p>
        <p className="calc-expr">{calc.expression}</p>
        <p className="calc-result num">{calc.expected
          ? <>{i.calcReported(formatValue(calc.calculated, calc.unit), formatValue(calc.expected, calc.unit))} · {calc.passed ? i.reconciles(calc.tolerance ?? '') : i.notReconciles}</>
          : <>{i.result} {formatValue(calc.calculated, calc.unit, true)}</>}</p>
      </div>)}
    </section>}

    <section className="inspector-section">
      <h4 data-execution>{i.how}</h4>
      {view.execution ? <>
        <p className="inspector-lede">{i.howNote}</p>
        <ExecutionPath execution={view.execution} />
      </> : <p className="inspector-lede">{i.noLog}</p>}
      <details className="trace"><summary>{i.technical}</summary>
        {view.trace && view.trace.length > 0 && <><p className="trace-head">{i.timings}</p>
          <ol>{view.trace.map(stage => <li key={`${stage.order}-${stage.label}`} className={`stage-${stage.status}`}><span>{stage.label}</span><span className="num">{stage.duration_ms != null ? `${stage.duration_ms.toFixed(0)} ms` : ''}</span></li>)}</ol></>}
        {view.calculations.length > 0 && <><p className="trace-head">{i.run}</p>
          <ol>{view.calculations.map(c => <li key={c.key}><span>{c.title}</span><span className="num">{c.runId.slice(0, 18)}</span></li>)}</ol></>}
        {v.issues.length > 0 && <><p className="trace-head">{i.codes}</p><ul className="issue-list">{v.issues.map(issue => <li key={issue}>{issue}</li>)}</ul></>}
      </details>
    </section>
  </Sheet>
}
