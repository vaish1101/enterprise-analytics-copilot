import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/geist'
import '@fontsource-variable/geist-mono'
import App from './App'
import { applyTheme, readPreference } from './lib/theme'
import './styles/tokens.css'
import './styles/landing.css'
import './styles/workspace.css'
import './styles/system.css'

// Resolve the theme before the first React render to avoid a flash.
applyTheme(readPreference())

const root = document.getElementById('root')!
createRoot(root).render(<StrictMode><App /></StrictMode>)
