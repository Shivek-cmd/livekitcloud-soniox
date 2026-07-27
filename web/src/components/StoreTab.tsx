import { useEffect, useRef, useState } from 'react'
import {
  fetchMenu,
  fetchStoreConfig,
  fetchStorePaymentStatus,
  postStoreCheckout,
  postStoreDeliveryQuote,
  type MenuCatalog,
  type MenuItem,
  type StoreCheckoutSummary,
  type StorePaymentPreference,
} from '../lib/api'
import { sortCategories } from '../lib/menuSort'
import { categoryInitials, categoryTheme } from '../lib/categoryTheme'
import { SPICE_LEVELS, type SpiceLevel } from '../lib/storeCart'
import {
  clearStorePayPending,
  loadStorePayPending,
  saveStorePayPending,
  stripStorePayQueryParams,
} from '../lib/storePayPending'
import { useStoreCart } from '../hooks/useStoreCart'
import {
  composeDeliveryAddressLine,
  EMPTY_DELIVERY_ADDRESS,
  validateDeliveryAddressFields,
  type StoreDeliveryAddressFields,
} from '../lib/storeDeliveryAddress'

type DietFilter = 'all' | 'veg' | 'nonveg'
type CartPane = 'cart' | 'checkout' | 'validated' | 'awaiting_payment' | 'placed'

