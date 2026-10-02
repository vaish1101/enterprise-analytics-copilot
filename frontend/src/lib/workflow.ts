import { strings, type Lang } from '../i18n/strings'
import type { QueryResponse } from '../types'
import type { VerificationView } from './verification'

/*
 * The orchestration as the backend actually wires it (src/orchestration/graph.py):
 *
 *   plan → route ─┬─ analytics ─┐
 *                 ├─ knowledge ─┼─ assemble → synthesize → verify ─┬─ finalize (answer)
 *                 └─ both ──────┘              ▲                   ├─ revise (at most once) → verify
 *                 └─ short_circuit (clarify / unsupported)         └─ finalize (refused)
 *
 * Nothing here is streamed: a route is only ever derived from a completed response
 * (route, execution flags, recorded stages), or shown as a labelled illustration.
 */

export type NodeId = 'router' | 'analytics' | 'evidence' | 'synthesis' | 'verifier' | 'answer' | 'clarify' | 'limit'
export type EdgeId = 'router-analytics' | 'router-evidence' | 'analytics-synthesis' | 'evidence-synthesis' | 'synthesis-verifier'
  | 'verifier-answer' | 'verifier-limit' | 'router-clarify' | 'router-limit'
/** done: ran. skipped: on no path for this request. stopped: the request ended here. idle: no claim made. */
export type NodeState = 'done' | 'skipped' | 'stopped' | 'failed' | 'idle'
/** Where the shown route comes from. Only `live` and `test` describe a request made in this session. */
export type WorkflowSource = 'live' | 'test' | 'recorded' | 'overview' | 'pending'
export type Detail = { label: string; value: string }

export const NODE_ORDER: NodeId[] = ['router', 'analytics', 'evidence', 'synthesis', 'verifier', 'answer', 'clarify', 'limit']
export const OUTCOME_NODES: NodeId[] = ['answer', 'clarify', 'limit']
export const EDGES: Record<EdgeId, [NodeId, NodeId]> = {
  'router-analytics': ['router', 'analytics'], 'router-evidence': ['router', 'evidence'],
  'analytics-synthesis': ['analytics', 'synthesis'], 'evidence-synthesis': ['evidence', 'synthesis'],
  'synthesis-verifier': ['synthesis', 'verifier'], 'verifier-answer': ['verifier', 'answer'], 'verifier-limit': ['verifier', 'limit'],
  'router-clarify': ['router', 'clarify'], 'router-limit': ['router', 'limit'],
}

export type Workflow = {
  source: WorkflowSource
  nodes: Record<NodeId, NodeState>
  /** Edges the request travelled, grouped into steps; edges in one step ran side by side. */
  steps: EdgeId[][]
  /** The verifier sent the draft back once (the only loop the graph has). */
  revised: boolean
  outcome: NodeId | null
  /** One short line per node, from the response. */
  meta: Partial<Record<NodeId, string>>
  /** Safe artifacts per node: inputs and results, never reasoning or prompts. */
  details: Partial<Record<NodeId, Detail[]>>
}

const idle = (): Record<NodeId, NodeState> => Object.fromEntries(NODE_ORDER.map(id => [id, 'idle'])) as Record<NodeId, NodeState>

export type Scenario = 'fact' | 'definition' | 'driver' | 'clarification' | 'unsupported'
export const SCENARIOS: Scenario[] = ['driver', 'fact', 'definition', 'clarification', 'unsupported']

function route(analytics: boolean, retrieval: boolean, synthesis: boolean, verification: boolean, outcome: NodeId | null) {
  const nodes = idle()
  const steps: EdgeId[][] = []
  nodes.router = 'done'
  const branch: EdgeId[] = [], join: EdgeId[] = []
  if (analytics) { nodes.analytics = 'done'; branch.push('router-analytics'); join.push('analytics-synthesis') }
  if (retrieval) { nodes.evidence = 'done'; branch.push('router-evidence'); join.push('evidence-synthesis') }
  if (branch.length) steps.push(branch)
  if (synthesis) { nodes.synthesis = 'done'; if (join.length) steps.push(join) }
  if (verification) { nodes.verifier = 'done'; steps.push(['synthesis-verifier']) }
  if (outcome === 'answer') { nodes.answer = 'done'; steps.push(['verifier-answer']) }
  if (outcome === 'clarify') { nodes.clarify = 'stopped'; steps.push(['router-clarify']) }
  if (outcome === 'limit') { nodes.limit = 'stopped'; steps.push([verification ? 'verifier-limit' : 'router-limit']) }
  for (const id of NODE_ORDER) if (nodes[id] === 'idle') nodes[id] = 'skipped'
  return { nodes, steps }
}

