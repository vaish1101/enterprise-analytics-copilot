import { useId, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { formatValue, isNegative, magnitude, spokenValue, unitName } from '../lib/format'
import type { BarView, VisualView } from '../lib/viewModel'
import type { FactSource } from '../types'
import { GlyphCalculation, GlyphManagement, IconBars, IconTable } from './glyphs'
import { useEvidence } from './evidenceContext'
import { useStrings } from '../i18n'

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T | null>(null)
  const [width, setWidth] = useState(0)
  useLayoutEffect(() => {
    const node = ref.current
    if (!node) return
    const update = () => setWidth(Math.round(node.getBoundingClientRect().width))
    update()
    const observer = new ResizeObserver(update)
    observer.observe(node)
    return () => observer.disconnect()
  }, [])
  return [ref, width] as const
}

type Tone = 'endpoint' | 'up' | 'down'
const tone = (bar: BarView, endpoint = false): Tone => endpoint ? 'endpoint' : isNegative(bar.value) ? 'down' : 'up'

function BarTip({ bar, source, extra }: { bar: BarView; source?: FactSource; extra?: string }) {
  const { s } = useStrings()
  return <div className="bar-tip" role="tooltip">
    <strong>{bar.label}</strong>
    <span className="bar-tip-value">{formatValue(bar.value, bar.unit, bar.provenance === 'MANAGEMENT_ATTRIBUTED')}</span>
    {extra && <span className="bar-tip-meta">{extra}</span>}
    {bar.provenance === 'MANAGEMENT_ATTRIBUTED' && <span className="bar-tip-meta amber"><GlyphManagement size={12} /> {s.chart.management}</span>}
    {source && <span className="bar-tip-source">{source.source_title} · {source.location} · {source.page_or_sheet}</span>}
  </div>
}

/* ---- Bridge (waterfall) ---------------------------------------------------------- */

