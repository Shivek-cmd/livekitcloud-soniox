import { useEffect, useState } from 'react'
import { fetchMenu, type MenuCatalog } from '../lib/api'

export function LiveMenu() {
  const [menu, setMenu] = useState<MenuCatalog | null>(null)
  const [error, setError] = useState(false)

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
                {cat.items.map((item) => (
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
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