/** A labelled illustration of a typical route. Never presented as a trace. */
export function scenarioWorkflow(scenario: Scenario | null): Workflow {
  if (!scenario) return { source: 'overview', nodes: idle(), steps: [], revised: false, outcome: null, meta: {}, details: {} }
  const r = scenario === 'fact' ? route(true, false, true, true, 'answer')
    : scenario === 'definition' ? route(false, true, true, true, 'answer')
    : scenario === 'driver' ? route(true, true, true, true, 'answer')
    : scenario === 'clarification' ? route(false, false, false, false, 'clarify')
    : route(false, false, false, false, 'limit')
  const outcome: NodeId = scenario === 'clarification' ? 'clarify' : scenario === 'unsupported' ? 'limit' : 'answer'
  return { source: 'overview', ...r, revised: false, outcome, meta: {}, details: {} }
}

export const pendingWorkflow = (): Workflow => ({ source: 'pending', nodes: idle(), steps: [], revised: false, outcome: null, meta: {}, details: {} })

type Context = { company?: string; scope?: string; metric?: string; period?: string; route: string }
export type WorkflowInput = {
  response: QueryResponse; verification: VerificationView; kind: 'sample' | 'test' | 'live'; lang: Lang
  context: Context; figures: number; calculations: { title: string; passed?: boolean }[]
  citations: { source_title: string; page_number: number | string }[]; alsoRead: number
  findings: number; supportKinds: string[]
}

/** The route one completed response took, read from its own metadata. */
export function buildWorkflow(input: WorkflowInput): Workflow {
  const { response, verification: v, kind, lang, context } = input
  const t = strings(lang).wf
  const labels = new Set(response.execution.stages.map(stage => stage.label))
  const answered = v.outcome === 'answer'
  // The recorded demo answer carries its flags but no stage list; a released answer has been drafted and checked.
  const synthesis = labels.has('Structured draft generated') || (kind === 'sample' && answered)
  const verification = labels.has('Independent verification completed') || (kind === 'sample' && answered)
  const failed = labels.has('Workflow failed safely') || v.state === 'system_failure'
  const outcome: NodeId = answered ? 'answer' : v.outcome === 'clarification' ? 'clarify' : 'limit'
  const { nodes, steps } = route(response.execution.analytics_used, response.execution.retrieval_used, synthesis, verification, outcome)
  if (failed) nodes.limit = 'failed'

  const join = (parts: (string | undefined)[]) => parts.filter(Boolean).join(' · ')
  const meta: Workflow['meta'] = { router: join([context.metric, context.period]) || context.route }
  const details: Workflow['details'] = {
    router: [
      context.company && { label: t.d.company, value: context.company }, context.scope && { label: t.d.scope, value: context.scope },
      context.metric && { label: t.d.metric, value: context.metric }, context.period && { label: t.d.period, value: context.period },
      { label: t.d.kind, value: context.route },
    ].filter(Boolean) as Detail[],
  }
  if (nodes.analytics === 'done') {
    meta.analytics = t.m.figures(input.figures)
    details.analytics = [
      context.metric && { label: t.d.metric, value: context.metric }, { label: t.d.figures, value: String(input.figures) },
      ...input.calculations.map(c => ({ label: c.title, value: c.passed === undefined ? t.d.calculated : c.passed ? t.d.reconciles : t.d.notReconciled })),
    ].filter(Boolean) as Detail[]
  }
  if (nodes.evidence === 'done') {
    meta.evidence = t.m.sources(input.citations.length)
    details.evidence = [
      ...input.citations.map(c => ({ label: t.d.cited, value: `${c.source_title} · ${t.d.page} ${c.page_number}` })),
      ...(input.alsoRead ? [{ label: t.d.alsoRead, value: String(input.alsoRead) }] : []),
    ]
    if (!details.evidence.length) details.evidence = [{ label: t.d.cited, value: '0' }]
  }
  if (nodes.synthesis === 'done') {
    meta.synthesis = t.m.findings(input.findings)
    details.synthesis = [
      { label: t.d.written, value: kind === 'live' ? t.d.byModel : kind === 'test' ? t.d.byTest : t.d.byRecorded },
      { label: t.d.released, value: String(input.findings) },
      ...(input.supportKinds.length ? [{ label: t.d.support, value: input.supportKinds.join(', ') }] : []),
      ...(kind !== 'sample' ? [{ label: t.d.calls, value: String(response.execution.provider_calls) }] : []),
    ]
  }
  if (nodes.verifier === 'done') {
    meta.verifier = response.execution.revision_used ? t.m.revised : v.checked ? t.m.checked(v.checked) : undefined
    details.verifier = [
      { label: t.d.checked, value: `${v.released} / ${Math.max(v.checked, v.released)}` },
      { label: t.d.revision, value: response.execution.revision_used ? t.d.revisedOnce : t.d.none },
      ...(v.removed ? [{ label: t.d.removed, value: String(v.removed) }] : []),
      { label: t.d.result, value: v.title },
    ]
  }
  details[outcome] = [{ label: t.d.result, value: v.title }]
  meta[outcome] = outcome === 'clarify' ? t.m.beforeAnalysis : outcome === 'limit' && !verification ? t.m.beforeAnalysis : undefined
  return { source: kind === 'sample' ? 'recorded' : kind, nodes, steps, revised: response.execution.revision_used, outcome, meta, details }
}
