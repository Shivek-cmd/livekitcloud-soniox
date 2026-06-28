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
