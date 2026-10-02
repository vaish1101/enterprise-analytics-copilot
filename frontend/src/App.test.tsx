import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { SAMPLE_LABELS, SAMPLE_RESPONSE } from './lib/sample'

const metadata = {
  system_version: 'step8-product-1.0.0', headline: 'x',
  companies: [{ id: 'henkel', name: 'Henkel', periods: ['H1 2026'], scopes: ['Group'] }],
  examples: [{ category: 'Analytics', questions: ['What were Henkel H1 2026 sales?'] }],
  retrieval_model: 'm', retrieval_method: 'dense', retrieval_version: 'v', top_k: 5, graph_version: 'g', verifier_version: 'v',
  demo_mode: false, rights_notice: 'Only governed outputs.', labels: SAMPLE_LABELS,
}
const live = { ...structuredClone(SAMPLE_RESPONSE), request_id: 'request_1', session_id: 'session_12345678', latency_ms: 1200, provider: 'fake', model: 'det',
  execution: { ...SAMPLE_RESPONSE.execution, stages: [{ order: 1, label: 'Question classified', status: 'completed', duration_ms: 2 }] } }

const respond = (body: unknown, ok = true, status = 200) => Promise.resolve({ ok, status, json: () => Promise.resolve(body) } as Response)
function installFetch(queryResult: unknown = live, ok = true, status = 200, session: unknown = { session_id: 'session_12345678', interaction_count: 1, interactions: [] }) {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes('/metadata')) return respond(metadata)
    if (url.includes('/sessions/')) return respond(session)
    return respond(queryResult, ok, status)
  }))
}
const queryCalls = () => vi.mocked(fetch).mock.calls.filter(c => String(c[0]).includes('/query'))

async function ask(question: string) {
  const box = screen.getByLabelText('Follow-up or new question')
  fireEvent.change(box, { target: { value: question } })
  fireEvent.keyDown(box, { key: 'Enter', metaKey: true })
}

