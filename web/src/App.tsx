import { useState } from 'react'
import '@livekit/components-styles'
import './App.css'
import { OrderWithSierra } from './components/OrderWithSierra'
import { StoreTab } from './components/StoreTab'

type Tab = 'order' | 'store'

export default function App() {
  const [tab, setTab] = useState<Tab>('order')

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-name">Bizbull Restaurant</span>
          <span className="brand-sub">ਪੰਜਾਬੀ ਖਾਣਾ · Punjabi Cuisine</span>
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
      </header>

      <main className="content">
        {tab === 'order' ? <OrderWithSierra /> : <StoreTab />}
      </main>
    </div>
  )
}
