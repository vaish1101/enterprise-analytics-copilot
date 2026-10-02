import type { ReactElement, SVGProps } from 'react'
import type { SupportKind } from '../lib/viewModel'
import type { VerificationState } from '../lib/verification'

/*
 * One icon system. 16px grid, 1.25 stroke, round caps, currentColor.
 * Support glyphs are semantic marks, not decoration: each maps to exactly one
 * support mechanism in the governed pipeline.
 */

type IconProps = SVGProps<SVGSVGElement> & { size?: number }

function Svg({ size = 16, children, ...rest }: IconProps) {
  return <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.25}
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" {...rest}>{children}</svg>
}

export const IconArrowRight = (p: IconProps) => <Svg {...p}><path d="M3 8h10M9 4l4 4-4 4" /></Svg>
export const IconArrowDown = (p: IconProps) => <Svg {...p}><path d="M8 3v10M4 9l4 4 4-4" /></Svg>
export const IconArrowUp = (p: IconProps) => <Svg {...p}><path d="M8 13V3M4 7l4-4 4 4" /></Svg>
export const IconExternal = (p: IconProps) => <Svg {...p}><path d="M6 3.5H3.5v9h9V10M9 3.5h3.5V7M12.5 3.5 7 9" /></Svg>
export const IconClose = (p: IconProps) => <Svg {...p}><path d="M4 4l8 8M12 4l-8 8" /></Svg>
export const IconChevron = (p: IconProps) => <Svg {...p}><path d="M6 4l4 4-4 4" /></Svg>
export const IconTable = (p: IconProps) => <Svg {...p}><rect x="2.5" y="3" width="11" height="10" rx="1.5" /><path d="M2.5 6.5h11M2.5 10h11M6.5 6.5V13" /></Svg>
export const IconBars = (p: IconProps) => <Svg {...p}><path d="M3 13V8M6.5 13V4M10 13V9.5M13.5 13V6" /></Svg>
export const IconInfo = (p: IconProps) => <Svg {...p}><circle cx="8" cy="8" r="5.5" /><path d="M8 7.25v3.5M8 5.2v.05" /></Svg>
export const IconLayers = (p: IconProps) => <Svg {...p}><path d="M8 2.5 14 5.5 8 8.5 2 5.5z" /><path d="M2 8.5l6 3 6-3M2 11l6 3 6-3" opacity=".55" /></Svg>

/* ---- Support glyphs -------------------------------------------------------- */

export const GlyphFact = (p: IconProps) => <Svg {...p}><rect x="2.75" y="2.75" width="10.5" height="10.5" rx="1.25" /><path d="M2.75 6.4h10.5M2.75 9.6h10.5M6.2 6.4v6.85" /></Svg>
export const GlyphCalculation = (p: IconProps) => <Svg {...p}><path d="M11.75 3.25h-7.5L8.4 8l-4.15 4.75h7.5" /></Svg>
export const GlyphManagement = (p: IconProps) => <Svg {...p}><path d="M8 2.5 13.5 8 8 13.5 2.5 8z" /><path d="M8 6v4" opacity=".6" /></Svg>
export const GlyphInterpretation = (p: IconProps) => <Svg {...p}><circle cx="8" cy="8" r="5.25" strokeDasharray="1.6 2.1" /></Svg>
export const GlyphLimitation = (p: IconProps) => <Svg {...p}><path d="M8 2.75 13.5 12.75H2.5z" /><path d="M8 6.75v2.6M8 11.2v.05" /></Svg>
export const GlyphDocument = (p: IconProps) => <Svg {...p}><path d="M4 2.75h5.25L12 5.5v7.75H4z" /><path d="M9 2.75V5.75h3M6 8.5h4M6 10.75h2.5" /></Svg>

export const SUPPORT_META: Record<SupportKind, { label: string; description: string; Glyph: (p: IconProps) => ReactElement }> = {
  fact: { label: 'Reported figure', description: 'Matches a figure in the governed fact table exactly.', Glyph: GlyphFact },
  calculation: { label: 'Calculated from reported figures', description: 'Produced by a recorded, deterministic calculation.', Glyph: GlyphCalculation },
  document: { label: 'Cited passage', description: 'Supported by a retrieved passage from company reporting.', Glyph: GlyphDocument },
  management: { label: 'Management attribution · not causal', description: 'How management attributed the change. Not an established cause.', Glyph: GlyphManagement },
  interpretation: { label: 'Interpretation', description: 'A reading of the governed material, not a reported figure.', Glyph: GlyphInterpretation },
  limitation: { label: 'Limitation', description: 'A caveat that bounds the answer.', Glyph: GlyphLimitation },
}

