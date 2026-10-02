import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { setFormatLocale } from '../lib/format'
import { strings, type Lang, type Strings } from './strings'

export type { Lang, Strings } from './strings'
export { strings, METRIC_DE, periodLabel } from './strings'

const KEY = 'eac-lang'

export function readLang(): Lang {
  try { return window.localStorage.getItem(KEY) === 'de' ? 'de' : 'en' } catch { return 'en' }
}

type Ctx = { lang: Lang; s: Strings; setLang: (lang: Lang) => void }
const LangContext = createContext<Ctx>({ lang: 'en', s: strings('en'), setLang: () => undefined })

/** Interface language. The choice persists; number formatting follows it. */
export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>(readLang)
  setFormatLocale(lang)
  useEffect(() => {
    document.documentElement.lang = lang
    try { window.localStorage.setItem(KEY, lang) } catch { /* storage unavailable: lasts for this page */ }
  }, [lang])
  const value = useMemo(() => ({ lang, s: strings(lang), setLang }), [lang])
  return <LangContext.Provider value={value}>{children}</LangContext.Provider>
}

export const useStrings = () => useContext(LangContext)