function BridgeChart({ visual, height }: { visual: Extract<VisualView, { kind: 'bridge' }>; height: number }) {
  const { s } = useStrings()
  const [wrap, width] = useWidth<HTMLDivElement>()
  const { factSources, openInspector } = useEvidence()
  const [active, setActive] = useState<string | null>(null)
  const columns: { bar: BarView; kind: Tone; from: number; to: number; caption: string }[] = []
  let running = magnitude(visual.start.value)
  columns.push({ bar: visual.start, kind: 'endpoint', from: 0, to: running, caption: visual.startLabel })
  for (const component of visual.components) {
    const next = running + magnitude(component.value)
    columns.push({ bar: component, kind: tone(component), from: running, to: next, caption: '' })
    running = next
  }
  columns.push({ bar: visual.end, kind: 'endpoint', from: 0, to: magnitude(visual.end.value), caption: visual.endLabel })

  const top = 30, bottom = 8
  const max = Math.max(...columns.map(c => Math.max(c.from, c.to))) * 1.06
  const min = Math.min(0, ...columns.map(c => Math.min(c.from, c.to)))
  const plot = height - top - bottom
  const y = (v: number) => top + (max - v) / (max - min) * plot
  const n = columns.length
  const pitch = width / n
  const barWidth = Math.max(10, Math.min(46, pitch * 0.46))

  if (width > 0 && width < 600) {
    // Narrow screens: the same governed geometry, laid out as a horizontal waterfall.
    const hmax = Math.max(...columns.map(c => Math.max(c.from, c.to))) * 1.04
    const at = (v: number) => `${(Math.max(0, v) / hmax) * 100}%`
    return <div className="chart bridge-h" ref={wrap}>
      <ul>{columns.map(column => <li key={column.bar.key} className={`bh tone-${column.kind}`} tabIndex={0} role="button"
        onClick={event => openInspector({ kind: 'figure', factId: column.bar.factId }, event.currentTarget)}
        onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); openInspector({ kind: 'figure', factId: column.bar.factId }, event.currentTarget) } }}
        aria-label={`${column.bar.label}${column.caption ? `, ${column.caption}` : ''}: ${spokenValue(column.bar.value, column.bar.unit)}`}>
        <span className="bh-label">{column.bar.label}{column.caption && <em>{column.caption}</em>}</span>
        <span className="bh-track"><span data-bar={column.bar.key} className="bh-bar"
          style={{ left: at(Math.min(column.from, column.to)), width: `max(2px, calc(${at(Math.max(column.from, column.to))} - ${at(Math.min(column.from, column.to))}))` }} /></span>
        <span className="bh-value">{formatValue(column.bar.value, null, column.kind !== 'endpoint')}</span>
      </li>)}</ul>
    </div>
  }

  return <div className="chart bridge" ref={wrap}>
    {width > 0 && <svg className="chart-svg" width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img"
      aria-label={s.chart.waterfall(visual.startLabel, visual.endLabel, unitName(visual.unit))}>
      <defs>
        <linearGradient id="bar-up" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="var(--c-up)" stopOpacity=".92" /><stop offset="1" stopColor="var(--c-up)" stopOpacity=".92" /></linearGradient>
        <linearGradient id="bar-down" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="var(--c-down)" stopOpacity=".92" /><stop offset="1" stopColor="var(--c-down)" stopOpacity=".92" /></linearGradient>
        <linearGradient id="bar-end" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="var(--c-end)" stopOpacity=".85" /><stop offset="1" stopColor="var(--c-end)" stopOpacity=".85" /></linearGradient>
      </defs>
      <line className="axis" x1={0} x2={width} y1={y(0)} y2={y(0)} />
      {columns.map((column, i) => {
        const cx = pitch * i + pitch / 2
        const y1 = y(Math.max(column.from, column.to))
        const y2 = y(Math.min(column.from, column.to))
        const h = Math.max(1.5, y2 - y1)
        const next = columns[i + 1]
        const isActive = active === column.bar.key
        const signed = column.kind !== 'endpoint'
        const labelY = column.kind === 'down' ? y2 + 15 : y1 - 9
        return <g key={column.bar.key} className={`bar-col tone-${column.kind} ${isActive ? 'is-active' : ''} ${active && !isActive ? 'is-dim' : ''}`}>
          {next && <line className="connector" x1={cx + barWidth / 2} x2={pitch * (i + 1) + pitch / 2 - barWidth / 2} y1={y(column.to)} y2={y(column.to)} />}
          <rect data-bar={column.bar.key} className="bar" x={cx - barWidth / 2} y={y1} width={barWidth} height={h} rx={2}
            fill={`url(#bar-${column.kind === 'endpoint' ? 'end' : column.kind})`} />
          <line className="bar-edge" x1={cx - barWidth / 2 + 1} x2={cx + barWidth / 2 - 1} y1={column.kind === 'down' ? y2 : y1} y2={column.kind === 'down' ? y2 : y1} />
          <text className="bar-value" x={cx} y={labelY} textAnchor="middle">{formatValue(column.bar.value, null, signed)}</text>
          <rect className="bar-hit" x={pitch * i} y={top - 20} width={pitch} height={plot + 20} tabIndex={0}
            aria-label={`${column.bar.label}${column.caption ? `, ${column.caption}` : ''}: ${spokenValue(column.bar.value, column.bar.unit)}${column.bar.provenance === 'MANAGEMENT_ATTRIBUTED' ? s.chart.managementSpoken : ''}`}
            role="button" onMouseEnter={() => setActive(column.bar.key)} onMouseLeave={() => setActive(null)}
            onFocus={() => setActive(column.bar.key)} onBlur={() => setActive(null)}
            onClick={event => openInspector({ kind: 'figure', factId: column.bar.factId }, event.currentTarget as unknown as HTMLElement)}
            onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); openInspector({ kind: 'figure', factId: column.bar.factId }, event.currentTarget as unknown as HTMLElement) } }} />
        </g>
      })}
    </svg>}
    <div className="bridge-labels" aria-hidden="true">
      {columns.map(column => <span key={column.bar.key} className={`bl tone-${column.kind} ${active === column.bar.key ? 'is-active' : ''}`}>
        <b>{column.bar.label}</b>{column.caption && <em>{column.caption}</em>}
      </span>)}
    </div>
    {/* Hover or focus detail sits in its own line inside the chart; it never covers other content. */}
    <p className="bar-detail" aria-hidden="true">{(() => {
      const column = columns.find(c => c.bar.key === active)
      if (!column) return <span className="bar-detail-hint">{s.x.unit(unitName(visual.unit))}</span>
      const source = factSources[column.bar.factId]
      return <><strong>{column.bar.label}</strong><span className="num">{formatValue(column.bar.value, column.bar.unit, column.kind !== 'endpoint')}</span>
        <span>{column.caption || visual.periodLabel}</span>{source && <span className="bar-detail-source">{source.source_title} · {source.page_or_sheet}</span>}</>
    })()}</p>
  </div>
}

/* ---- Signed horizontal bars (decomposition / ranking) ----------------------------- */