describe('Enterprise Analytics Copilot experience', () => {
  beforeEach(() => { window.location.hash = ''; localStorage.clear(); installFetch() })
  afterEach(() => { cleanup(); vi.unstubAllGlobals() })

  it('opens as a product: headline, demo dataset, a real composer and example questions', async () => {
    render(<App />)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Ask a business question. See the analysis behind the answer.')
    expect(screen.getByText(/Mercedes-Benz · Henkel · Siemens/)).toBeInTheDocument()
    // Three capability rows, each a full-row button carrying its label and one validated question.
    for (const label of ['Compare figures', 'Explain reported drivers', 'Understand a definition']) expect(screen.getByText(label).closest('button')).not.toBeNull()
    fireEvent.click(screen.getByText('Understand a definition').closest('button')!)
    expect(screen.getByLabelText('Business question')).toHaveValue('How does Henkel define organic sales growth?')
    // The wider coverage lives behind "What can I ask?"; picking a question fills the composer only.
    fireEvent.click(screen.getByRole('button', { name: 'What can I ask?' }))
    const coverage = await screen.findByRole('dialog', { name: 'What can I ask?' })
    expect(within(coverage).getAllByRole('heading', { level: 4 })).toHaveLength(6)
    fireEvent.click(within(coverage).getByRole('button', { name: 'What was Siemens revenue in Q2 2026?' }))
    expect(screen.getByLabelText('Business question')).toHaveValue('What was Siemens revenue in Q2 2026?')
    expect(queryCalls()).toHaveLength(0)
    // No alternative illustrated composition: without WebGL the page is simply the product.
    expect(screen.queryByRole('img', { name: /Drawing of the answer instrument/ })).not.toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Analyze' }).length).toBeGreaterThan(0)
  })

  it('never uses internal or design-concept vocabulary in visible text', async () => {
    render(<App />)
    const text = document.body.textContent ?? ''
    expect(text).not.toMatch(/Anatomy|anatomy|DECOMPOSITION_EXPLANATION|MANAGEMENT_ATTRIBUTED|percentage_point|EUR_million|knowledge-only|retrieval route/)
  })

  it('states that companies are public-reporting demo datasets, not customers', () => {
    render(<App />)
    expect(screen.getByText('Mercedes-Benz, Henkel and Siemens are used only as public-reporting demo datasets. No affiliation, sponsorship, partnership or endorsement is implied.')).toBeInTheDocument()
    expect(screen.getByText(/© 2026 Vaishnavi Iyer · Enterprise Analytics Copilot/)).toBeInTheDocument()
    const linkedIn = screen.getByRole('link', { name: /LinkedIn/ })
    expect(linkedIn).toHaveAttribute('href', 'https://www.linkedin.com/in/vaishnavi-iyer-60b9141b1/')
    expect(linkedIn).toHaveAttribute('target', '_blank')
    expect(screen.getByText('Designed and developed as an independent portfolio project.')).toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/customer|trusted by/i)
  })

  it('submits from the first-viewport composer', async () => {
    render(<App />)
    fireEvent.submit(screen.getByLabelText('Business question').closest('form')!)
    await waitFor(() => expect(queryCalls()).toHaveLength(1))
    expect(JSON.parse(queryCalls()[0][1]!.body as string).question).toBe('What drove Mercedes-Benz Cars adjusted EBIT in Q2 2026?')
  })

  it('labels the demo answer honestly and scopes verification to findings', () => {
    render(<App />)
    expect(screen.getByText('Recorded demo')).toBeInTheDocument()
    const lead = screen.getByRole('region', { name: 'Direct answer' })
    expect(lead).toHaveTextContent('Adjusted EBIT fell from €1,228m to €909m.')
    expect(lead).toHaveTextContent('Largest reported contributions')
    // The direct answer states only reported values; it never derives a figure of its own.
    expect(lead).not.toHaveTextContent('319')
    expect(within(lead).queryByText(/verified|checked/i)).not.toBeInTheDocument()
    expect(screen.getByText('5 checked findings')).toBeInTheDocument()
    // The answer comes before the checks.
    const status = screen.getByRole('region', { name: 'Checks and sources' })
    expect(lead.compareDocumentPosition(status) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.queryByText(/^Verified$/)).not.toBeInTheDocument()
  })

  it('renders the governed bridge with the combined component intact and inspects a single bar', async () => {
    render(<App />)
    const figure = screen.getByRole('figure')
    expect(within(figure).getAllByText('Volume / structure / net pricing').length).toBeGreaterThan(0)
    expect(within(figure).getByText(/Adds up to €909m/)).toBeInTheDocument()
    fireEvent.click(within(figure).getByRole('button', { name: 'Show as table' }))
    expect(within(figure).getByRole('table')).toHaveTextContent('Volume / structure / net pricing')
  })

  it('opens the inspector at the selected figure from a KPI and restores focus on Escape', async () => {
    const fact = structuredClone(live)
    fact.analytics = { ...fact.analytics!, operation: 'RETRIEVE', components: [], supporting: [], reconciliations: [], changes: [] }
    installFetch(fact)
    render(<App />)
    await ask('What was Mercedes-Benz Cars adjusted EBIT in Q2 2026?')
    await screen.findByRole('button', { name: /Adjusted EBIT, Q2 2026: 909 million euros/ })
    const kpi = screen.getByRole('button', { name: /Adjusted EBIT, Q2 2026: 909 million euros/ })
    kpi.focus(); fireEvent.click(kpi)
    const dialog = await screen.findByRole('dialog', { name: 'Sources & checks' })
    const selected = within(dialog).getByRole('region', { name: 'Selected figure' })
    expect(selected).toHaveTextContent('€909m')
    expect(selected).toHaveTextContent('Mercedes-Benz Group Fact Sheet Q2 2026 XLSX')
    fireEvent.keyDown(document, { key: 'Escape' })
    await waitFor(() => expect(document.activeElement).toBe(kpi))
  })

  it('links a finding to its own support', async () => {
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Show all 5' }))
    fireEvent.click(screen.getByRole('button', { name: 'Show the source for finding 5' }))
    const selected = await screen.findByRole('region', { name: 'Finding 05' })
    expect(selected).toHaveTextContent('Cited sources')
    expect(selected).toHaveTextContent('Mercedes-Benz Group Fact Sheet Q2 2026 PDF')
  })

  it('shows an honest loading state, then the live result with recorded execution', async () => {
    let resolve: (v: Response) => void = () => {}
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => String(input).includes('/metadata') ? respond(metadata)
      : String(input).includes('/sessions/') ? respond({ interactions: [] }) : new Promise<Response>(r => { resolve = r })))
    render(<App />)
    await ask('What drove Mercedes-Benz Cars adjusted EBIT in Q2 2026?')
    expect(await screen.findByText('Working on your answer…')).toBeInTheDocument()
    expect(screen.queryByText(/Retrieving|Calculating|Verifying|%/)).not.toBeInTheDocument()
    resolve({ ok: true, status: 200, json: () => Promise.resolve(live) } as Response)
    expect(await screen.findByText('Live result')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /^Sources & checks/ }))
    expect(await screen.findByRole('list', { name: 'Recorded steps' })).toHaveTextContent('Reported figures')
  })

  it('ignores a stale response when a newer analysis has started', async () => {
    const resolvers: ((v: Response) => void)[] = []
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => String(input).includes('/metadata') ? respond(metadata)
      : String(input).includes('/sessions/') ? respond({ interactions: [] }) : new Promise<Response>(r => { resolvers.push(r) })))
    render(<App />)
    await ask('What drove Mercedes-Benz Cars adjusted EBIT in Q2 2026?')
    fireEvent.click(screen.getByRole('button', { name: 'New analysis' }))
    resolvers[0]({ ok: true, status: 200, json: () => Promise.resolve(live) } as Response)
    await new Promise(r => setTimeout(r, 20))
    expect(screen.queryByText('Live result')).not.toBeInTheDocument()
    expect(screen.getByText('Recorded demo')).toBeInTheDocument()
  })

  it('shows context carried forward from the previous question', async () => {
    installFetch(live, true, 200, { session_id: 's', interaction_count: 1, interactions: [{ request_id: 'request_1', question: 'What about Vans?', resolved_question: 'What drove Mercedes-Benz Vans adjusted EBIT in Q2 2026?' }] })
    render(<App />)
    await ask('What about Vans?')
    expect(await screen.findByText(/Read together with your previous question as/)).toHaveTextContent('What drove Mercedes-Benz Vans adjusted EBIT in Q2 2026?')
  })

  it('sends the session on follow-ups and records history without re-running', async () => {
    render(<App />)
    await ask('What drove Mercedes-Benz Cars adjusted EBIT in Q2 2026?')
    await screen.findByText('Live result')
    await ask('What about Vans?')
    await waitFor(() => expect(queryCalls()).toHaveLength(2))
    expect((queryCalls()[1][1]?.headers as Record<string, string>)['X-Session-ID']).toBe('session_12345678')
    fireEvent.click(screen.getByRole('button', { name: /History, 2 analyses/ }))
    const dialog = await screen.findByRole('dialog', { name: 'History' })
    fireEvent.click(within(dialog).getAllByRole('button', { name: /What drove/ })[0])
    expect(queryCalls()).toHaveLength(2)
  })

  it('turns clarification into structured governed choices', async () => {
    installFetch({ ...live, status: 'NEEDS_CLARIFICATION', route: 'NEEDS_CLARIFICATION', claims: [], provenance_summary: [], citations: [], analytics: null, fact_sources: [], verification: null,
      clarification_question: "For Mercedes-Benz, does 'sales' mean revenue or vehicle unit sales?",
      clarification_options: [{ label: 'Revenue', detail: 'Value in € million', question: 'How did Mercedes revenue change in Q2 2026?' }, { label: 'Unit sales', detail: 'Vehicles sold', question: 'How did Mercedes unit sales change in Q2 2026?' }] })
    render(<App />)
    await ask('How did Mercedes sales change in Q2 2026?')
    expect(await screen.findByRole('heading', { name: 'Do you mean revenue or vehicles sold?' })).toBeInTheDocument()
    expect(screen.getByText('Choose one so the analysis uses the right measure.')).toBeInTheDocument()
    expect(within(document.getElementById('product')!).queryByText(/governed/i)).not.toBeInTheDocument()
    const group = screen.getByRole('group', { name: 'Do you mean revenue or vehicles sold?' })
    expect(group).toHaveTextContent('Money earned from sales, reported in € million.')
    expect(group).toHaveTextContent('Number of vehicles sold.')
    expect(screen.queryByRole('figure')).not.toBeInTheDocument()
    fireEvent.click(within(group).getByRole('button', { name: /Vehicles sold/ }))
    await waitFor(() => expect(queryCalls()).toHaveLength(2))
    expect(JSON.parse(queryCalls()[1][1]!.body as string).question).toBe('How did Mercedes unit sales change in Q2 2026?')
  })

  it('explains an unsupported question and offers the truthful next step', async () => {
    installFetch({ ...live, status: 'REFUSED', route: 'UNSUPPORTED', claims: [], provenance_summary: [], citations: [], analytics: null, fact_sources: [], verification: null,
      answer: 'x', refusal_reason: "Mercedes-Benz does not disclose a separate governed price contribution here; the source only supports the combined 'Volume / structure / net pricing' bridge component.",
      alternatives: [{ label: 'Show the reported bridge', question: 'What drove Mercedes-Benz Cars adjusted EBIT in Q2 2026?' }] })
    render(<App />)
    await ask('How much Mercedes-Benz Cars EBIT was due to price alone in Q2 2026?')
    expect(await screen.findByRole('heading', { name: 'Not separately disclosed' })).toBeInTheDocument()
    expect(screen.getByText(/does not disclose a separate price contribution/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /View the combined contribution/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Edit question' })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.queryByText(/UNSUPPORTED/)).not.toBeInTheDocument()
  })

  it.each([
    ['EVIDENCE_CONFLICT', { refusal_reason: 'EVIDENCE_CONFLICT', answer: 'The governed sources conflict.' }, 'The sources disagree'],
    ['REFUSED', { refusal_reason: 'WORKFLOW_FAILURE:AuthenticationError', answer: 'I cannot provide a verified answer.' }, 'Something went wrong'],
  ])('renders %s as a distinct product state without numbers', async (status, patch, title) => {
    installFetch({ ...live, status, claims: [], provenance_summary: [], verification: null, citations: [], analytics: null, fact_sources: [], ...patch })
    render(<App />)
    await ask('What was revenue?')
    expect(await screen.findByRole('heading', { name: title })).toBeInTheDocument()
    expect(screen.queryByRole('figure')).not.toBeInTheDocument()
    expect(screen.queryByText(/checked finding/)).not.toBeInTheDocument()
  })

  it('keeps the question on transport errors and offers retry', async () => {
    installFetch({ error: { code: 'RATE_LIMITED', message: 'The demo request limit has been reached.' } }, false, 429)
    render(<App />)
    await ask('What were Henkel H1 2026 sales?')
    expect(await screen.findByText('The demo request limit has been reached.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
    expect(screen.getByDisplayValue('What were Henkel H1 2026 sales?')).toBeInTheDocument()
  })

  it('persists an explicit theme and follows the system by default', () => {
    render(<App />)
    expect(document.documentElement.dataset.themePreference).toBe('system')
    const toggle = screen.getByRole('switch', { name: 'Dark mode' })
    const wasDark = toggle.getAttribute('aria-checked') === 'true'
    fireEvent.click(toggle)
    expect(document.documentElement.dataset.theme).toBe(wasDark ? 'light' : 'dark')
    expect(localStorage.getItem('eac-theme')).toBe(wasDark ? 'light' : 'dark')
    // One direct control: no chevron, no appearance menu.
    expect(screen.queryByRole('button', { name: 'Appearance options' })).not.toBeInTheDocument()
    expect(screen.getAllByRole('switch')).toHaveLength(1)
  })

  it('lets the hero examples hint the relevant instrument subassembly without submitting', () => {
    const seen: unknown[] = []
    const listener = (event: Event) => seen.push((event as CustomEvent).detail)
    window.addEventListener('eac-instrument', listener)
    render(<App />)
    fireEvent.mouseEnter(screen.getByText('Understand a definition').closest('button')!)
    fireEvent.mouseEnter(screen.getByText('Explain reported drivers').closest('button')!)
    fireEvent.focus(screen.getByLabelText('Business question'))
    window.removeEventListener('eac-instrument', listener)
    expect(seen).toEqual(['metric', 'analytics', 'wake'])
    expect(queryCalls()).toHaveLength(0)
  })

  it('shows only the execution branches that actually ran', async () => {
    installFetch({ ...live, route: 'KNOWLEDGE_ONLY', analytics: null, execution: { ...live.execution, analytics_used: false, retrieval_used: true,
      stages: [{ order: 1, label: 'Question classified', status: 'completed' }, { order: 3, label: 'Document evidence retrieved', status: 'completed' },
        { order: 5, label: 'Structured draft generated', status: 'completed' }, { order: 6, label: 'Independent verification completed', status: 'completed' }] } })
    render(<App />)
    await ask('How does Henkel define organic sales growth?')
    fireEvent.click(await screen.findByRole('button', { name: /^Sources & checks/ }))
    const map = await screen.findByRole('list', { name: 'Recorded steps' })
    expect(map).toHaveTextContent('Company reporting')
    expect(map).not.toHaveTextContent('Reported figures')
  })

  it('offers one public experience: no classic view', async () => {
    window.location.hash = '#classic'
    render(<App />)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Ask a business question.')
    expect(screen.queryByText(/Classic/i)).not.toBeInTheDocument()
  })

  it('gives every control an accessible name, including icon-only ones', async () => {
    render(<App />)
    for (const button of screen.getAllByRole('button')) expect(button).toHaveAccessibleName()
    expect(screen.getByRole('link', { name: 'Enterprise Analytics Copilot, back to top' })).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'How it works' }).length).toBeGreaterThan(0)
    // New analysis is offered only once there is an analysis to replace.
    expect(screen.queryByRole('button', { name: 'New analysis' })).not.toBeInTheDocument()
    await ask('What drove Mercedes-Benz Cars adjusted EBIT in Q2 2026?')
    expect(await screen.findByRole('button', { name: 'New analysis' })).toBeInTheDocument()
  })

  it('keeps utilities in one menu on small screens', () => {
    render(<App />)
    const menu = screen.getByRole('button', { name: 'Menu' })
    fireEvent.click(menu)
    expect(menu).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getAllByRole('switch')).toHaveLength(2)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(menu).toHaveAttribute('aria-expanded', 'false')
  })

  it('offers three trust controls after the answer and opens the route this analysis took', async () => {
    render(<App />)
    const controls = within(screen.getByRole('region', { name: 'Checks and sources' })).getAllByRole('button').map(b => b.textContent)
    expect(controls.slice(-3)).toEqual(['Sources & checks', 'Interpretation & limits', 'View analysis steps'])
    const limits = screen.getByRole('region', { name: 'Interpretation & limits' })
    expect(limits).toHaveTextContent('The disclosure does not establish how much of the combined effect came from price alone.')
    expect(screen.queryByRole('list', { name: 'Workflow steps' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'View analysis steps' }))
    const steps = screen.getByRole('region', { name: 'Analysis steps' })
    expect(steps).toHaveTextContent('Recorded workflow')
    expect(steps).toHaveTextContent('It is not a current run.')
    expect(within(steps).getAllByRole('listitem').map(li => li.getAttribute('data-state'))).toEqual(['done', 'done', 'done', 'done', 'done', 'done', 'skipped', 'skipped'])
    fireEvent.click(within(steps).getByRole('button', { name: /Check findings/ }))
    expect(steps).toHaveTextContent('Draft corrected once')
    fireEvent.click(within(steps).getByRole('button', { name: 'Technical names' }))
    expect(steps).toHaveTextContent('Verifier / Critic')
    expect(steps).toHaveTextContent('Only synthesis calls the language model.')
  })

  it('explains the governed workflow in How it works without claiming a trace', async () => {
    render(<App />)
    fireEvent.click(screen.getAllByRole('button', { name: 'How it works' })[0])
    const dialog = await screen.findByRole('dialog', { name: 'How an answer is built' })
    expect(within(dialog).getAllByRole('tab').map(t => t.textContent)).toEqual(['Overview', 'Governed workflow', 'Technical details'])
    fireEvent.click(within(dialog).getByRole('tab', { name: 'Governed workflow' }))
    expect(dialog).toHaveTextContent('Governed analytical workflow')
    expect(dialog).toHaveTextContent('It is not a trace of a request.')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Ambiguous question' }))
    expect(dialog).not.toHaveTextContent(/\bRan\b/)
    expect(within(dialog).getByRole('button', { name: /Clarification/ })).toHaveTextContent('Ends here')
    fireEvent.click(within(dialog).getByRole('tab', { name: 'Technical details' }))
    expect(dialog).toHaveTextContent('LangGraph')
  })

  it('keeps the material limit beside the answer and explains input, operation and output without the instrument', async () => {
    render(<App />)
    expect(screen.getByRole('region', { name: 'Direct answer' })).toHaveTextContent('Price is not disclosed separately from volume and structure.')
    expect(screen.getByText(/A governed analytical workflow coordinates reported figures/)).toBeInTheDocument()
    // No WebGL here: the same explanation is given in text above the result.
    const panel = screen.getByRole('region', { name: 'How an answer is built' })
    expect(panel).toHaveTextContent('Mercedes-Benz Cars')
    expect(panel).toHaveTextContent('Reported figures + Reporting evidence + Supported synthesis + Checks')
    expect(screen.queryByRole('button', { name: 'Replay explanation' })).not.toBeInTheDocument()
    await ask('How did Mercedes sales change in Q2 2026?')
    await waitFor(() => expect(queryCalls()).toHaveLength(1))
  })

  it('does not present a located section as a written answer', async () => {
    const doc = structuredClone(live)
    doc.route = 'KNOWLEDGE_ONLY'; doc.provider = 'deterministic_fake'; doc.analytics = null
    doc.verification = { ...doc.verification!, supported_claims: 1, total_claims: 1 }
    doc.claims = doc.claims.slice(-1).map(c => ({ ...c, text: 'The report\'s "Business development" section covers this metric for the period.' }))
    doc.provenance_summary = [{ provenance: 'REPORTED', count: 1 }]
    installFetch(doc)
    render(<App />)
    await ask('What did management say about Mercedes-Benz Cars adjusted EBIT in Q2 2026?')
    expect(await screen.findByText('Located in the reporting, not summarised')).toBeInTheDocument()
    expect(screen.queryByText(/checked finding/)).not.toBeInTheDocument()
  })

  it('never calls a test-mode answer a live result', async () => {
    installFetch({ ...live, provider: 'deterministic_fake' })
    render(<App />)
    await ask('What drove Mercedes-Benz Cars adjusted EBIT in Q2 2026?')
    // The internal test state is not badged, and is never passed off as a live result.
    await screen.findByRole('region', { name: 'Direct answer' })
    expect(screen.queryByText(/test mode/i)).not.toBeInTheDocument()
    expect(screen.queryByText('Live result')).not.toBeInTheDocument()
    expect(screen.queryByText('Recorded demo')).not.toBeInTheDocument()
  })

  it('locks background scroll while the evidence sheet is open', async () => {
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: /^Sources & checks/ }))
    await screen.findByRole('dialog', { name: 'Sources & checks' })
    expect(document.documentElement.style.overflow).toBe('hidden')
    fireEvent.keyDown(document, { key: 'Escape' })
    await waitFor(() => expect(document.documentElement.style.overflow).toBe(''))
  })

  it('shows a response with no verification result as not shown, never as findings', async () => {
    installFetch({ ...live, verification: null })
    render(<App />)
    await ask('What drove Mercedes-Benz Cars adjusted EBIT in Q2 2026?')
    expect(await screen.findByText('The service returned an invalid verification result. No answer was released.')).toBeInTheDocument()
    expect(screen.queryByText(/checked finding/)).not.toBeInTheDocument()
  })

  it('switches the interface to German, persists it, and formats numbers the German way', async () => {
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Deutsch' }))
    expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent('Stellen Sie eine Geschäftsfrage. Sehen Sie die Analyse hinter der Antwort.')
    expect(localStorage.getItem('eac-lang')).toBe('de')
    expect(document.documentElement.lang).toBe('de')
    expect(screen.getByRole('region', { name: 'Direkte Antwort' })).toHaveTextContent('1.228 Mio. €')
    expect(screen.getAllByText('Demo-Fragen müssen derzeit auf Englisch gestellt werden.').length).toBeGreaterThan(0)
    expect(screen.getAllByRole('button', { name: 'Analysieren' }).length).toBeGreaterThan(0)
    expect(screen.getByText('5 geprüfte Aussagen')).toBeInTheDocument()
    // Company content stays as published: the analysed question is not translated.
    expect(screen.getAllByText('What drove Mercedes-Benz Cars adjusted EBIT in Q2 2026?').length).toBeGreaterThan(0)
    cleanup()
    render(<App />)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Stellen Sie eine Geschäftsfrage. Sehen Sie die Analyse hinter der Antwort.')
    fireEvent.click(screen.getByRole('button', { name: 'English' }))
  })

  it('shows a reported figure as a headline value, with no chart', async () => {
    const fact = structuredClone(live)
    fact.analytics = { ...fact.analytics!, operation: 'RETRIEVE', components: [], supporting: [], reconciliations: [], changes: [] }
    fact.citations = []
    installFetch(fact)
    render(<App />)
    await ask('What was Mercedes-Benz Cars adjusted EBIT in Q2 2026?')
    expect(await screen.findByRole('button', { name: /Adjusted EBIT, Q2 2026: 909 million euros/ })).toBeInTheDocument()
    expect(screen.queryByRole('figure')).not.toBeInTheDocument()
  })

  it('keeps technical vocabulary out of the default interface', async () => {
    render(<App />)
    const text = document.body.textContent ?? ''
    expect(text).not.toMatch(/governed metric|provenance|retrieval|LangGraph|pgvector|verifier|Model-written|Released findings/i)
  })
})
