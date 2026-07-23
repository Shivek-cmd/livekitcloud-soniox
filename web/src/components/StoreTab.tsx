import { useEffect, useState } from 'react'
import {
  fetchMenu,
  postStoreCheckout,
  type MenuCatalog,
  type MenuItem,
  type StoreCheckoutSummary,
  type StorePaymentPreference,
} from '../lib/api'
import { sortCategories } from '../lib/menuSort'
import { categoryInitials, categoryTheme } from '../lib/categoryTheme'
import { SPICE_LEVELS, type SpiceLevel } from '../lib/storeCart'
import { useStoreCart } from '../hooks/useStoreCart'

type DietFilter = 'all' | 'veg' | 'nonveg'
type CartPane = 'cart' | 'checkout' | 'validated' | 'placed'

const DELIVERY_FEE_HINT = 5 // display hint; server is authoritative

/**
 * Store browse + cart + checkout (S1–S7).
 * Full-bleed menu until first add; Your order slides in from the right.
 */
export function StoreTab() {
  const [menu, setMenu] = useState<MenuCatalog | null>(null)
  const [error, setError] = useState(false)
  const [activeCategory, setActiveCategory] = useState('')
  const [diet, setDiet] = useState<DietFilter>('all')
  const [search, setSearch] = useState('')
  const [spicePick, setSpicePick] = useState<MenuItem | null>(null)
  const [pane, setPane] = useState<CartPane>('cart')
  const [orderType, setOrderType] = useState<'pickup' | 'delivery'>('pickup')
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [address, setAddress] = useState('')
  const [note, setNote] = useState('')
  const [paymentPreference, setPaymentPreference] =
    useState<StorePaymentPreference>('later')
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string[] | null>(null)
  const [summary, setSummary] = useState<StoreCheckoutSummary | null>(null)
  const cart = useStoreCart()

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

  useEffect(() => {
    setSpicePick(null)
  }, [diet, search, activeCategory])

  const matchesDiet = (item: MenuItem) => {
    if (diet === 'veg') return item.veg
    if (diet === 'nonveg') return !item.veg
    return true
  }

  const requestAdd = (item: MenuItem) => {
    if (!item.available) return
    if (item.has_spice) {
      setSpicePick((prev) => (prev?.id === item.id ? null : item))
      return
    }
    cart.addItem({
      id: item.id,
      name: item.name,
      unitPrice: item.price,
      imageUrl: item.image_url,
    })
    if (pane === 'validated' || pane === 'placed') {
      setPane('cart')
      setSummary(null)
    }
  }

  const confirmSpice = (spice: SpiceLevel) => {
    if (!spicePick) return
    cart.addItem({
      id: spicePick.id,
      name: spicePick.name,
      unitPrice: spicePick.price,
      spice,
      imageUrl: spicePick.image_url,
    })
    setSpicePick(null)
    if (pane === 'validated' || pane === 'placed') {
      setPane('cart')
      setSummary(null)
    }
  }

  const displayDelivery =
    pane === 'checkout' && orderType === 'delivery' ? DELIVERY_FEE_HINT : 0
  const displayTotal = cart.subtotal + displayDelivery

  const submitCheckout = async () => {
    setFormError(null)
    setSubmitting(true)
    try {
      const res = await postStoreCheckout({
        items: cart.lines.map((l) => ({
          id: l.id,
          qty: l.qty,
          modifiers: l.modifiers,
        })),
        order_type: orderType,
        customer: { name: name.trim(), phone: phone.trim() },
        delivery_address: orderType === 'delivery' ? address.trim() : null,
        note: note.trim() || null,
        payment_preference: paymentPreference,
        place: false,
      })
      if (!res.ok || !res.summary) {
        setFormError(res.blockers?.length ? res.blockers : ['Validation failed.'])
        return
      }
      if (
        res.summary.payment_preference === 'now' ||
        res.summary.payment_preference === 'later'
      ) {
        setPaymentPreference(res.summary.payment_preference)
      }
      setSummary(res.summary)
      setPane('validated')
    } catch {
      setFormError(['Could not reach the server. Is the token server running?'])
    } finally {
      setSubmitting(false)
    }
  }

  const placeOrder = async () => {
    setFormError(null)
    setSubmitting(true)
    try {
      const res = await postStoreCheckout({
        items: cart.lines.map((l) => ({
          id: l.id,
          qty: l.qty,
          modifiers: l.modifiers,
        })),
        order_type: orderType,
        customer: { name: name.trim(), phone: phone.trim() },
        delivery_address: orderType === 'delivery' ? address.trim() : null,
        note: note.trim() || null,
        payment_preference: paymentPreference,
        place: true,
      })
      if (!res.ok || !res.summary) {
        setFormError(
          res.blockers?.length
            ? res.blockers
            : ['Could not place the order. Please try again.'],
        )
        return
      }
      setSummary(res.summary)
      setPane('placed')
      cart.clear()
    } catch {
      setFormError(['Could not reach the server. Is the token server running?'])
    } finally {
      setSubmitting(false)
    }
  }

  const startNewOrder = () => {
    setPane('cart')
    setSummary(null)
    setFormError(null)
    setNote('')
  }

  const categories = menu?.categories ?? []
  const effectiveCategory = activeCategory || categories[0]?.name || ''
  const query = search.trim().toLowerCase()
  const searching = query.length > 0

  const imageById = (() => {
    const map = new Map<string, string>()
    for (const cat of categories) {
      for (const item of cat.items) {
        if (item.image_url) map.set(item.id, item.image_url)
      }
    }
    return map
  })()

  const lineImage = (id: string, fallback?: string | null) =>
    fallback || imageById.get(id) || null

  const matchesSearch = (item: MenuItem) => {
    if (!searching) return true
    return (
      item.name.toLowerCase().includes(query) ||
      (item.voice_line || '').toLowerCase().includes(query)
    )
  }

  type DisplayItem = MenuItem & { categoryName: string }

  const displayItems: DisplayItem[] = searching
    ? categories.flatMap((cat) =>
        cat.items
          .filter(matchesDiet)
          .filter(matchesSearch)
          .map((item) => ({ ...item, categoryName: cat.name })),
      )
    : (
        categories.find((c) => c.name === effectiveCategory)?.items ?? []
      )
        .filter(matchesDiet)
        .map((item) => ({ ...item, categoryName: effectiveCategory }))

  // Full-bleed menu until first add; stay open through checkout / thank-you.
  const cartPanelOpen =
    cart.itemCount > 0 ||
    pane === 'checkout' ||
    pane === 'validated' ||
    pane === 'placed'

  return (
    <div className="store">
      <div
        className={cartPanelOpen ? 'store-grid cart-open' : 'store-grid'}
      >
        <section className="panel store-catalog" aria-label="Store menu">
          <div className="panel-title">
            Menu
            {menu && (
              <span className="store-item-count">{menu.item_count} items</span>
            )}
          </div>

          {error && (
            <div className="menu-status">
              Couldn’t load the menu. Please refresh.
            </div>
          )}
          {!error && !menu && (
            <div className="menu-status">Loading menu…</div>
          )}

          {menu && (
            <>
              <div className="store-toolbar">
                <label className="store-search">
                  <span className="store-search-icon" aria-hidden>
                    <svg viewBox="0 0 24 24" width="18" height="18" fill="none">
                      <circle
                        cx="11"
                        cy="11"
                        r="6.5"
                        stroke="currentColor"
                        strokeWidth="2"
                      />
                      <path
                        d="M16.5 16.5L20 20"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                      />
                    </svg>
                  </span>
                  <input
                    type="search"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search dishes…"
                    autoComplete="off"
                    enterKeyHint="search"
                  />
                  {search && (
                    <button
                      type="button"
                      className="store-search-clear"
                      aria-label="Clear search"
                      onClick={() => setSearch('')}
                    >
                      ×
                    </button>
                  )}
                </label>
                <div className="store-diet-chips" role="group" aria-label="Diet filter">
                  <button
                    type="button"
                    className={diet === 'all' ? 'store-chip is-active' : 'store-chip'}
                    onClick={() => setDiet('all')}
                  >
                    All
                  </button>
                  <button
                    type="button"
                    className={
                      diet === 'veg' ? 'store-chip is-active is-veg' : 'store-chip'
                    }
                    onClick={() => setDiet('veg')}
                  >
                    <span className="diet-mark veg" aria-hidden />
                    Veg
                  </button>
                  <button
                    type="button"
                    className={
                      diet === 'nonveg'
                        ? 'store-chip is-active is-nonveg'
                        : 'store-chip'
                    }
                    onClick={() => setDiet('nonveg')}
                  >
                    <span className="diet-mark nonveg" aria-hidden />
                    Non-veg
                  </button>
                </div>
              </div>

              <div className="store-browse">
                <nav
                  className={
                    searching ? 'store-cat-nav is-dimmed' : 'store-cat-nav'
                  }
                  aria-label="Menu categories"
                >
                  {categories.map((cat) => {
                    const active = !searching && cat.name === effectiveCategory
                    const n = cat.items.filter(matchesDiet).length
                    return (
                      <button
                        key={cat.name}
                        type="button"
                        className={
                          active ? 'store-cat-link is-active' : 'store-cat-link'
                        }
                        aria-current={active ? 'true' : undefined}
                        onClick={() => {
                          setActiveCategory(cat.name)
                          setSearch('')
                        }}
                      >
                        <span className="store-cat-link-name">{cat.name}</span>
                        <span className="store-cat-link-count">{n}</span>
                      </button>
                    )
                  })}
                </nav>

                <div className="store-browse-main">
                  <div className="store-browse-head">
                    <h3>
                      {searching
                        ? `Results for “${search.trim()}”`
                        : effectiveCategory}
                    </h3>
                    <span>
                      {displayItems.length}{' '}
                      {displayItems.length === 1 ? 'dish' : 'dishes'}
                    </span>
                  </div>

                  <div className="menu-scroll store-menu-scroll">
                    <ul className="store-card-grid">
                      {displayItems.map((item) => {
                        const spiceOpen = spicePick?.id === item.id
                        return (
                        <li
                          key={item.id}
                          className={
                            [
                              'store-card',
                              !item.available ? 'unavailable' : '',
                              spiceOpen ? 'is-spice-open' : '',
                            ]
                              .filter(Boolean)
                              .join(' ')
                          }
                        >
                          <div
                            className={
                              item.image_url
                                ? 'store-card-media has-photo'
                                : 'store-card-media'
                            }
                            data-theme={categoryTheme(item.categoryName)}
                            data-veg={item.veg ? '1' : '0'}
                          >
                            {item.image_url ? (
                              <img
                                className="store-card-photo"
                                src={item.image_url}
                                alt=""
                                loading="lazy"
                                decoding="async"
                                referrerPolicy="no-referrer"
                              />
                            ) : (
                              <span className="store-card-media-mark" aria-hidden>
                                {categoryInitials(item.categoryName)}
                              </span>
                            )}
                            <span
                              className={
                                item.veg
                                  ? 'diet-mark veg store-card-mark'
                                  : 'diet-mark nonveg store-card-mark'
                              }
                              title={item.veg ? 'Vegetarian' : 'Non-vegetarian'}
                            />
                            {!item.available && (
                              <span className="store-card-soldout">Sold out</span>
                            )}
                          </div>
                          <div className="store-card-body">
                            <div className="store-card-top">
                              <h4 className="store-card-name">{item.name}</h4>
                              {item.has_spice && item.available && (
                                <span className="store-spice-tag">Spice</span>
                              )}
                            </div>
                            {searching && (
                              <p className="store-card-cat">{item.categoryName}</p>
                            )}
                            {spiceOpen ? (
                              <div className="store-spice-stage">
                                <div
                                  className="store-spice-inline"
                                  role="group"
                                  aria-label={`Spice level for ${item.name}`}
                                >
                                  <p className="store-spice-inline-label">
                                    Choose spice
                                  </p>
                                  <div className="store-spice-chips">
                                    {SPICE_LEVELS.map((level) => (
                                      <button
                                        key={level}
                                        type="button"
                                        className="store-spice-chip"
                                        onClick={() => confirmSpice(level)}
                                      >
                                        {level}
                                      </button>
                                    ))}
                                  </div>
                                  <button
                                    type="button"
                                    className="store-spice-inline-cancel"
                                    onClick={() => setSpicePick(null)}
                                  >
                                    Cancel
                                  </button>
                                </div>
                              </div>
                            ) : (
                              <div className="store-card-foot store-card-foot-enter">
                                <span className="store-card-price">
                                  ${item.price.toFixed(2)}
                                </span>
                                <button
                                  type="button"
                                  className="store-add-btn"
                                  disabled={!item.available}
                                  onClick={() => requestAdd(item)}
                                  aria-label={`Add ${item.name}`}
                                >
                                  Add
                                </button>
                              </div>
                            )}
                          </div>
                        </li>
                        )
                      })}
                    </ul>
                    {displayItems.length === 0 && (
                      <div className="menu-status">
                        {searching
                          ? 'No dishes match your search.'
                          : 'No items match this filter.'}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </>
          )}
        </section>

        <div className="store-cart-stage" aria-hidden={!cartPanelOpen}>
          <aside
            className="panel store-cart"
            aria-label="Your order"
            aria-hidden={!cartPanelOpen}
          >
          <div className="panel-title">
            {pane === 'checkout'
              ? 'Checkout'
              : pane === 'validated'
                ? 'Review'
                : pane === 'placed'
                  ? 'Order placed'
                  : 'Your order'}
            {pane === 'cart' && cart.itemCount > 0 && (
              <span className="store-item-count">{cart.itemCount}</span>
            )}
          </div>

          {pane === 'cart' && cart.lines.length > 0 && (
            <>
              <ul className="store-cart-lines">
                {cart.lines.map((line) => {
                  const img = lineImage(line.id, line.imageUrl)
                  return (
                    <li key={line.key} className="store-cart-line">
                      <div className="store-cart-line-row">
                        <div
                          className={
                            img
                              ? 'store-cart-thumb has-photo'
                              : 'store-cart-thumb'
                          }
                          aria-hidden
                        >
                          {img ? (
                            <img
                              src={img}
                              alt=""
                              loading="lazy"
                              decoding="async"
                              referrerPolicy="no-referrer"
                            />
                          ) : (
                            <span>{line.name.slice(0, 1)}</span>
                          )}
                        </div>
                        <div className="store-cart-line-body">
                          <div className="store-cart-line-main">
                            <span className="store-cart-name">{line.name}</span>
                            {line.modifiers.length > 0 && (
                              <span className="store-cart-mod">
                                {line.modifiers.join(', ')}
                              </span>
                            )}
                            <span className="store-cart-line-price">
                              ${(line.unitPrice * line.qty).toFixed(2)}
                            </span>
                          </div>
                          <div className="store-cart-line-actions">
                            <div
                              className="store-qty"
                              role="group"
                              aria-label={`Quantity for ${line.name}`}
                            >
                              <button
                                type="button"
                                className="store-qty-btn"
                                onClick={() =>
                                  cart.setQty(line.key, line.qty - 1)
                                }
                                aria-label="Decrease quantity"
                              >
                                −
                              </button>
                              <span className="store-qty-val">{line.qty}</span>
                              <button
                                type="button"
                                className="store-qty-btn"
                                onClick={() =>
                                  cart.setQty(line.key, line.qty + 1)
                                }
                                aria-label="Increase quantity"
                              >
                                +
                              </button>
                            </div>
                            <button
                              type="button"
                              className="store-remove-btn"
                              onClick={() => cart.removeItem(line.key)}
                            >
                              Remove
                            </button>
                          </div>
                        </div>
                      </div>
                    </li>
                  )
                })}
              </ul>

              <div className="store-cart-footer">
                <div className="ot-row">
                  <span>Subtotal</span>
                  <span>${cart.subtotal.toFixed(2)}</span>
                </div>
                <div className="ot-row ot-total">
                  <span>Total</span>
                  <span>${cart.subtotal.toFixed(2)}</span>
                </div>
                <button
                  type="button"
                  className="store-checkout-btn ready"
                  disabled={cart.lines.length === 0}
                  onClick={() => {
                    setFormError(null)
                    setPane('checkout')
                  }}
                >
                  Checkout
                </button>
                <p className="store-pay-note">
                  Pay at pickup/delivery, or pay now online at checkout.
                </p>
              </div>
            </>
          )}

          {pane === 'checkout' && (
            <div className="store-checkout-form">
              <div className="store-order-type" role="group" aria-label="Order type">
                <button
                  type="button"
                  className={
                    orderType === 'pickup'
                      ? 'store-type-btn active'
                      : 'store-type-btn'
                  }
                  onClick={() => setOrderType('pickup')}
                >
                  Pickup
                </button>
                <button
                  type="button"
                  className={
                    orderType === 'delivery'
                      ? 'store-type-btn active'
                      : 'store-type-btn'
                  }
                  onClick={() => setOrderType('delivery')}
                >
                  Delivery
                </button>
              </div>

              <label className="store-field">
                <span>Name</span>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  autoComplete="name"
                  placeholder="Your name"
                />
              </label>
              <label className="store-field">
                <span>Phone</span>
                <input
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  autoComplete="tel"
                  placeholder="5875551234"
                />
              </label>
              {orderType === 'delivery' && (
                <label className="store-field">
                  <span>Delivery address</span>
                  <textarea
                    value={address}
                    onChange={(e) => setAddress(e.target.value)}
                    rows={3}
                    placeholder="Street, city, postal code"
                  />
                </label>
              )}
              <label className="store-field">
                <span>Note (optional)</span>
                <input
                  type="text"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="Allergies or special requests"
                />
              </label>

              <div
                className="store-order-type"
                role="radiogroup"
                aria-label="Payment"
              >
                <button
                  type="button"
                  role="radio"
                  aria-checked={paymentPreference === 'later'}
                  className={
                    paymentPreference === 'later'
                      ? 'store-type-btn active'
                      : 'store-type-btn'
                  }
                  onClick={() => setPaymentPreference('later')}
                >
                  {orderType === 'delivery' ? 'Pay on delivery' : 'Pay at pickup'}
                </button>
                <button
                  type="button"
                  role="radio"
                  aria-checked={paymentPreference === 'now'}
                  className={
                    paymentPreference === 'now'
                      ? 'store-type-btn active'
                      : 'store-type-btn'
                  }
                  onClick={() => setPaymentPreference('now')}
                >
                  Pay now
                </button>
              </div>
              <p className="store-pay-note">
                {paymentPreference === 'now'
                  ? 'Pay online after you place — card entry on a secure Clover page (next step).'
                  : orderType === 'delivery'
                    ? 'Pay when your order arrives.'
                    : 'Pay when you pick up.'}
              </p>

              {formError && (
                <ul className="store-form-errors">
                  {formError.map((b) => (
                    <li key={b}>{b}</li>
                  ))}
                </ul>
              )}

              <div className="store-cart-footer">
                <div className="ot-row">
                  <span>Subtotal</span>
                  <span>${cart.subtotal.toFixed(2)}</span>
                </div>
                {orderType === 'delivery' && (
                  <div className="ot-row">
                    <span>Delivery</span>
                    <span>${DELIVERY_FEE_HINT.toFixed(2)}</span>
                  </div>
                )}
                <div className="ot-row ot-total">
                  <span>Total</span>
                  <span>${displayTotal.toFixed(2)}</span>
                </div>
                <button
                  type="button"
                  className="store-checkout-btn ready"
                  disabled={submitting || cart.lines.length === 0}
                  onClick={submitCheckout}
                >
                  {submitting ? 'Checking…' : 'Review order'}
                </button>
                <button
                  type="button"
                  className="store-back-btn"
                  onClick={() => setPane('cart')}
                  disabled={submitting}
                >
                  Back to cart
                </button>
                <p className="store-pay-note">
                  Prices are confirmed by the server. Placing the order comes next.
                </p>
              </div>
            </div>
          )}

          {pane === 'validated' && summary && (
            <div className="store-validated">
              <p className="store-validated-banner">
                Prices confirmed. Ready to place —{' '}
                {(summary.payment_preference ?? paymentPreference) === 'now'
                  ? 'you chose pay now.'
                  : summary.order_type === 'delivery'
                    ? 'pay when it arrives.'
                    : 'pay at pickup.'}
              </p>
              <ul className="store-cart-lines">
                {summary.items.map((line) => {
                  const img = lineImage(line.id)
                  return (
                  <li
                    key={`${line.id}-${line.modifiers.join('-')}`}
                    className="store-cart-line"
                  >
                    <div className="store-cart-line-row">
                      <div
                        className={
                          img ? 'store-cart-thumb has-photo' : 'store-cart-thumb'
                        }
                        aria-hidden
                      >
                        {img ? (
                          <img
                            src={img}
                            alt=""
                            loading="lazy"
                            decoding="async"
                            referrerPolicy="no-referrer"
                          />
                        ) : (
                          <span>{line.name.slice(0, 1)}</span>
                        )}
                      </div>
                      <div className="store-cart-line-body">
                        <div className="store-cart-line-main">
                          <span className="store-cart-name">
                            {line.qty}× {line.name}
                          </span>
                          {line.modifiers.length > 0 && (
                            <span className="store-cart-mod">
                              {line.modifiers.join(', ')}
                            </span>
                          )}
                          <span className="store-cart-line-price">
                            ${line.line_total.toFixed(2)}
                          </span>
                        </div>
                      </div>
                    </div>
                  </li>
                  )
                })}
              </ul>
              <div className="store-validated-meta">
                <div>
                  <strong>
                    {summary.order_type === 'delivery' ? 'Delivery' : 'Pickup'}
                  </strong>
                  {' · '}
                  {summary.customer.name} · {summary.customer.phone}
                </div>
                {summary.delivery_address && (
                  <div>{summary.delivery_address}</div>
                )}
                {summary.note && <div>Note: {summary.note}</div>}
              </div>
              {formError && (
                <ul className="store-form-errors">
                  {formError.map((b) => (
                    <li key={b}>{b}</li>
                  ))}
                </ul>
              )}
              <div className="store-cart-footer">
                <div className="ot-row">
                  <span>Subtotal</span>
                  <span>${summary.subtotal.toFixed(2)}</span>
                </div>
                {summary.delivery_charge > 0 && (
                  <div className="ot-row">
                    <span>Delivery</span>
                    <span>${summary.delivery_charge.toFixed(2)}</span>
                  </div>
                )}
                <div className="ot-row ot-total">
                  <span>Total</span>
                  <span>${summary.total.toFixed(2)}</span>
                </div>
                <button
                  type="button"
                  className="store-checkout-btn ready"
                  disabled={submitting}
                  onClick={placeOrder}
                >
                  {submitting ? 'Placing…' : 'Place order'}
                </button>
                <button
                  type="button"
                  className="store-back-btn"
                  onClick={() => {
                    setPane('checkout')
                    setFormError(null)
                  }}
                  disabled={submitting}
                >
                  Edit details
                </button>
              </div>
            </div>
          )}

          {pane === 'placed' && summary && (
            <div className="store-placed">
              <p className="store-placed-banner">Thank you — your order is in.</p>
              <div className="store-placed-id">
                Order ID: <strong>{summary.order_id}</strong>
              </div>
              {summary.eta && (
                <div className="store-placed-eta">Ready in about {summary.eta}</div>
              )}
              <ul className="store-cart-lines">
                {summary.items.map((line) => {
                  const img = lineImage(line.id)
                  return (
                  <li
                    key={`${line.id}-${line.modifiers.join('-')}-done`}
                    className="store-cart-line"
                  >
                    <div className="store-cart-line-row">
                      <div
                        className={
                          img ? 'store-cart-thumb has-photo' : 'store-cart-thumb'
                        }
                        aria-hidden
                      >
                        {img ? (
                          <img
                            src={img}
                            alt=""
                            loading="lazy"
                            decoding="async"
                            referrerPolicy="no-referrer"
                          />
                        ) : (
                          <span>{line.name.slice(0, 1)}</span>
                        )}
                      </div>
                      <div className="store-cart-line-body">
                        <div className="store-cart-line-main">
                          <span className="store-cart-name">
                            {line.qty}× {line.name}
                          </span>
                          {line.modifiers.length > 0 && (
                            <span className="store-cart-mod">
                              {line.modifiers.join(', ')}
                            </span>
                          )}
                          <span className="store-cart-line-price">
                            ${line.line_total.toFixed(2)}
                          </span>
                        </div>
                      </div>
                    </div>
                  </li>
                  )
                })}
              </ul>
              <div className="store-validated-meta">
                <div>
                  <strong>
                    {summary.order_type === 'delivery' ? 'Delivery' : 'Pickup'}
                  </strong>
                  {' · '}
                  {summary.customer.name} · {summary.customer.phone}
                </div>
                {summary.delivery_address && (
                  <div>{summary.delivery_address}</div>
                )}
              </div>
              <div className="store-cart-footer">
                <div className="ot-row ot-total">
                  <span>Total</span>
                  <span>${summary.total.toFixed(2)}</span>
                </div>
                <p className="store-pay-note">
                  {(summary.payment_preference ?? paymentPreference) === 'now'
                    ? 'You chose pay now. Online payment link comes in the next step — your order is already with the kitchen.'
                    : `Pay later at ${
                        summary.order_type === 'delivery' ? 'the door' : 'pickup'
                      }.`}
                  {summary.clover_submitted
                    ? ' Sent to the kitchen.'
                    : ' Logged locally (Clover submit off).'}
                </p>
                <button
                  type="button"
                  className="store-checkout-btn ready"
                  onClick={startNewOrder}
                >
                  New order
                </button>
              </div>
            </div>
          )}
          </aside>
        </div>
      </div>
    </div>
  )
}
