// Same-origin endpoints (Caddy proxies /token, /health, /menu -> token server).
export const TOKEN_URL = '/token'
export const MENU_URL = '/menu'

export interface MenuItem {
  id: string
  name: string
  voice_line: string
  price: number
  veg: boolean
  available: boolean
  has_spice: boolean
  options: string[]
  /** From GET /menu — Clover when synced, else demo Unsplash fill. */
  image_url?: string | null
}

export interface MenuCategory {
  name: string
  items: MenuItem[]
}

export interface MenuCatalog {
  tenant_id: string
  synced_at: string
  item_count: number
  categories: MenuCategory[]
}

export interface TokenResponse {
  token: string
  url: string
  room: string
  identity: string
}

// ── Live order state (pushed by the agent over the `order.state` data topic) ──
export interface OrderItem {
  id: string | null
  name: string
  voice_line: string
  qty: number
  unit_price: number
  line_total: number
  note: string
  modifiers: string[]
}

export type OrderStatus =
  | 'empty'
  | 'building'
  | 'awaiting_contact'
  | 'confirming'
  | 'placed'

export interface OrderState {
  v: number
  status: OrderStatus
  items: OrderItem[]
  order_type: 'pickup' | 'delivery' | null
  delivery_address: string | null
  customer: { name: string | null; phone: string | null }
  subtotal: number
  delivery_charge: number
  total: number
  eta: string | null
  order_id: string | null
}

// Result returned by cart_* RPCs.
export interface CartRpcResult {
  ok: boolean
  error?: string
  needs?: string[]
  state?: OrderState
}

export async function fetchToken(): Promise<TokenResponse> {
  const resp = await fetch(TOKEN_URL)
  if (!resp.ok) throw new Error('Failed to get token')
  return resp.json()
}

export async function fetchMenu(): Promise<MenuCatalog> {
  const resp = await fetch(MENU_URL)
  if (!resp.ok) throw new Error('Failed to load menu')
  return resp.json()
}

export const STORE_CHECKOUT_URL = '/store/checkout'

export interface StoreCheckoutItemPayload {
  id: string
  qty: number
  modifiers: string[]
}

export type StorePaymentPreference = 'later' | 'now'

export interface StoreCheckoutRequest {
  items: StoreCheckoutItemPayload[]
  order_type: 'pickup' | 'delivery'
  customer: { name: string; phone: string }
  delivery_address?: string | null
  note?: string | null
  /** later = pay at pickup/door (default); now = online pay (Hosted Checkout in P2+) */
  payment_preference?: StorePaymentPreference
  place?: boolean
}

export interface StoreCheckoutSummaryLine {
  id: string
  name: string
  voice_line: string
  qty: number
  unit_price: number
  line_total: number
  modifiers: string[]
}

export interface StoreCheckoutSummary {
  items: StoreCheckoutSummaryLine[]
  order_type: 'pickup' | 'delivery'
  customer: { name: string; phone: string }
  delivery_address: string | null
  note: string | null
  payment_preference?: StorePaymentPreference
  /** Set in P2+ when pay-now Hosted Checkout is created */
  checkout_url?: string | null
  checkout_session_id?: string | null
  /** Unix ms from Clover HCO (session ~15 min) */
  checkout_expires_at_ms?: number | null
  subtotal: number
  delivery_charge: number
  total: number
  placed: boolean
  order_id: string | null
  eta?: string | null
  clover_submitted?: boolean
  session_id?: string | null
}

export interface StoreCheckoutResponse {
  ok: boolean
  status: string
  summary?: StoreCheckoutSummary
  blockers?: string[]
  placed?: boolean
  place_requested?: boolean
}

export async function postStoreCheckout(
  body: StoreCheckoutRequest,
): Promise<StoreCheckoutResponse> {
  const resp = await fetch(STORE_CHECKOUT_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = (await resp.json().catch(() => null)) as
    | StoreCheckoutResponse
    | { detail?: StoreCheckoutResponse | string }
    | null

  if (!resp.ok) {
    const detail =
      data && typeof data === 'object' && 'detail' in data ? data.detail : null
    if (detail && typeof detail === 'object' && 'blockers' in detail) {
      return detail as StoreCheckoutResponse
    }
    if (resp.status === 429) {
      return {
        ok: false,
        status: 'rate_limited',
        blockers: [
          'Too many checkout attempts. Please wait a minute and try again.',
        ],
      }
    }
    if (resp.status === 502 || resp.status === 503) {
      return {
        ok: false,
        status: 'invalid',
        blockers: [
          'The restaurant system is temporarily unavailable. Please try again in a moment.',
        ],
      }
    }
    const msg =
      typeof detail === 'string'
        ? detail
        : 'Checkout failed. Please check your details.'
    return { ok: false, status: 'invalid', blockers: [msg] }
  }
  return data as StoreCheckoutResponse
}

export interface StorePaymentStatus {
  checkout_session_id?: string | null
  order_id?: string | null
  status?: string | null
  payment_id?: string | null
  receipt_url?: string | null
  paid_at?: string | null
}

export async function fetchStorePaymentStatus(opts: {
  checkoutSessionId?: string | null
  orderId?: string | null
}): Promise<StorePaymentStatus | null> {
  const params = new URLSearchParams()
  if (opts.checkoutSessionId) {
    params.set('checkout_session_id', opts.checkoutSessionId)
  } else if (opts.orderId) {
    params.set('order_id', opts.orderId)
  } else {
    return null
  }
  const resp = await fetch(`/store/payment-status?${params.toString()}`)
  if (!resp.ok) return null
  const data = (await resp.json()) as {
    found?: boolean
    payment?: StorePaymentStatus | null
  }
  if (!data.found || !data.payment) return null
  return data.payment
}

export async function fetchStoreConfig(): Promise<{ pay_now_enabled: boolean }> {
  try {
    const resp = await fetch('/store/config')
    if (!resp.ok) return { pay_now_enabled: false }
    const data = (await resp.json()) as { pay_now_enabled?: boolean }
    return { pay_now_enabled: Boolean(data.pay_now_enabled) }
  } catch {
    return { pay_now_enabled: false }
  }
}
