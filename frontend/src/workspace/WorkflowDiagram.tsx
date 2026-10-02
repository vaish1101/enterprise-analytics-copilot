import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react'
import gsap from 'gsap'
import { useStrings } from '../i18n'
import { EDGES, NODE_ORDER, OUTCOME_NODES, type EdgeId, type NodeId, type Workflow } from '../lib/workflow'

type Box = { l: number; t: number; r: number; b: number; cx: number; cy: number }
type Geometry = { w: number; h: number; box: Record<NodeId, Box> }

const R = 8
/** Right-angled connector with rounded corners: out of `a`, across at `mx`, into `b`. */
function elbow(ax: number, ay: number, bx: number, by: number, mx: number) {
  if (Math.abs(ay - by) < 1) return `M${ax} ${ay}H${bx}`
  const d = by > ay ? 1 : -1
  return `M${ax} ${ay}H${mx - R}Q${mx} ${ay} ${mx} ${ay + d * R}V${by - d * R}Q${mx} ${by} ${mx + R} ${by}H${bx}`
}
/** Bypass rail: leaves the router vertically, runs along the edge of the graph, enters an outcome. */
function rail(from: Box, to: Box, y: number, gap: number) {
  const up = y < from.cy, x0 = from.cx, y0 = up ? from.t : from.b, d = up ? -1 : 1
  const x1 = to.l - gap * 0.32, e = to.cy > y ? 1 : -1
  return `M${x0} ${y0}V${y - d * R}Q${x0} ${y} ${x0 + R} ${y}H${x1 - R}Q${x1} ${y} ${x1} ${y + e * R}V${to.cy - e * R}Q${x1} ${to.cy} ${x1 + R} ${to.cy}H${to.l}`
}

function paths(g: Geometry): Record<EdgeId | 'loop', string> {
  const b = g.box, gap = Math.max(16, b.analytics.l - b.router.r)
  const mid = (a: Box, c: Box) => a.r + (c.l - a.r) / 2
  const loopY = Math.min(b.verifier.t, b.synthesis.t) - 16
  return {
    'router-analytics': elbow(b.router.r, b.router.cy, b.analytics.l, b.analytics.cy, mid(b.router, b.analytics)),
    'router-evidence': elbow(b.router.r, b.router.cy, b.evidence.l, b.evidence.cy, mid(b.router, b.evidence)),
    'analytics-synthesis': elbow(b.analytics.r, b.analytics.cy, b.synthesis.l, b.synthesis.cy, mid(b.analytics, b.synthesis)),
    'evidence-synthesis': elbow(b.evidence.r, b.evidence.cy, b.synthesis.l, b.synthesis.cy, mid(b.evidence, b.synthesis)),
    'synthesis-verifier': elbow(b.synthesis.r, b.synthesis.cy, b.verifier.l, b.verifier.cy, mid(b.synthesis, b.verifier)),
    'verifier-answer': elbow(b.verifier.r, b.verifier.cy, b.answer.l, b.answer.cy, b.verifier.r + gap * 0.36),
    'verifier-limit': elbow(b.verifier.r, b.verifier.cy, b.limit.l, b.limit.cy, b.verifier.r + gap * 0.36),
    'router-clarify': rail(b.router, b.clarify, 9, gap),
    'router-limit': rail(b.router, b.limit, g.h - 9, gap),
    loop: `M${b.verifier.cx} ${b.verifier.t}V${loopY + R}Q${b.verifier.cx} ${loopY} ${b.verifier.cx - R} ${loopY}H${b.synthesis.cx + R}Q${b.synthesis.cx} ${loopY} ${b.synthesis.cx} ${loopY + R}V${b.synthesis.t}`,
  }
}

const EDGE_IDS = Object.keys(EDGES) as EdgeId[]

/**
 * The orchestration as a system map: semantic steps in reading order, SVG connectors drawn
 * from their measured positions, and one restrained pass of motion along the route that
 * ran. On narrow containers the same list reads as a vertical timeline (see system.css).
 *
 * It never invents progress: every state comes from the `Workflow` it is given, and the
 * pass of motion only replays that finished route.
 */