const DELIVERY_FEE_HINT = 5 // display hint when Direct off; server is authoritative

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
  const [deliveryAddr, setDeliveryAddr] =
    useState<StoreDeliveryAddressFields>(EMPTY_DELIVERY_ADDRESS)
  const [note, setNote] = useState('')
  const [paymentPreference, setPaymentPreference] =
    useState<StorePaymentPreference>('later')
  const [checkoutKey, setCheckoutKey] = useState(() => {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
      return crypto.randomUUID()
    }
    return `store_${Date.now()}_${Math.random().toString(36).slice(2)}`
  })
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string[] | null>(null)
  const [summary, setSummary] = useState<StoreCheckoutSummary | null>(null)
  const [receiptUrl, setReceiptUrl] = useState<string | null>(null)
  const [payNowEnabled, setPayNowEnabled] = useState(false)
  const [uberDirectEnabled, setUberDirectEnabled] = useState(false)
  const [deliveryFeeFallback, setDeliveryFeeFallback] =
    useState(DELIVERY_FEE_HINT)
  const [uberQuoteId, setUberQuoteId] = useState<string | null>(null)
  const [uberQuoteFee, setUberQuoteFee] = useState<number | null>(null)
  const [uberQuoteMinutes, setUberQuoteMinutes] = useState<number | null>(null)
  const [quoteLoading, setQuoteLoading] = useState(false)
  const [quoteHint, setQuoteHint] = useState<string | null>(null)
  const [paymentPollTimedOut, setPaymentPollTimedOut] = useState(false)
  const [payReturnNote, setPayReturnNote] = useState<string | null>(null)
  const skipAutoOpenCheckout = useRef(false)
  const cart = useStoreCart()

  // Restore pending pay-now after Clover redirect (new tab / refresh).
  useEffect(() => {
    let fromPay: string | null = null
    try {
      fromPay = new URLSearchParams(window.location.search).get('store_pay')
    } catch {
      fromPay = null
    }
    const pending = loadStorePayPending()
    if (pending?.summary && pending.checkout_session_id) {
      skipAutoOpenCheckout.current = true
      setPaymentPreference('now')
      setSummary(pending.summary)
      if (pending.summary.placed && pending.summary.order_id) {
        setPane('placed')
      } else {
        setPane('awaiting_payment')
      }
      if (fromPay === '0') {
        setPayReturnNote(
          'Payment was cancelled or failed. You can open checkout again, or start a new order.',
        )
      } else if (fromPay === '1') {
        setPayReturnNote('Checking payment status…')
      }
    }
    if (fromPay != null || pending) {
      stripStorePayQueryParams()
    }
  }, [])

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
    fetchStoreConfig().then((cfg) => {
      if (cancelled) return
      setPayNowEnabled(cfg.pay_now_enabled)
      setUberDirectEnabled(Boolean(cfg.uber_direct_enabled))
      if (typeof cfg.delivery_charge_fallback === 'number') {
        setDeliveryFeeFallback(cfg.delivery_charge_fallback)
      }
    })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!payNowEnabled && paymentPreference === 'now') {
      setPaymentPreference('later')
    }
  }, [payNowEnabled, paymentPreference])

  // Debounced Uber Direct quote when delivery address looks complete.
  useEffect(() => {
    if (pane !== 'checkout' || orderType !== 'delivery') {
      return
    }
    if (!uberDirectEnabled) {
      setUberQuoteId(null)
      setUberQuoteFee(null)
      setUberQuoteMinutes(null)
      setQuoteLoading(false)
      setQuoteHint(null)
      return
    }
    const blockers = validateDeliveryAddressFields(deliveryAddr)
    if (blockers.length) {
      setUberQuoteId(null)
      setUberQuoteFee(null)
      setUberQuoteMinutes(null)
      setQuoteLoading(false)
      setQuoteHint(null)
      return
    }

    let cancelled = false
    setQuoteLoading(true)
    setQuoteHint('Getting delivery quote…')
    const timer = window.setTimeout(() => {
      postStoreDeliveryQuote({
        dropoff: {
          street: deliveryAddr.street,
          city: deliveryAddr.city,
          state: deliveryAddr.state,
          postal: deliveryAddr.postal,
          country: deliveryAddr.country || 'CA',
          unit: deliveryAddr.unit || null,
          phone: phone.trim() || null,
          notes: deliveryAddr.notes || null,
        },
        dropoff_phone: phone.trim() || null,
        subtotal: cart.subtotal,
      })
        .then((res) => {
          if (cancelled) return
          if (!res.enabled) {
            setUberQuoteId(null)
            setUberQuoteFee(res.fee ?? deliveryFeeFallback)
            setUberQuoteMinutes(null)
            setQuoteHint(null)
            return
          }
          if (!res.ok || !res.quote_id || res.fee == null) {
            setUberQuoteId(null)
            setUberQuoteFee(deliveryFeeFallback)
            setUberQuoteMinutes(null)
            setQuoteHint(
              res.blockers?.[0] ||
                `Using flat delivery $${deliveryFeeFallback.toFixed(2)} for now.`,
            )
            return
          }
          setUberQuoteId(res.quote_id)
          setUberQuoteFee(res.fee)
          setUberQuoteMinutes(res.duration_minutes ?? null)
          setQuoteHint(
            res.duration_minutes
              ? `About ${res.duration_minutes} min · quote holds ~15 min`
              : 'Quote holds about 15 minutes',
          )
        })
        .catch(() => {
          if (cancelled) return
          setUberQuoteId(null)
          setUberQuoteFee(deliveryFeeFallback)
          setQuoteHint(
            `Could not reach Uber — using flat $${deliveryFeeFallback.toFixed(2)}.`,
          )
        })
        .finally(() => {
          if (!cancelled) setQuoteLoading(false)
        })
    }, 550)

    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [
    pane,
    orderType,
    uberDirectEnabled,
    deliveryAddr,
    phone,
    cart.subtotal,
    deliveryFeeFallback,
  ])

  useEffect(() => {
    setSpicePick(null)
  }, [diet, search, activeCategory])

  // Pay now — open Clover Hosted Checkout (before kitchen place).
  useEffect(() => {
    if (pane !== 'awaiting_payment' || !summary?.checkout_url) return
    if (skipAutoOpenCheckout.current) {
      skipAutoOpenCheckout.current = false
      return
    }
    const url = summary.checkout_url
    const w = window.open(url, '_blank', 'noopener,noreferrer')
    if (!w) {
      console.info('Store pay-now popup blocked; use Pay now button')
    }
  }, [pane, summary?.checkout_url, summary?.checkout_session_id])

  // Pay now — poll until paid + kitchen order id (then thank-you).
  useEffect(() => {
    if (pane !== 'awaiting_payment') return
    if ((summary?.payment_preference ?? paymentPreference) !== 'now') return
    const sessionId = summary?.checkout_session_id
    if (!sessionId) return

    let cancelled = false
    let tries = 0
    setPaymentPollTimedOut(false)
    const tick = async () => {
      tries += 1
      try {
        const pay = await fetchStorePaymentStatus({
          checkoutSessionId: sessionId,
        })
        if (cancelled) return
        if (pay?.status === 'paid' && pay.receipt_url) {
          setReceiptUrl(pay.receipt_url)
          setPayReturnNote(null)
          if (pay.order_id) {
            setSummary((prev) => {
              if (!prev) return prev
              const next = {
                ...prev,
                placed: true,
                order_id: pay.order_id ?? prev.order_id,
                eta: pay.eta ?? prev.eta,
                clover_submitted: !String(pay.order_id || '').startsWith('LOG-'),
              }
              saveStorePayPending({
                checkout_session_id: sessionId,
                summary: next,
              })
              return next
            })
            setPane('placed')
            return
          }
        }
      } catch {
        // ignore transient poll errors
      }
      if (cancelled) return
      if (tries >= 40) {
        setPaymentPollTimedOut(true)
        setPayReturnNote(null)
        return
      }
      window.setTimeout(tick, 3000)
    }
    tick()
    return () => {
      cancelled = true
    }
  }, [
    pane,
    summary?.checkout_session_id,
    summary?.payment_preference,
    paymentPreference,
  ])

  // If we restored an already-placed order, fetch receipt once.
  useEffect(() => {
    if (pane !== 'placed' || receiptUrl) return
    const sessionId = summary?.checkout_session_id
    if (!sessionId) return
    let cancelled = false
    fetchStorePaymentStatus({ checkoutSessionId: sessionId }).then((pay) => {
      if (cancelled) return
      if (pay?.receipt_url) setReceiptUrl(pay.receipt_url)
    })
    return () => {
      cancelled = true
    }
  }, [pane, summary?.checkout_session_id, receiptUrl])

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
    if (pane === 'validated' || pane === 'awaiting_payment' || pane === 'placed') {
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
    if (pane === 'validated' || pane === 'awaiting_payment' || pane === 'placed') {
      setPane('cart')
      setSummary(null)
    }
  }

  const displayDelivery =
    pane === 'checkout' && orderType === 'delivery'
      ? uberQuoteFee ?? deliveryFeeFallback
      : 0
  const displayTotal = cart.subtotal + displayDelivery

  const checkoutNote = () => {
    const parts = [note.trim()]
    if (orderType === 'delivery' && deliveryAddr.notes.trim()) {
      parts.push(`Delivery notes: ${deliveryAddr.notes.trim()}`)
    }
    const joined = parts.filter(Boolean).join(' | ')
    return joined || null
  }

  const submitCheckout = async () => {
    setFormError(null)
    if (orderType === 'delivery') {
      const addrBlockers = validateDeliveryAddressFields(deliveryAddr)
      if (addrBlockers.length) {
        setFormError(addrBlockers)
        return
      }
    }
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
        delivery_address:
          orderType === 'delivery'
            ? composeDeliveryAddressLine(deliveryAddr)
            : null,
        delivery_dropoff:
          orderType === 'delivery'
            ? {
                street: deliveryAddr.street,
                unit: deliveryAddr.unit || null,
                city: deliveryAddr.city,
                state: deliveryAddr.state,
                postal: deliveryAddr.postal,
                country: deliveryAddr.country || 'CA',
                phone: phone.trim() || null,
                name: name.trim() || null,
                notes: deliveryAddr.notes || null,
              }
            : null,
        note: checkoutNote(),
        payment_preference: paymentPreference,
        checkout_key: checkoutKey,
        uber_quote_id: orderType === 'delivery' ? uberQuoteId : null,
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
    if (orderType === 'delivery') {
      const addrBlockers = validateDeliveryAddressFields(deliveryAddr)
      if (addrBlockers.length) {
        setFormError(addrBlockers)
        return
      }
    }
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
        delivery_address:
          orderType === 'delivery'
            ? composeDeliveryAddressLine(deliveryAddr)
            : null,
        delivery_dropoff:
          orderType === 'delivery'
            ? {
                street: deliveryAddr.street,
                unit: deliveryAddr.unit || null,
                city: deliveryAddr.city,
                state: deliveryAddr.state,
                postal: deliveryAddr.postal,
                country: deliveryAddr.country || 'CA',
                phone: phone.trim() || null,
                name: name.trim() || null,
                notes: deliveryAddr.notes || null,
              }
            : null,
        note: checkoutNote(),
        payment_preference: paymentPreference,
        checkout_key: checkoutKey,
        uber_quote_id: orderType === 'delivery' ? uberQuoteId : null,
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
      if (res.status === 'awaiting_payment' || res.summary.checkout_url) {
        if (res.summary.checkout_session_id) {
          saveStorePayPending({
            checkout_session_id: res.summary.checkout_session_id,
            summary: res.summary,
          })
        }
        skipAutoOpenCheckout.current = false
        setPayReturnNote(null)
        setPane('awaiting_payment')
      } else {
        clearStorePayPending()
        setPane('placed')
      }
      cart.clear()
    } catch {
      setFormError(['Could not reach the server. Is the token server running?'])
    } finally {
      setSubmitting(false)
    }
  }

  const startNewOrder = () => {
    clearStorePayPending()
    setPane('cart')
    setSummary(null)
    setReceiptUrl(null)
    setPaymentPollTimedOut(false)
    setPayReturnNote(null)
    setFormError(null)
    setNote('')
    setDeliveryAddr(EMPTY_DELIVERY_ADDRESS)
    setUberQuoteId(null)
    setUberQuoteFee(null)
    setUberQuoteMinutes(null)
    setQuoteHint(null)
    setCheckoutKey(
      typeof crypto !== 'undefined' && crypto.randomUUID
        ? crypto.randomUUID()
        : `store_${Date.now()}_${Math.random().toString(36).slice(2)}`,
    )
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
    pane === 'awaiting_payment' ||
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
                : pane === 'awaiting_payment'
                  ? 'Complete payment'
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
                <div className="store-address-block">
                  <p className="store-address-heading">Delivery address</p>
                  <label className="store-field">
                    <span>Street</span>
                    <input
                      type="text"
                      value={deliveryAddr.street}
                      onChange={(e) =>
                        setDeliveryAddr((a) => ({ ...a, street: e.target.value }))
                      }
                      autoComplete="street-address"
                      placeholder="99 Wye Rd"
                    />
                  </label>
                  <label className="store-field">
                    <span>Unit / suite (optional)</span>
                    <input
                      type="text"
                      value={deliveryAddr.unit}
                      onChange={(e) =>
                        setDeliveryAddr((a) => ({ ...a, unit: e.target.value }))
                      }
                      autoComplete="address-line2"
                      placeholder="#31"
                    />
                  </label>
                  <div className="store-address-row">
                    <label className="store-field">
                      <span>City</span>
                      <input
                        type="text"
                        value={deliveryAddr.city}
                        onChange={(e) =>
                          setDeliveryAddr((a) => ({ ...a, city: e.target.value }))
                        }
                        autoComplete="address-level2"
                        placeholder="Sherwood Park"
                      />
                    </label>
                    <label className="store-field store-field-narrow">
                      <span>Province</span>
                      <input
                        type="text"
                        value={deliveryAddr.state}
                        onChange={(e) =>
                          setDeliveryAddr((a) => ({
                            ...a,
                            state: e.target.value.toUpperCase(),
                          }))
                        }
                        autoComplete="address-level1"
                        placeholder="AB"
                        maxLength={2}
                      />
                    </label>
                  </div>
                  <div className="store-address-row">
                    <label className="store-field">
                      <span>Postal code</span>
                      <input
                        type="text"
                        value={deliveryAddr.postal}
                        onChange={(e) =>
                          setDeliveryAddr((a) => ({
                            ...a,
                            postal: e.target.value.toUpperCase(),
                          }))
                        }
                        autoComplete="postal-code"
                        placeholder="T8B 1C9"
                      />
                    </label>
                    <label className="store-field store-field-narrow">
                      <span>Country</span>
                      <input
                        type="text"
                        value={deliveryAddr.country}
                        onChange={(e) =>
                          setDeliveryAddr((a) => ({
                            ...a,
                            country: e.target.value.toUpperCase(),
                          }))
                        }
                        autoComplete="country"
                        placeholder="CA"
                        maxLength={2}
                      />
                    </label>
                  </div>
                  <label className="store-field">
                    <span>Delivery notes (optional)</span>
                    <input
                      type="text"
                      value={deliveryAddr.notes}
                      onChange={(e) =>
                        setDeliveryAddr((a) => ({ ...a, notes: e.target.value }))
                      }
                      placeholder="Buzzer, gate code, leave at door…"
                    />
                  </label>
                </div>
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
                {payNowEnabled && (
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
                )}
              </div>
              <p className="store-pay-note">
                {!payNowEnabled
                  ? orderType === 'delivery'
                    ? 'Pay when your order arrives.'
                    : 'Pay when you pick up.'
                  : paymentPreference === 'now'
                    ? 'Pay online after you place — secure Clover checkout page (link expires in about 15 minutes).'
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
                    <span>Delivery{quoteLoading ? '…' : ''}</span>
                    <span>${displayDelivery.toFixed(2)}</span>
                  </div>
                )}
                {orderType === 'delivery' && quoteHint && (
                  <p className="store-pay-note store-quote-hint">{quoteHint}</p>
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
                Prices confirmed.{' '}
                {(summary.payment_preference ?? paymentPreference) === 'now'
                  ? 'Next: pay online — we send the order to the kitchen after payment.'
                  : summary.order_type === 'delivery'
                    ? 'Ready to place — pay when it arrives.'
                    : 'Ready to place — pay at pickup.'}
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
                  {submitting
                    ? (summary.payment_preference ?? paymentPreference) === 'now'
                      ? 'Starting payment…'
                      : 'Placing…'
                    : (summary.payment_preference ?? paymentPreference) === 'now'
                      ? 'Pay now'
                      : 'Place order'}
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

          {pane === 'awaiting_payment' && summary && (
            <div className="store-placed">
              <p className="store-placed-banner">
                Complete payment to send your order to the kitchen.
              </p>
              {payReturnNote && (
                <p className="store-pay-note">{payReturnNote}</p>
              )}
              <ul className="store-cart-lines">
                {summary.items.map((line) => {
                  const img = lineImage(line.id)
                  return (
                    <li
                      key={`${line.id}-${line.modifiers.join('-')}-pay`}
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
              <div className="store-cart-footer">
                <div className="ot-row ot-total">
                  <span>Total</span>
                  <span>${summary.total.toFixed(2)}</span>
                </div>
                {summary.checkout_url && (
                  <a
                    className="store-checkout-btn ready store-pay-now-link"
                    href={summary.checkout_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Open secure checkout
                  </a>
                )}
                <p className="store-pay-note">
                  {paymentPollTimedOut
                    ? 'Still waiting for payment. Open the checkout link again if it expired (~15 min). Your order is not sent to the kitchen until payment succeeds.'
                    : 'Pay on the Clover page. This screen updates when payment is confirmed — then we place your order.'}
                </p>
                <button
                  type="button"
                  className="store-back-btn"
                  onClick={startNewOrder}
                >
                  Cancel / new order
                </button>
              </div>
            </div>
          )}

          {pane === 'placed' && summary && (
            <div className="store-success" role="status" aria-live="polite">
              <div className="store-success-hero">
                <div className="store-success-check" aria-hidden>
                  <svg viewBox="0 0 72 72" className="store-success-check-svg">
                    <circle
                      className="store-success-ring"
                      cx="36"
                      cy="36"
                      r="30"
                      fill="none"
                    />
                    <path
                      className="store-success-tick"
                      fill="none"
                      d="M22 37.5 L31.5 47 L50 26"
                    />
                  </svg>
                </div>
                <h3 className="store-success-title">Order placed!</h3>
                <p className="store-success-sub">
                  {summary.order_type === 'delivery' &&
                  summary.uber_dispatch_required
                    ? 'The kitchen has your order. The restaurant is arranging delivery; no courier is confirmed yet.'
                    : summary.order_type === 'delivery' &&
                        summary.uber_tracking_url
                      ? 'The kitchen has your order and your courier is arranged.'
                      : (summary.payment_preference ?? paymentPreference) ===
                          'now'
                        ? 'Payment received. The kitchen has your order.'
                        : summary.order_type === 'delivery'
                          ? 'We got it — pay when it arrives.'
                          : 'We got it — pay when you pick up.'}
                </p>
                {summary.order_id && (
                  <div className="store-success-id">
                    <span className="store-success-id-label">Order ID</span>
                    <strong>{summary.order_id}</strong>
                  </div>
                )}
                {summary.eta && (
                  <div className="store-success-eta">
                    Ready in about <strong>{summary.eta}</strong>
                  </div>
                )}
                {summary.uber_tracking_url && (
                  <a
                    className="store-checkout-btn ready store-pay-now-link"
                    href={summary.uber_tracking_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Track delivery
                  </a>
                )}
                <div className="store-success-pills">
                  <span className="store-success-pill">
                    {summary.order_type === 'delivery' ? 'Delivery' : 'Pickup'}
                  </span>
                  <span
                    className={
                      (summary.payment_preference ?? paymentPreference) === 'now'
                        ? 'store-success-pill is-paid'
                        : 'store-success-pill'
                    }
                  >
                    {(summary.payment_preference ?? paymentPreference) === 'now'
                      ? 'Paid online'
                      : summary.order_type === 'delivery'
                        ? 'Pay on delivery'
                        : 'Pay at pickup'}
                  </span>
                </div>
              </div>

              <div className="store-success-body">
                <ul className="store-cart-lines store-success-lines">
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

                <div className="store-validated-meta store-success-meta">
                  <div>
                    {summary.customer.name} · {summary.customer.phone}
                  </div>
                  {summary.delivery_address && (
                    <div>{summary.delivery_address}</div>
                  )}
                </div>

                <div className="store-cart-footer store-success-footer">
                  <div className="ot-row ot-total">
                    <span>Total</span>
                    <span>${summary.total.toFixed(2)}</span>
                  </div>
                  {receiptUrl && (
                    <a
                      className="store-checkout-btn ready store-pay-now-link"
                      href={receiptUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      View receipt
                    </a>
                  )}
                  <button
                    type="button"
                    className="store-checkout-btn ready"
                    onClick={startNewOrder}
                  >
                    New order
                  </button>
                </div>
              </div>
            </div>
          )}
          </aside>
        </div>
      </div>
    </div>
  )
}
