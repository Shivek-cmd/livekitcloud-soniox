/** Structured Store delivery address (PR 093 P2) — compose one line for Clover/n8n. */

export type StoreDeliveryAddressFields = {
  street: string
  unit: string
  city: string
  state: string
  postal: string
  country: string
  notes: string
}

export const EMPTY_DELIVERY_ADDRESS: StoreDeliveryAddressFields = {
  street: '',
  unit: '',
  city: '',
  state: 'AB',
  postal: '',
  country: 'CA',
  notes: '',
}

const CA_POSTAL_RE =
  /^[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z]\s?\d[ABCEGHJ-NPRSTV-Z]\d$/i

export function normalizeCaPostal(postal: string): string | null {
  const compact = postal.replace(/\s+/g, '').toUpperCase()
  if (compact.length !== 6) return null
  const spaced = `${compact.slice(0, 3)} ${compact.slice(3)}`
  if (!CA_POSTAL_RE.test(spaced)) return null
  return spaced
}

export function composeDeliveryAddressLine(
  addr: StoreDeliveryAddressFields,
): string {
  const street = addr.street.trim()
  const unit = addr.unit.trim()
  const streetPart = unit ? `${street}, ${unit}` : street
  const city = addr.city.trim()
  const state = addr.state.trim().toUpperCase()
  const postalNorm =
    addr.country.trim().toUpperCase() === 'CA'
      ? normalizeCaPostal(addr.postal) || addr.postal.trim().toUpperCase()
      : addr.postal.trim()
  const country = addr.country.trim().toUpperCase() || 'CA'
  return [streetPart, city, `${state} ${postalNorm}`.trim(), country]
    .filter(Boolean)
    .join(', ')
}

/** Client-side blockers before POST /store/checkout (server still revalidates). */
export function validateDeliveryAddressFields(
  addr: StoreDeliveryAddressFields,
): string[] {
  const blockers: string[] = []
  if (addr.street.trim().length < 3) {
    blockers.push('Delivery street is required.')
  }
  if (addr.city.trim().length < 2) {
    blockers.push('Delivery city is required.')
  }
  if (addr.state.trim().length < 2) {
    blockers.push('Delivery province/state is required.')
  }
  const country = addr.country.trim().toUpperCase() || 'CA'
  if (addr.postal.trim().length < 3) {
    blockers.push('Delivery postal/ZIP is required.')
  } else if (country === 'CA' || country === 'CAN' || country === 'CANADA') {
    if (!normalizeCaPostal(addr.postal)) {
      blockers.push('Delivery postal code looks invalid for Canada.')
    }
  }
  return blockers
}
