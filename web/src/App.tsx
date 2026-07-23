import { useEffect, useState } from 'react'
import '@livekit/components-styles'
import './App.css'
import { OrderWithSierra } from './components/OrderWithSierra'
import { StoreTab } from './components/StoreTab'

type Tab = 'order' | 'store'
type Theme = 'dark' | 'light'

function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    try {
      return (localStorage.getItem('theme') as Theme) || 'light'
    } catch {
      return 'light'
    }
  })

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    try {
      localStorage.setItem('theme', theme)
    } catch {
      /* ignore */
    }
  }, [theme])

  const toggle = () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))
  return [theme, toggle]
}

function ThemeToggle({ theme, onToggle }: { theme: Theme; onToggle: () => void }) {
  const isLight = theme === 'light'
  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={onToggle}
      aria-label={isLight ? 'Switch to dark mode' : 'Switch to light mode'}
      title={isLight ? 'Dark mode' : 'Light mode'}
    >
      <span className={`theme-toggle-thumb ${isLight ? 'light' : 'dark'}`}>
        {isLight ? <SunIcon size={11} /> : <MoonIcon size={11} />}
      </span>
    </button>
  )
}

function SunIcon({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="5" />
      <line x1="12" y1="1" x2="12" y2="3" />
      <line x1="12" y1="21" x2="12" y2="23" />
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
      <line x1="1" y1="12" x2="3" y2="12" />
      <line x1="21" y1="12" x2="23" y2="12" />
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
    </svg>
  )
}

function MoonIcon({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  )
}

const TAB_SESSION_KEY = 'voice_active_tab'

function readStoredTab(): Tab {
  try {
    const v = sessionStorage.getItem(TAB_SESSION_KEY)
    if (v === 'store' || v === 'order') return v
  } catch {
    /* ignore */
  }
  return 'order'
}

export default function App() {
  const [tab, setTab] = useState<Tab>(readStoredTab)
  const [theme, toggleTheme] = useTheme()

  useEffect(() => {
    try {
      sessionStorage.setItem(TAB_SESSION_KEY, tab)
    } catch {
      /* ignore */
    }
  }, [tab])

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-name">Bizbull Restaurant</span>
          <span className="brand-sub">Punjabi Cuisine</span>
        </div>
        <nav className="tabs" role="tablist">
          <button
            role="tab"
            aria-selected={tab === 'order'}
            className={tab === 'order' ? 'tab active' : 'tab'}
            onClick={() => setTab('order')}
          >
            Order with Sierra
          </button>
          <button
            role="tab"
            aria-selected={tab === 'store'}
            className={tab === 'store' ? 'tab active' : 'tab'}
            onClick={() => setTab('store')}
          >
            Store
          </button>
        </nav>
        <div className="topbar-actions">
          <ThemeToggle theme={theme} onToggle={toggleTheme} />
        </div>
      </header>

      <main className="content">
        {tab === 'order' ? <OrderWithSierra /> : <StoreTab />}
      </main>
    </div>
  )
}
