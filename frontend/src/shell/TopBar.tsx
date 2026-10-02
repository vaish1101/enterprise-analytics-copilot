import { useEffect, useRef, useState } from 'react'
import { useStrings, type Lang } from '../i18n'
import type { ResolvedTheme, ThemePreference } from '../lib/theme'
import { BrandMark, IconHistory, IconMoon, IconPlus, IconSun } from '../workspace/glyphs'

/** One visible light/dark control. Until it is used, the theme follows the system. */
function ThemeToggle({ resolved, onChange }: { resolved: ResolvedTheme; onChange: (v: ThemePreference) => void }) {
  const { s } = useStrings()
  const dark = resolved === 'dark'
  return <button type="button" role="switch" aria-checked={dark} aria-label={s.nav.theme} className={`theme-switch ${dark ? 'is-dark' : ''}`}
    onClick={() => onChange(dark ? 'light' : 'dark')}>
    <IconSun size={13} /><IconMoon size={13} /><span className="knob" aria-hidden="true" />
  </button>
}

function LanguageControl() {
  const { s, lang, setLang } = useStrings()
  const langs: Lang[] = ['en', 'de']
  return <div className="lang-control" role="group" aria-label={s.lang.label}>
    {langs.map(l => <button key={l} type="button" lang={l} aria-pressed={lang === l} aria-label={s.lang[l]} onClick={() => setLang(l)}>{l.toUpperCase()}</button>)}
  </div>
}

export function TopBar({ solid, resolved, onTheme, onHistory, onNew, onHowItWorks, historyCount, showNew }: {
  solid: boolean; resolved: ResolvedTheme; onTheme: (v: ThemePreference) => void
  onHistory: (trigger: HTMLElement) => void; onNew: () => void; onHowItWorks: (trigger: HTMLElement) => void; historyCount: number
  /** New analysis is offered only once there is an analysis to replace. */
  showNew: boolean
}) {
  const { s } = useStrings()
  const [menu, setMenu] = useState(false)
  const menuButton = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!menu) return
    const onDown = (event: PointerEvent) => { if (!(event.target as HTMLElement).closest('.bar-menu, .bar-menu-button')) setMenu(false) }
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') { setMenu(false); menuButton.current?.focus() } }
    document.addEventListener('pointerdown', onDown)
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('pointerdown', onDown); document.removeEventListener('keydown', onKey) }
  }, [menu])

  const how = <button type="button" className="bar-link" onClick={event => { setMenu(false); onHowItWorks(menuButton.current ?? event.currentTarget) }}>{s.nav.how}</button>
  const history = <button type="button" className="bar-link" onClick={event => { setMenu(false); onHistory(menuButton.current ?? event.currentTarget) }} aria-label={s.nav.historyCount(historyCount)}>
    <IconHistory size={15} /><span>{s.nav.history}</span>{historyCount > 0 && <span className="count" aria-hidden="true">{historyCount}</span>}
  </button>

  return <header className={`topbar ${solid ? 'is-solid' : ''}`}>
    <a className="brand" href="#top" aria-label={s.nav.home} onClick={event => { event.preventDefault(); window.scrollTo({ top: 0 }) }}>
      <BrandMark /><span>Enterprise Analytics Copilot</span>
    </a>
    <nav className="topbar-actions" aria-label={s.nav.product}>
      <div className="bar-desktop">
        <button type="button" className="bar-link" onClick={event => onHowItWorks(event.currentTarget)}>{s.nav.how}</button>
        <button type="button" className="bar-link" onClick={event => onHistory(event.currentTarget)} aria-label={s.nav.historyCount(historyCount)}>
          <IconHistory size={15} /><span>{s.nav.history}</span>{historyCount > 0 && <span className="count" aria-hidden="true">{historyCount}</span>}
        </button>
      </div>
      {showNew && <button type="button" className="bar-primary" aria-label={s.nav.newAnalysis} onClick={onNew}><IconPlus size={15} /><span className="bar-label">{s.nav.newAnalysis}</span></button>}
      <div className="bar-desktop"><LanguageControl /><ThemeToggle resolved={resolved} onChange={onTheme} /></div>
      <button ref={menuButton} type="button" className="bar-menu-button" aria-haspopup="true" aria-expanded={menu} aria-controls="bar-menu" onClick={() => setMenu(v => !v)}>{s.x.menu}</button>
      {menu && <div id="bar-menu" className="bar-menu">
        {how}{history}
        <div className="bar-menu-row"><span>{s.lang.label}</span><LanguageControl /></div>
        <div className="bar-menu-row"><span>{s.nav.theme}</span><ThemeToggle resolved={resolved} onChange={onTheme} /></div>
      </div>}
    </nav>
  </header>
}