function HorizontalBars({ bars, unit, footer }: { bars: (BarView & { rank?: number })[]; unit: string; footer?: ReactNode }) {
  const { s } = useStrings()
  const { factSources, openInspector } = useEvidence()
  const [active, setActive] = useState<string | null>(null)
  const extent = Math.max(...bars.map(b => Math.abs(magnitude(b.value))), 1)
  const hasNegative = bars.some(b => isNegative(b.value))
  return <div className="chart hbars">
    <ul className="hbar-list">
      {bars.map(bar => {
        const share = Math.abs(magnitude(bar.value)) / extent
        const negative = isNegative(bar.value)
        const signed = bar.provenance === 'MANAGEMENT_ATTRIBUTED' || hasNegative
        return <li key={bar.key} className={`hbar ${negative ? 'tone-down' : 'tone-up'} ${active === bar.key ? 'is-active' : ''}`}
          tabIndex={0} role="button" onClick={event => openInspector({ kind: 'figure', factId: bar.factId }, event.currentTarget)}
          onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); openInspector({ kind: 'figure', factId: bar.factId }, event.currentTarget) } }}
          onMouseEnter={() => setActive(bar.key)} onMouseLeave={() => setActive(null)} onFocus={() => setActive(bar.key)} onBlur={() => setActive(null)}
          aria-label={`${bar.rank ? s.chart.rank(bar.rank) : ''}${bar.label}: ${spokenValue(bar.value, bar.unit)}`}>
          <span className="hbar-label">{bar.rank ? <i>{bar.rank}</i> : null}{bar.label}</span>
          <span className={`hbar-track ${hasNegative ? 'two-sided' : ''}`}>
            <span data-bar={bar.key} className="hbar-fill" style={{ '--share': share } as CSSProperties} />
          </span>
          <span className="hbar-value">{formatValue(bar.value, unit, signed)}</span>
        </li>
      })}
    </ul>
    {footer}
  </div>
}

function ComparisonChart({ visual }: { visual: Extract<VisualView, { kind: 'comparison' }> }) {
  const { s } = useStrings()
  const { openInspector } = useEvidence()
  // One shared zero baseline: positive values rise from it, negative values hang below it.
  const values = visual.bars.map(b => magnitude(b.value))
  const up = Math.max(0, ...values), down = Math.max(0, ...values.map(v => -v))
  const span = up + down || 1
  const zero = up / span
  return <div className="chart comparison">
    <div className="cmp-plot" style={{ '--zero': zero } as CSSProperties}>
      <span className="cmp-zero" aria-hidden="true" />
      {visual.bars.map((bar, i) => {
        const v = values[i]
        const top = v >= 0 ? zero - v / span : zero
        return <button type="button" key={bar.key} className={`cmp-col ${i === visual.bars.length - 1 ? 'is-current' : ''} ${v < 0 ? 'is-negative' : ''}`}
          onClick={event => openInspector({ kind: 'figure', factId: bar.factId }, event.currentTarget)}
          aria-label={`${bar.label}: ${spokenValue(bar.value, bar.unit)}. ${s.chart.inspect}`}>
          <span className="cmp-track"><span data-bar={bar.key} className="cmp-fill" style={{ '--top': top, '--h': Math.max(Math.abs(v) / span, 0.004) } as CSSProperties} /></span>
          <span className="cmp-value">{formatValue(bar.value, bar.unit)}</span>
          <span className="cmp-label">{bar.label}</span>
        </button>
      })}
    </div>
    {visual.change && <div className="cmp-change"><GlyphCalculation size={14} /><span>{s.chart.change}</span><strong>{formatValue(visual.change.value, visual.change.unit, true)}</strong></div>}
  </div>
}

/* ---- Accessible table alternative --------------------------------------------------- */

function rowsFor(visual: VisualView, management: string): { label: string; period?: string; value: string; unit: string; note?: string }[] {
  switch (visual.kind) {
    case 'bridge': return [
      { label: visual.start.label, period: visual.startLabel, value: visual.start.value, unit: visual.unit },
      ...visual.components.map(c => ({ label: c.label, period: visual.periodLabel, value: c.value, unit: visual.unit, note: management })),
      { label: visual.end.label, period: visual.endLabel, value: visual.end.value, unit: visual.unit },
    ]
    case 'decomposition': return [
      ...visual.components.map(c => ({ label: c.label, period: visual.periodLabel, value: c.value, unit: visual.unit, note: c.provenance === 'MANAGEMENT_ATTRIBUTED' ? management : undefined })),
      { label: visual.total.label, period: visual.periodLabel, value: visual.total.value, unit: visual.unit },
    ]
    case 'ranking': return visual.bars.map(b => ({ label: `${b.rank}. ${b.label}`, period: visual.periodLabel, value: b.value, unit: visual.unit }))
    case 'comparison': return visual.bars.map(b => ({ label: visual.metricLabel, period: b.label, value: b.value, unit: visual.unit }))
  }
}

