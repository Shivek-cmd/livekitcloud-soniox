import { useEffect, useRef, useState } from 'react'
import { fetchMenu, type MenuCatalog } from '../lib/api'
import { useCart } from '../hooks/useCart'

type Feedback = 'added' | 'needs' | 'error'

export function LiveMenu() {
  const [menu, setMenu] = useState<MenuCatalog | null>(null)
  const [error, setError] = useState(false)
  const [feedback, setFeedback] = useState<Record<string, Feedback>>({})
  const [busy, setBusy] = useState<Record<string, boolean>>({})
  const timers = useRef<Record<string, ReturnType<typeof setTimeout>>>({})
  const { addItem, ready } = useCart()

  useEffect(() => {
    let cancelled = false
    fetchMenu()
      .then((m) => {
        if (!cancelled) setMenu(m)
      })
      .catch(() => {
        if (!cancelled) setError(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const t = timers.current
    return () => {
      Object.values(t).forEach(clearTimeout)
    }
  }, [])

  const flash = (id: string, kind: Feedback) => {
    setFeedback((f) => ({ ...f, [id]: kind }))
    clearTimeout(timers.current[id])
    timers.current[id] = setTimeout(() => {
      setFeedback((f) => {
        const next = { ...f }
        delete next[id]
        return next
      })
    }, 2200)
  }

  const onAdd = async (id: string) => {
    setBusy((b) => ({ ...b, [id]: true }))
    const res = await addItem(id)
    setBusy((b) => ({ ...b, [id]: false }))
    if (!res.ok) flash(id, 'error')
    else if (res.needs && res.needs.length > 0) flash(id, 'needs')
    else flash(id, 'added')
  }

  return (
    <section className="panel menu-panel" aria-label="Menu">
      <div className="panel-title">Menu</div>
      {error && <div className="menu-status">Couldn’t load the menu. Please refresh.</div>}
      {!error && !menu && <div className="menu-status">Loading menu…</div>}
      {menu && (
        <div className="menu-scroll">
          {menu.categories.map((cat) => (
            <div key={cat.name} className="menu-cat">
              <h3 className="menu-cat-title">{cat.name}</h3>
              <ul className="menu-items">
                {cat.items.map((item) => {
                  const fb = feedback[item.id]
                  return (
                    <li
                      key={item.id}
                      className={item.available ? 'menu-item' : 'menu-item unavailable'}
                    >
                      <span
                        className={item.veg ? 'veg-dot veg' : 'veg-dot nonveg'}
                        title={item.veg ? 'Vegetarian' : 'Non-vegetarian'}
                        aria-hidden
                      />
                      <span className="mi-name">{item.name}</span>
                      {!item.available && <span className="mi-badge">Sold out</span>}
                      <span className="mi-price">${item.price.toFixed(2)}</span>
                      <button
                        className={`mi-add${fb ? ` fb-${fb}` : ''}`}
                        disabled={!ready || !item.available || busy[item.id]}
                        title={!ready ? 'Start a call to add items' : 'Add to order'}
                        onClick={() => onAdd(item.id)}
                      >
                        {fb === 'added'
                          ? 'Added ✓'
                          : fb === 'needs'
                            ? 'Added · Sierra’ll confirm'
                            : fb === 'error'
                              ? 'Try again'
                              : busy[item.id]
                                ? '…'
                                : 'Add'}
                      </button>
                    </li>
                  )
                })}
              </ul>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
