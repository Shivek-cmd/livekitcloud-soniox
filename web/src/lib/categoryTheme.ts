/** Category visual themes for Store S6 placeholders (on-brand tokens only). */

export type CategoryTheme =
  | 'starters'
  | 'veg'
  | 'nonveg'
  | 'tandoor'
  | 'combos'
  | 'breads'
  | 'desserts'
  | 'drinks'
  | 'sides'
  | 'default'

const RULES: { match: RegExp; theme: CategoryTheme }[] = [
  { match: /starter|snack/i, theme: 'starters' },
  { match: /vegetarian|veg\b/i, theme: 'veg' },
  { match: /non-?veg|non veg/i, theme: 'nonveg' },
  { match: /tandoor|grill/i, theme: 'tandoor' },
  { match: /combo|platter/i, theme: 'combos' },
  { match: /bread|rice/i, theme: 'breads' },
  { match: /dessert|mithai|sweet/i, theme: 'desserts' },
  { match: /drink|beverage|lassi/i, theme: 'drinks' },
  { match: /extra|side/i, theme: 'sides' },
]

export function categoryTheme(name: string): CategoryTheme {
  for (const rule of RULES) {
    if (rule.match.test(name)) return rule.theme
  }
  return 'default'
}

/** Short label shown on the placeholder tile. */
export function categoryInitials(name: string): string {
  const parts = name
    .replace(/&/g, ' ')
    .split(/\s+/)
    .filter(Boolean)
  if (parts.length === 0) return '?'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[1][0]).toUpperCase()
}