function DataTable({ visual, caption }: { visual: VisualView; caption: string }) {
  const { s } = useStrings()
  return <table className="data-table">
    <caption>{caption}</caption>
    <thead><tr><th scope="col">{s.chart.item}</th><th scope="col">{s.chart.period}</th><th scope="col" className="num">{s.chart.value(unitName(visual.unit))}</th><th scope="col">{s.chart.note}</th></tr></thead>
    <tbody>{rowsFor(visual, s.chart.management).map((row, i) => <tr key={i}><th scope="row">{row.label}</th><td>{row.period}</td><td className="num">{formatValue(row.value, null, visual.kind !== 'comparison' && !!row.note)}</td><td>{row.note}</td></tr>)}</tbody>
  </table>
}

/* ---- Frame ------------------------------------------------------------------------ */

function useTitle() {
  const { s } = useStrings()
  return (visual: VisualView): string => {
    switch (visual.kind) {
      case 'bridge': return s.chart.bridge(visual.start.label)
      case 'decomposition': return s.chart.breakdown(visual.total.label)
      case 'ranking': return s.chart.ranked
      case 'comparison': return visual.metricLabel
    }
  }
}

export function AnalyticalVisual({ visual }: { visual: VisualView }) {
  const { s } = useStrings()
  const title = useTitle()
  const [asTable, setAsTable] = useState(false)
  const headingId = useId()
  const management = visual.kind === 'bridge' || (visual.kind === 'decomposition' && visual.components.some(c => c.provenance === 'MANAGEMENT_ATTRIBUTED'))
    || (visual.kind === 'ranking' && visual.bars.some(b => b.provenance === 'MANAGEMENT_ATTRIBUTED'))
  const period = visual.kind === 'comparison' ? visual.bars.map(b => b.label).join(' → ') : visual.kind === 'bridge' ? `${visual.startLabel} → ${visual.endLabel}` : visual.periodLabel
  return <figure className="visual" data-anatomy="visual" aria-labelledby={headingId}>
    <figcaption className="visual-head">
      <div className="visual-title">
        <span className="eyebrow">{s.chart.eyebrow}</span>
        <h3 id={headingId}>{title(visual)} <span className="visual-period">{period}</span></h3>
      </div>
      <div className="visual-meta">
        {management && <span className="meta-tag amber"><GlyphManagement size={13} /> {s.chart.management}</span>}
        {visual.kind === 'bridge' && visual.reconciled && <span className="meta-tag"><GlyphCalculation size={13} /> {s.chart.addsUp(formatValue(visual.end.value, visual.unit))}</span>}
        {visual.kind === 'decomposition' && visual.reconciliation && <span className={`meta-tag ${visual.reconciliation.passed ? '' : 'warm'}`}><GlyphCalculation size={13} /> {visual.reconciliation.passed ? s.chart.addsUpWithin(visual.reconciliation.tolerance) : s.chart.notAddUp(visual.reconciliation.tolerance)}</span>}
        <button type="button" className="icon-toggle" aria-pressed={asTable} onClick={() => setAsTable(v => !v)}
          aria-label={asTable ? s.chart.chart : s.chart.table} title={asTable ? s.chart.chart : s.chart.table}>
          {asTable ? <IconBars /> : <IconTable />}
        </button>
      </div>
    </figcaption>
    {asTable ? <DataTable visual={visual} caption={s.chart.caption(title(visual), period, unitName(visual.unit))} />
      : visual.kind === 'bridge' ? <BridgeChart visual={visual} height={window.innerHeight < 820 ? 164 : window.innerHeight < 940 ? 184 : 204} />
      : visual.kind === 'comparison' ? <ComparisonChart visual={visual} />
      : visual.kind === 'ranking' ? <HorizontalBars bars={visual.bars} unit={visual.unit} />
      : <HorizontalBars bars={visual.components} unit={visual.unit} footer={<div className="hbar-total"><span>{visual.total.label}</span><strong>{formatValue(visual.total.value, visual.unit)}</strong></div>} />}
  </figure>
}
