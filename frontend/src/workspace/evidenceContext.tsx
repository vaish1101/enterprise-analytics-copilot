import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import type { CitationView } from '../lib/viewModel'
import type { FactSource } from '../types'

export type InspectorTarget =
  | { kind: 'citation'; index: number }
  | { kind: 'figure'; factId: number }
  | { kind: 'finding'; id: string }
  | { kind: 'calculation'; key: string }
  | { kind: 'overview' }
  | { kind: 'execution' }

type EvidenceState = {
  citations: CitationView[]
  factSources: Record<number, FactSource>
  activeClaim: string | null
  activeCitation: number | null
  setActiveClaim: (id: string | null) => void
  setActiveCitation: (index: number | null) => void
  inspector: InspectorTarget | null
  openInspector: (target: InspectorTarget, trigger?: HTMLElement | null) => void
  /** Move within an open inspector (source ↔ finding ↔ figure) without losing the way back. */
  navigate: (target: InspectorTarget) => void
  back: (() => void) | null
  closeInspector: () => void
  returnFocus: HTMLElement | null
}

const EvidenceContext = createContext<EvidenceState | null>(null)

export function EvidenceProvider({ citations, factSources, children }: { citations: CitationView[]; factSources: Record<number, FactSource>; children: ReactNode }) {
  const [activeClaim, setActiveClaim] = useState<string | null>(null)
  const [activeCitation, setActiveCitation] = useState<number | null>(null)
  const [inspector, setInspector] = useState<InspectorTarget | null>(null)
  const [returnFocus, setReturnFocus] = useState<HTMLElement | null>(null)
  const [trail, setTrail] = useState<InspectorTarget[]>([])
  const value = useMemo<EvidenceState>(() => ({
    citations, factSources, activeClaim, activeCitation, setActiveClaim, setActiveCitation, inspector, returnFocus,
    openInspector: (target, trigger) => { setReturnFocus(trigger ?? (document.activeElement as HTMLElement | null)); setTrail([]); setInspector(target) },
    navigate: target => { if (inspector) setTrail(t => [...t, inspector]); setInspector(target) },
    back: trail.length ? () => { setInspector(trail[trail.length - 1]); setTrail(t => t.slice(0, -1)) } : null,
    closeInspector: () => setInspector(null),
  }), [citations, factSources, activeClaim, activeCitation, inspector, returnFocus, trail])
  return <EvidenceContext.Provider value={value}>{children}</EvidenceContext.Provider>
}

export function useEvidence(): EvidenceState {
  const value = useContext(EvidenceContext)
  if (!value) throw new Error('useEvidence must be used inside EvidenceProvider')
  return value
}
