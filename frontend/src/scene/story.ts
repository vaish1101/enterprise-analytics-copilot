import { gsap } from 'gsap'
import type { StoryState } from './PrecisionEngine'

/**
 * The one master timeline. Scroll scrubs it; submission autoplay scrolls through the same
 * range, so there is never a second version of the sequence. Eases carry the physics:
 *
 *   heavy chassis        → power3.inOut (mass, slight inertia)
 *   precision mechanisms → expo.out (crisp registration)
 *   analytical data      → none (linear, controlled)
 *   evidence leaves      → power2.out (soft, masked)
 *   verification         → expo.out (short, decisive)
 *   unsupported material → power2.in (loses energy)
 */
export function buildStory(state: StoryState) {
  // One phrase, in six readable regions that overlap at their edges: question, figures,
  // reporting evidence, supported analysis, checks, answer. Gentle eases keep its momentum.
  const tl = gsap.timeline({ paused: true, defaults: { ease: 'none' } })
  tl.to(state, { enter: 1, duration: 0.1, ease: 'power1.out' }, 0)
  tl.to(state, { register: 1, duration: 0.1, ease: 'power2.out' }, 0.04)
  tl.to(state, { open: 1, duration: 0.2, ease: 'sine.inOut' }, 0.07)
  tl.to(state, { split: 1, duration: 0.2 }, 0.1)
  tl.to(state, { blocks: 1, duration: 0.16, ease: 'power1.out' }, 0.14)
  tl.to(state, { leaves: 1, duration: 0.16, ease: 'sine.inOut' }, 0.3)
  tl.to(state, { converge: 1, duration: 0.16 }, 0.46)
  tl.to(state, { claims: 1, duration: 0.17, ease: 'power1.inOut' }, 0.48)
  tl.to(state, { align: 1, duration: 0.1, ease: 'power1.inOut' }, 0.6)
  // The convergence on the inner crystal is the one decisive, fast move.
  tl.to(state, { lock: 1, duration: 0.13, ease: 'expo.out' }, 0.66)
  tl.to(state, { drop: 1, duration: 0.1, ease: 'power2.in' }, 0.68)
  tl.to(state, { release: 1, duration: 0.24, ease: 'sine.inOut' }, 0.76)
  tl.set({}, {}, 1)
  return tl
}

export type BeatId = 'ask' | 'register' | 'analytics' | 'evidence' | 'converge' | 'verify' | 'answer'
export type Beat = { id: BeatId; start: number; word: string }

export const BEATS: Beat[] = [
  { id: 'ask', start: 0, word: 'Question' },
  { id: 'register', start: 0.03, word: 'Context' },
  { id: 'analytics', start: 0.16, word: 'Figures' },
  { id: 'evidence', start: 0.31, word: 'Evidence' },
  { id: 'converge', start: 0.48, word: 'Analysis' },
  { id: 'verify', start: 0.64, word: 'Checks' },
  { id: 'answer', start: 0.78, word: 'Answer' },
]

export function beatAt(progress: number): number {
  let index = 0
  for (let i = 0; i < BEATS.length; i++) if (progress >= BEATS[i].start) index = i
  return index
}

/** The three stages shown as an understated progress line: Understand, Analyse, Answer. */
export function stageAt(beatIndex: number): 0 | 1 | 2 {
  const id = BEATS[beatIndex]?.id
  return id === 'ask' || id === 'register' ? 0 : id === 'answer' ? 2 : 1
}

/** How the sample question resolves. Spans index into the question text; values come from the catalog. */
export const QUESTION_TOKENS = [
  { phrase: 'What drove', kind: 'Intent', value: 'Driver analysis' },
  { phrase: 'Mercedes-Benz Cars', kind: 'Scope', value: 'Mercedes-Benz Cars' },
  { phrase: 'adjusted EBIT', kind: 'Metric', value: 'Adjusted EBIT · € million' },
  { phrase: 'Q2 2026', kind: 'Period', value: 'Q2 2026 vs Q2 2025' },
] as const
