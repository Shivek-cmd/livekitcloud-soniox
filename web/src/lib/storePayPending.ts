import type { StoreCheckoutSummary } from './api'

/** Survives Clover redirect into a new tab (sessionStorage would not). */
export const STORE_PAY_PENDING_KEY = 'store_pay_pending'
export const VOICE_ACTIVE_TAB_KEY = 'voice_active_tab'

export type StorePayPending = {
  checkout_session_id: string
  summary: StoreCheckoutSummary
  saved_at: number
}

export function saveStorePayPending(pending: {
  checkout_session_id: string
  summary: StoreCheckoutSummary
}): void {
  const sid = (pending.checkout_session_id || '').trim()
  if (!sid || !pending.summary) return
  try {
    const payload: StorePayPending = {
      checkout_session_id: sid,
      summary: pending.summary,
      saved_at: Date.now(),
    }
    localStorage.setItem(STORE_PAY_PENDING_KEY, JSON.stringify(payload))
    localStorage.setItem(VOICE_ACTIVE_TAB_KEY, 'store')
  } catch {
    /* ignore quota / private mode */
  }
}

export function loadStorePayPending(): StorePayPending | null {
  try {
    const raw = localStorage.getItem(STORE_PAY_PENDING_KEY)
    if (!raw) return null
    const data = JSON.parse(raw) as StorePayPending
    if (!data?.checkout_session_id || !data?.summary) return null
    // Drop stale pending after 2 hours
    if (data.saved_at && Date.now() - data.saved_at > 2 * 60 * 60 * 1000) {
      clearStorePayPending()
      return null
    }
    return data
  } catch {
    return null
  }
}

export function clearStorePayPending(): void {
  try {
    localStorage.removeItem(STORE_PAY_PENDING_KEY)
  } catch {
    /* ignore */
  }
}

export function stripStorePayQueryParams(): void {
  try {
    const url = new URL(window.location.href)
    if (!url.searchParams.has('store_pay') && !url.searchParams.has('tab')) {
      return
    }
    url.searchParams.delete('store_pay')
    url.searchParams.delete('tab')
    const next = url.pathname + (url.search ? url.search : '') + url.hash
    window.history.replaceState({}, '', next)
  } catch {
    /* ignore */
  }
}
