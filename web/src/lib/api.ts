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
