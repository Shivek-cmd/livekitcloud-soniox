/** Shared menu category ordering for voice LiveMenu + Store browse. */

export const CATEGORY_ORDER = [
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

export interface NamedCategory {
  name: string
}

export function sortCategories<T extends NamedCategory>(categories: T[]): T[] {
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