export const IconSun = (p: IconProps) => <Svg {...p}><circle cx="8" cy="8" r="2.75" /><path d="M8 1.75v1.5M8 12.75v1.5M1.75 8h1.5M12.75 8h1.5M3.6 3.6l1.05 1.05M11.35 11.35l1.05 1.05M3.6 12.4l1.05-1.05M11.35 4.65l1.05-1.05" /></Svg>
export const IconMoon = (p: IconProps) => <Svg {...p}><path d="M13 9.6A5.25 5.25 0 1 1 6.4 3a4.25 4.25 0 0 0 6.6 6.6Z" /></Svg>
export const IconSystem = (p: IconProps) => <Svg {...p}><rect x="2.25" y="3" width="11.5" height="8" rx="1.5" /><path d="M6 13.25h4M8 11v2.25" /></Svg>
export const IconHistory = (p: IconProps) => <Svg {...p}><path d="M2.75 8a5.25 5.25 0 1 0 1.6-3.8M2.5 2.75v2.5H5" /><path d="M8 5.25V8l1.9 1.3" /></Svg>
export const IconPlus = (p: IconProps) => <Svg {...p}><path d="M8 3v10M3 8h10" /></Svg>
export const IconCopy = (p: IconProps) => <Svg {...p}><rect x="5.25" y="5.25" width="8" height="8" rx="1.5" /><path d="M10.75 5.25V3.5a.75.75 0 0 0-.75-.75H3.5a.75.75 0 0 0-.75.75V10c0 .41.34.75.75.75h1.75" /></Svg>

/* ---- Verification mark -------------------------------------------------------- */

export function VerificationMark({ state, released = 0, checked = 0, size = 28 }: { state: VerificationState; released?: number; checked?: number; size?: number }) {
  const r = 11
  const c = 2 * Math.PI * r
  const segments = Math.max(checked, released, 1)
  const gap = segments > 1 ? 2.2 : 0
  const seg = c / segments - gap
  return <svg className={`vmark vmark-${state}`} width={size} height={size} viewBox="0 0 28 28" aria-hidden="true" focusable="false">
    {state === 'verified' || state === 'subset' || state === 'verified_with_limitations' ? <>
      {Array.from({ length: segments }, (_, i) => <circle key={i} className={i < released ? 'vm-seg on' : 'vm-seg off'} cx="14" cy="14" r={r}
        strokeDasharray={`${seg} ${c - seg}`} strokeDashoffset={-(i * (seg + gap)) + c / 4} />)}
      {state === 'verified' && <path className="vm-core" d="M9.6 14.2l3 3 5.9-6.4" />}
      {state === 'subset' && <path className="vm-core" d="M9.5 14h9" />}
      {state === 'verified_with_limitations' && <><path className="vm-core" d="M14 9.4v5.4" /><path className="vm-core" d="M14 18.4v.1" /></>}
    </> : null}
    {state === 'refused' && <><circle className="vm-ring" cx="14" cy="14" r={r} /><path className="vm-core" d="M8.2 19.8 19.8 8.2" /></>}
    {(state === 'system_failure' || state === 'unverifiable') && <><circle className="vm-ring" cx="14" cy="14" r={r} strokeDasharray="15 4 6 4" /><path className="vm-core" d="M14 9.4v5.4M14 18.4v.1" /></>}
    {state === 'evidence_conflict' && <><circle className="vm-ring" cx="11.5" cy="14" r="7" /><circle className="vm-ring" cx="16.5" cy="14" r="7" /></>}
    {state === 'clarification' && <><circle className="vm-ring" cx="14" cy="14" r={r} /><path className="vm-core" d="M11.4 11.4a2.7 2.7 0 1 1 3.6 2.5c-.6.3-1 .8-1 1.5v.5M14 18.6v.1" /></>}
    {state === 'unavailable' && <circle className="vm-ring" cx="14" cy="14" r={r} strokeDasharray="2 3" />}
  </svg>
}

export function BrandMark({ size = 22 }: { size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" focusable="false" className="brand-glyph">
    <path d="M12 3.5 20.5 7.6 12 11.7 3.5 7.6z" className="bg-top" />
    <path d="M3.5 11.6 12 15.7l8.5-4.1" className="bg-mid" />
    <path d="M3.5 15.4 12 19.5l8.5-4.1" className="bg-low" />
  </svg>
}
