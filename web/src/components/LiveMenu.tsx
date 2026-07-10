import { useEffect, useRef, useState } from 'react'
import { fetchMenu, type MenuCatalog, type MenuCategory, type MenuItem } from '../lib/api'

type DietFilter = 'all' | 'veg' | 'nonveg'

/** Browse order: how a guest typically builds a meal. Unknown cats go last. */
const CATEGORY_ORDER = [
  'Starters & Snacks',
  'Vegetarian Mains',
  'Non-Veg Mains',
  'Tandoor & Grill',
  'Combos & Platters',
  'Breads & Rice',
  'Desserts',
  'Drinks',
  'Extras & Sides',
]

function sortCategories(categories: MenuCategory[]): MenuCategory[] {
  const rank = (name: string) => {
    const i = CATEGORY_ORDER.findIndex(
      (c) => c.toLowerCase() === name.toLowerCase(),
    )
    return i === -1 ? CATEGORY_ORDER.length : i
  }
  return [...categories].sort((a, b) => {
    const d = rank(a.name) - rank(b.name)
    return d !== 0 ? d : a.name.localeCompare(b.name)
  })
}

export function LiveMenu() {
  const [menu, setMenu] = useState<MenuCatalog | null>(null)
  const [error, setError] = useState(false)
  const [activeCategory, setActiveCategory] = useState('')
  const [diet, setDiet] = useState<DietFilter>('all')
  const [canScrollLeft, setCanScrollLeft] = useState(false)
  const [canScrollRight, setCanScrollRight] = useState(false)
  const pillsRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let cancelled = false
    fetchMenu()
      .then((m) => {
        if (cancelled) return
        const categories = sortCategories(m.categories)
        setMenu({ ...m, categories })
        setActiveCategory(categories[0]?.name ?? '')
      })
      .catch(() => {
        if (!cancelled) setError(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const updatePillScroll = () => {
    const el = pillsRef.current
    if (!el) {
      setCanScrollLeft(false)
      setCanScrollRight(false)
      return
    }
    const max = el.scrollWidth - el.clientWidth
    setCanScrollLeft(el.scrollLeft > 2)
    setCanScrollRight(max > 2 && el.scrollLeft < max - 2)
  }

  useEffect(() => {
    const el = pillsRef.current
    if (!el) return
    updatePillScroll()
    el.addEventListener('scroll', updatePillScroll, { passive: true })
    const ro = new ResizeObserver(updatePillScroll)
    ro.observe(el)
    return () => {
      el.removeEventListener('scroll', updatePillScroll)
      ro.disconnect()
    }
  }, [menu])

  const scrollPills = (dir: -1 | 1) => {
    const el = pillsRef.current
    if (!el) return
    el.scrollBy({ left: dir * Math.max(160, el.clientWidth * 0.7), behavior: 'smooth' })
  }

  const matchesDiet = (item: MenuItem) => {
    if (diet === 'veg') return item.veg
    if (diet === 'nonveg') return !item.veg
    return true
  }

  const categories = menu?.categories ?? []
  const effectiveCategory = activeCategory || categories[0]?.name || ''
  const activeItems =
    (categories.find((c) => c.name === effectiveCategory)?.items ?? []).filter(
      matchesDiet,
    )

  return (
    <section className="panel menu-panel" aria-label="Menu">
      <div className="panel-title">Menu</div>
      {error && <div className="menu-status">Couldn’t load the menu. Please refresh.</div>}
      {!error && !menu && <div className="menu-status">Loading menu…</div>}
      {menu && (
        <>
          <div className="menu-filters" role="group" aria-label="Diet filter">
            <button
              type="button"
              className={diet === 'all' ? 'menu-filter active' : 'menu-filter'}
              onClick={() => setDiet('all')}
            >
              All
            </button>
            <button
              type="button"
              className={diet === 'veg' ? 'menu-filter active veg' : 'menu-filter'}
              onClick={() => setDiet('veg')}
            >
              <span className="veg-dot veg" aria-hidden />
              Veg
            </button>
            <button
              type="button"
              className={diet === 'nonveg' ? 'menu-filter active nonveg' : 'menu-filter'}
              onClick={() => setDiet('nonveg')}
            >
              <span className="veg-dot nonveg" aria-hidden />
              Non-veg
            </button>
          </div>

          <div className="menu-pills-wrap">
            <button
              type="button"
              className="menu-pill-arrow"
              aria-label="Previous categories"
              disabled={!canScrollLeft}
              onClick={() => scrollPills(-1)}
            >
              ‹
            </button>
            <div
              className="menu-pills"
              ref={pillsRef}
              role="tablist"
              aria-label="Menu categories"
            >
              {categories.map((cat) => (
                <button
                  key={cat.name}
                  type="button"
                  role="tab"
                  aria-selected={cat.name === effectiveCategory}
                  className={
                    cat.name === effectiveCategory
                      ? 'menu-pill active'
                      : 'menu-pill'
                  }
                  onClick={() => setActiveCategory(cat.name)}
                >
                  {cat.name}
                </button>
              ))}
            </div>
            <button
              type="button"
              className="menu-pill-arrow"
              aria-label="Next categories"
              disabled={!canScrollRight}
              onClick={() => scrollPills(1)}
            >
              ›
            </button>
          </div>

          <div className="menu-scroll">
            <ul className="menu-items">
              {activeItems.map((item) => (
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
            {activeItems.length === 0 && (
              <div className="menu-status">No items match this filter.</div>
            )}
          </div>
        </>
      )}
    </section>
  )
}
