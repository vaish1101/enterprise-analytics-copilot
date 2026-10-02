import { useEffect, useId, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { IconClose } from '../workspace/glyphs'
import { useStrings } from '../i18n'

/**
 * Modal side sheet (bottom sheet on narrow screens). Traps focus, closes on Escape,
 * restores focus to the trigger, and scrolls only itself: opening it never moves the
 * page, so it cannot disturb scroll-driven presentation state.
 */
export function Sheet({ open, onClose, eyebrow, title, children, returnFocus, className = '', focusSelector, lead, focusKey }: {
  open: boolean; onClose: () => void; eyebrow?: string; title: string; children: ReactNode
  returnFocus?: HTMLElement | null; className?: string; focusSelector?: string; lead?: ReactNode
  /** Changes whenever the requested item changes, so navigation re-targets the scroll. */
  focusKey?: string
}) {
  const panel = useRef<HTMLDivElement>(null)
  const titleId = useId()
  const { lang } = useStrings()

  // Open/close: focus, keyboard trap, page scroll lock, focus restore.
  useEffect(() => {
    if (!open) return
    const node = panel.current
    const back = returnFocus ?? (document.activeElement as HTMLElement | null)
    node?.querySelector<HTMLElement>('.sheet-close')?.focus({ preventScroll: true })
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') { event.preventDefault(); onClose() }
      if (event.key === 'Tab' && node) {
        const focusable = [...node.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), textarea, [tabindex="0"], summary')]
        if (!focusable.length) return
        const first = focusable[0], last = focusable[focusable.length - 1]
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
      }
    }
    document.addEventListener('keydown', onKey)
    // Lock the page behind the sheet. html keeps its scroll position; the stable scrollbar
    // gutter (tokens.css) prevents a layout shift that would move scroll-driven content.
    const root = document.documentElement
    const previous = root.style.overflow
    root.style.overflow = 'hidden'
    return () => { document.removeEventListener('keydown', onKey); root.style.overflow = previous; back?.focus?.({ preventScroll: true }) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  // Navigation inside the sheet: bring the requested item into view, inside the sheet only.
  useEffect(() => {
    if (!open || !focusSelector) return
    const node = panel.current
    const target = node?.querySelector<HTMLElement>(focusSelector)
    if (node && target) node.scrollTop = Math.max(0, target.offsetTop - 72)
  }, [open, focusSelector, focusKey])

  if (!open) return null
  // Portalled to <body> so it always stacks above the fixed top bar, whatever contains the trigger.
  return createPortal(<>
    <div className="sheet-scrim" onClick={onClose} aria-hidden="true" />
    <div ref={panel} className={`sheet ${className}`} role="dialog" aria-modal="true" aria-labelledby={titleId}>
      <header className="sheet-head">
        <div>{lead}{eyebrow && !lead && <span className="sheet-eyebrow">{eyebrow}</span>}<h3 id={titleId}>{title}</h3></div>
        <button type="button" className="icon-button sheet-close" onClick={onClose} aria-label={lang === 'de' ? `${title} schließen` : `Close ${title.toLowerCase()}`}><IconClose /></button>
      </header>
      {children}
    </div>
  </>, document.body)
}
