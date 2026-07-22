/** Local Store cart (client-only). Server revalidates on checkout in S3+. */

export const SPICE_LEVELS = [
  'Mild',
  'Medium',
  'Spicy',
  'Extra Spicy',
] as const

export type SpiceLevel = (typeof SPICE_LEVELS)[number]

export interface StoreCartLine {
  /** Stable key: item id + spice (or bare id). */
  key: string
  id: string
  name: string
  unitPrice: number
  qty: number
  modifiers: string[]
  imageUrl?: string | null
}

export interface AddToStoreCartInput {
  id: string
  name: string
  unitPrice: number
  qty?: number
  spice?: SpiceLevel | null
  imageUrl?: string | null
}

export function lineKey(id: string, spice?: string | null): string {
  const s = (spice || '').trim()
  return s ? `${id}::${s.toLowerCase()}` : id
}

export function addToStoreCart(
  lines: StoreCartLine[],
  input: AddToStoreCartInput,
): StoreCartLine[] {
  const qty = Math.max(1, input.qty ?? 1)
  const spice = input.spice ?? null
  const modifiers = spice ? [spice] : []
  const key = lineKey(input.id, spice)
  const existing = lines.find((l) => l.key === key)
  if (existing) {
    return lines.map((l) =>
      l.key === key ? { ...l, qty: l.qty + qty } : l,
    )
  }
  return [
    ...lines,
    {
      key,
      id: input.id,
      name: input.name,
      unitPrice: input.unitPrice,
      qty,
      modifiers,
      imageUrl: input.imageUrl ?? null,
    },
  ]
}

export function setStoreCartQty(
  lines: StoreCartLine[],
  key: string,
  qty: number,
): StoreCartLine[] {
  if (qty <= 0) return lines.filter((l) => l.key !== key)
  return lines.map((l) => (l.key === key ? { ...l, qty } : l))
}

export function removeStoreCartLine(
  lines: StoreCartLine[],
  key: string,
): StoreCartLine[] {
  return lines.filter((l) => l.key !== key)
}

export function storeCartSubtotal(lines: StoreCartLine[]): number {
  return lines.reduce((sum, l) => sum + l.unitPrice * l.qty, 0)
}

export function storeCartItemCount(lines: StoreCartLine[]): number {
  return lines.reduce((sum, l) => sum + l.qty, 0)
}