export function WorkflowDiagram({ workflow, defaultTechnical = false, animate = true }: { workflow: Workflow; defaultTechnical?: boolean; animate?: boolean }) {
  const { s, lang } = useStrings()
  const t = s.wf
  const [technical, setTechnical] = useState(defaultTechnical)
  const [selected, setSelected] = useState<NodeId | null>(null)
  const [run, setRun] = useState(0)
  const [geo, setGeo] = useState<Geometry | null>(null)
  const graph = useRef<HTMLDivElement>(null)
  const detailId = useId()
  const reduced = useMemo(() => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false, [])

  const active = useMemo(() => new Set(workflow.steps.flat()), [workflow])
  const traced = workflow.steps.length > 0
  const name = (id: NodeId) => t.node[id][technical ? 1 : 0]
  // An illustration never says a step "ran"; only a route read from a response does.
  const stateText = (id: NodeId) => {
    const state = workflow.nodes[id]
    if (workflow.source === 'overview') return t.stateTypical[state]
    return id === 'answer' && state === 'done' ? t.shown : t.state[state]
  }
  const order = NODE_ORDER.filter(id => workflow.nodes[id] === 'done' || workflow.nodes[id] === 'stopped' || workflow.nodes[id] === 'failed')

  useEffect(() => { setSelected(null) }, [workflow])

  // Connector geometry follows the laid-out nodes, so it stays right at any width, language or theme.
  useLayoutEffect(() => {
    const node = graph.current
    if (!node) return
    const measure = () => {
      const base = node.getBoundingClientRect()
      if (!base.width) return
      const box = {} as Record<NodeId, Box>
      for (const id of NODE_ORDER) {
        const r = node.querySelector<HTMLElement>(`[data-node="${id}"] .wf-node`)?.getBoundingClientRect()
        if (!r) return
        box[id] = { l: r.left - base.left, t: r.top - base.top, r: r.right - base.left, b: r.bottom - base.top, cx: r.left - base.left + r.width / 2, cy: r.top - base.top + r.height / 2 }
      }
      setGeo({ w: base.width, h: base.height, box })
    }
    measure()
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(measure)
    observer.observe(node)
    return () => observer.disconnect()
  }, [technical, lang, workflow])

  const d = useMemo(() => (geo ? paths(geo) : null), [geo])
  const ready = d !== null

  // One pass along the route that ran. Reduced motion, or nothing to replay: final state only.
  useEffect(() => {
    const node = graph.current
    if (!node || !ready || !animate || reduced || !traced) return
    // The timeline layout has no connectors to travel: it shows the finished state directly.
    const lines = node.querySelector('.wf-lines')
    if (!lines || getComputedStyle(lines).display === 'none') return
    const q = <T extends Element>(sel: string) => node.querySelector<T>(sel)
    const nodeEl = (id: NodeId) => q<HTMLElement>(`[data-node="${id}"] .wf-node`)
    const tl = gsap.timeline({ delay: 0.15 })
    const touched: Element[] = []
    const dim = (id: NodeId) => { const el = nodeEl(id); if (el) { touched.push(el); gsap.set(el, { opacity: 0.42 }) } }
    const light = (id: NodeId, at: string | number) => { const el = nodeEl(id); if (el) tl.to(el, { opacity: 1, duration: 0.22, ease: 'power1.out' }, at) }
    const travel = (edge: EdgeId | 'loop', at: string) => {
      const line = q<SVGPathElement>(`[data-on="${edge}"]`), dot = q<SVGCircleElement>(`[data-dot="${edge}"]`)
      if (!line || !dot) return
      const length = line.getTotalLength()
      touched.push(line, dot)
      gsap.set(line, { strokeDasharray: length, strokeDashoffset: length })
      const p = { v: 0 }
      tl.to(line, { strokeDashoffset: 0, duration: 0.5, ease: 'power2.inOut' }, at)
      tl.to(p, { v: 1, duration: 0.5, ease: 'power2.inOut',
        onStart: () => { dot.style.opacity = '1' },
        onUpdate: () => { const pt = line.getPointAtLength(p.v * length); dot.setAttribute('cx', String(pt.x)); dot.setAttribute('cy', String(pt.y)) },
        onComplete: () => { dot.style.opacity = '0' } }, at)
    }
    for (const id of order) if (id !== 'router') dim(id)
    workflow.steps.forEach((edges, i) => {
      const label = `s${i}`
      tl.addLabel(label, i === 0 ? 0.1 : '>-0.05')
      edges.forEach(edge => travel(edge, label))
      edges.forEach(edge => light(EDGES[edge][1], `${label}+=0.42`))
      // The one real loop: the verifier returns the draft, synthesis revises, the verifier checks again.
      if (edges[0] === 'synthesis-verifier' && workflow.revised) { tl.addLabel(`${label}r`, '>'); travel('loop', `${label}r`) }
    })
    return () => { tl.kill(); gsap.set(touched, { clearProps: 'opacity,strokeDasharray,strokeDashoffset' }) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workflow, run, ready, animate, reduced, technical])

  const details = selected ? workflow.details[selected] : undefined
  return <div className={`wf source-${workflow.source} ${traced ? 'is-traced' : ''}`}>
    <div className="wf-head">
      <p className="wf-source"><span className="wf-chip">{t.source[workflow.source]}</span><span>{t.sourceNote[workflow.source]}</span></p>
      <div className="wf-tools">
        <button type="button" className="wf-toggle" aria-pressed={technical} onClick={() => setTechnical(v => !v)}>{t.names}</button>
        {traced && animate && !reduced && <button type="button" className="wf-toggle" onClick={() => setRun(v => v + 1)}>{t.replay}</button>}
      </div>
    </div>
    {traced && <p className="sr-only">{t.routeText(order.map(name).join(', '))}</p>}
    <div className="wf-graph" ref={graph}>
      {d && geo && <svg className="wf-lines" width={geo.w} height={geo.h} viewBox={`0 0 ${geo.w} ${geo.h}`} aria-hidden="true">
        {EDGE_IDS.map(edge => <path key={edge} className={`wf-edge ${traced && !active.has(edge) ? 'is-off' : ''}`} d={d[edge]} />)}
        {(workflow.revised || !traced) && <path className={`wf-edge wf-loop ${workflow.revised ? '' : 'is-rule'}`} d={d.loop} />}
        {EDGE_IDS.filter(edge => active.has(edge)).map(edge => <path key={edge} className={`wf-edge is-on ${EDGES[edge][1] === 'clarify' || EDGES[edge][1] === 'limit' ? 'is-stop' : ''}`} data-on={edge} d={d[edge]} />)}
        {workflow.revised && <path className="wf-edge is-on wf-loop" data-on="loop" d={d.loop} />}
        {[...EDGE_IDS.filter(edge => active.has(edge)), ...(workflow.revised ? ['loop'] : [])].map(edge => <circle key={edge} className="wf-dot" data-dot={edge} r="3.5" />)}
        {(workflow.revised || !traced) && <text className="wf-loop-label" x={(geo.box.synthesis.cx + geo.box.verifier.cx) / 2} y={Math.min(geo.box.verifier.t, geo.box.synthesis.t) - 22} textAnchor="middle">{workflow.revised ? t.revision : t.revisionRule}</text>}
      </svg>}
      <ol className="wf-nodes" aria-label={t.diagram}>
        {NODE_ORDER.map(id => {
          const state = workflow.nodes[id]
          return <li key={id} data-node={id} data-state={state} className={OUTCOME_NODES.includes(id) ? 'is-outcome' : ''}>
            <button type="button" className="wf-node" aria-pressed={selected === id} aria-controls={detailId} onClick={() => setSelected(v => (v === id ? null : id))}>
              <span className="wf-name">{name(id)}</span>
              <span className="wf-kind">{technical && t.kind[id] ? t.kind[id] : t.desc[id]}</span>
              {workflow.meta[id] && <span className="wf-meta">{workflow.meta[id]}</span>}
              {stateText(id) && <span className="wf-state">{stateText(id)}</span>}
            </button>
          </li>
        })}
      </ol>
      {workflow.revised && <p className="wf-revision-note">{t.revision}</p>}
    </div>
    <div id={detailId} className="wf-detail" role="region" aria-live="polite" aria-label={selected ? name(selected) : t.select}>
      {selected ? <div className="wf-inspect" data-node={selected}>
        <div className="wf-inspect-head">
          <p className="wf-detail-head">{t.selected}</p>
          <h5>{t.node[selected][0]}<span>{t.node[selected][1]}{t.kind[selected] ? ` · ${t.kind[selected]}` : ''}</span></h5>
        </div>
        <dl className="wf-io">
          <div><dt>{t.usesLabel}</dt><dd>{t.io[selected][0]}</dd></div>
          <div><dt>{t.producesLabel}</dt><dd>{t.io[selected][1]}</dd></div>
        </dl>
        {details && details.length > 0 && <div className="wf-used"><p className="wf-detail-head">{t.used}</p>
          <dl>{details.map((item, i) => <div key={`${item.label}-${i}`}><dt>{item.label}</dt><dd>{item.value}</dd></div>)}</dl></div>}
      </div> : <p className="wf-hint"><span className="wf-hint-mark" aria-hidden="true" />{t.empty}</p>}
    </div>
    {technical && <p className="wf-legend">{t.legend}</p>}
  </div>
}
