import { useEffect, useState } from 'react'

export type ThemePreference = 'light' | 'dark' | 'system'
export type ResolvedTheme = 'light' | 'dark'

const KEY = 'eac-theme'
const media = () => window.matchMedia?.('(prefers-color-scheme: light)')

export function readPreference(): ThemePreference {
  try {
    const value = window.localStorage.getItem(KEY)
    return value === 'light' || value === 'dark' || value === 'system' ? value : 'system'
  } catch { return 'system' }
}

export function resolveTheme(preference: ThemePreference): ResolvedTheme {
  if (preference !== 'system') return preference
  return media()?.matches ? 'light' : 'dark'
}

export function applyTheme(preference: ThemePreference): ResolvedTheme {
  const resolved = resolveTheme(preference)
  document.documentElement.dataset.theme = resolved
  document.documentElement.dataset.themePreference = preference
  window.dispatchEvent(new CustomEvent<ResolvedTheme>('eac-theme', { detail: resolved }))
  return resolved
}

/** Theme preference state. Explicit choices persist; System follows the OS live. */
export function useTheme() {
  const [preference, setPreference] = useState<ThemePreference>(readPreference)
  const [resolved, setResolved] = useState<ResolvedTheme>(() => resolveTheme(readPreference()))

  useEffect(() => {
    setResolved(applyTheme(preference))
    try {
      if (preference === 'system') window.localStorage.removeItem(KEY)
      else window.localStorage.setItem(KEY, preference)
    } catch { /* storage unavailable: preference lasts for this page only */ }
    if (preference !== 'system') return
    const query = media()
    const onChange = () => setResolved(applyTheme('system'))
    query?.addEventListener?.('change', onChange)
    return () => query?.removeEventListener?.('change', onChange)
  }, [preference])

  return { preference, resolved, setPreference }
}

/** Current resolved theme for non-React consumers (the WebGL scene). */
export function currentTheme(): ResolvedTheme {
  return document.documentElement.dataset.theme === 'light' ? 'light' : 'dark'
}
