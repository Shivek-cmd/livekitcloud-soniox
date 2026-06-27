# Clover Inventory & menu (for voice ordering)

> Captured 2026-06-27 from Clover Platform Docs (`working-with-inventory`,
> `managing-modifier-groups-modifiers`, `managing-item-availability`, `webhooks`).
> Why we care: Sierra's menu must come from **Clover as source of truth**, not `restaurant/menu.py`.

## Inventory terminology

| Term | Meaning |
|---|---|
| **Item** | Menu product/service — `name`, `price` (cents), `hidden`, `available`, categories |
| **Category** | Visual grouping in Register (Appetizers, Mains, Drinks) |
| **Modifier group** | Set of options for an item (Spice Level, Toppings); `minRequired`, `maxAllowed` |
| **Modifier** | Single option in a group — `name`, `price` (cents) |
| **Item group / variants** | Same style in different sizes/colors (retail; less common for restaurants) |
| **Tags / labels** | Reporting + kitchen printer routing (`expand=item.tags`) |
| **Item stock** | Quantity tracking; `autoManage`, `stockCount`, `stockAlertThreshold` |

Merchants manage inventory via **Clover Inventory app** or **Merchant Dashboard**.
Sandbox: bulk import from Excel sample file.

## Key REST endpoints

All under `https://{base}/v3/merchants/{mId}/...`

| Operation | Endpoint | Notes |
|---|---|---|
| List items | `GET /items` | Paginate; use `filter`, `expand` |
| Get item + modifiers | `GET /items/{itemId}?expand=modifierGroups` | Required for voice modifier prompts |
| List categories | `GET /categories` | Build menu sections for LLM context |
| List modifier groups | `GET /modifier_groups` | |
| Modifiers in group | `GET /modifier_groups/{groupId}/modifiers` | |
| Item ↔ modifier link | `POST /item_modifier_groups` | Setup only (merchant-side) |
| Item stock (all) | `GET /item_stocks` | |
| Item stock (one) | `GET /item_stocks/{itemId}` | |
| Update stock | `POST /item_stocks/{itemId}` | `quantity`, `stockAlertThreshold` |
| Mark unavailable | `POST /items/{itemId}` | `"available": false` (does not delete item) |
| Low stock filter | `GET /items?expand=itemStock&filter=lowStock=true` | |

Prices in API responses are **integer cents** (`price: 1295` = $12.95).

## Modifier model (critical for voice)

Example: `Caesar Salad` item linked to `Salad Add-in` modifier group containing `Tofu`, `Avocado`.

```
Item (Greek Salad)
  └── ModifierGroup (Salad Add-in)
        ├── Modifier (Tofu)   +$1.00
        └── Modifier (Avocado) +$1.00
```

- Groups can enforce **min/max** selections (Register app enforces; we must too for voice).
- When building orders, modifiers attach to **line items** as `modifications[]`.
- Custom modifier names/prices in atomic orders can **override** inventory defaults if both `name`
  and `amount` are passed without `modId` — but for production use **real modifier IDs**.

Expand pattern for menu build:
```
GET /items/{itemId}?expand=modifierGroups
GET /modifier_groups/{groupId}?expand=modifiers   # if needed
```

## Availability & stock (production edge cases)

Items have multiple availability signals:

| Field | Meaning |
|---|---|
| `hidden` | Hidden from Register (still in inventory) |
| `available` | Can be ordered (`false` = temporarily unavailable / "86'd") |
| `autoManage` | Clover tracks stock automatically |
| `itemStock.quantity` | Current stock count |
| `stockAlertThreshold` | Low-stock alert level |

**Sierra must handle:**
- Item `available: false` → "Sorry, that's not available right now."
- `autoManage: true` + `quantity <= 0` → out of stock mid-shift.
- Modifier availability — separate endpoint (`manage-item-modifiers-availability`); check before order submit.

**Do not** update stock via `POST /items/{id}` — use `item_stocks` endpoints.

## Menu sync strategy (for planning)

Recommended approach for Sierra multi-tenant:

1. **Initial full sync** — paginate `GET /items?expand=modifierGroups,categories` (+ stock).
2. **Webhook-driven delta** — on `I`, `IG`, `IM`, `IC` events, re-fetch affected objects.
3. **Local voice menu cache** — transform Clover catalog → compact LLM-friendly structure:
   - Canonical item names + aliases (voice: "paneer tikka" ↔ Clover item name).
   - Modifier groups with allowed choices and prices.
   - Category groupings for recommendations.
4. **TTL fallback** — periodic re-sync (e.g. every 15–30 min) if webhook missed.

**Avoid** polling inventory on every phone call — rate limits + latency.

Use `modifiedTime` filter for incremental: `?filter=modifiedTime>=...`

## Voice-specific menu concerns

- Clover item names may differ from spoken Punjabi/English ("Chole Bhature" vs "Bhatura with Chole").
  Plan a **name alias layer** per tenant (not in Clover API — our config).
- Long menus → don't inject full catalog into system prompt; use **tool-based lookup** or
  category-scoped retrieval.
- Pass menu item names in Soniox STT `context` field for better recognition (see soniox doc).
- Prices: Clover calculates authoritative totals; Sierra speaks estimates but **confirms Clover total**
  at checkout step.

## Punjabi TTS — Clover name vs Gurmukhi speech label

Clover inventory **`name`** is usually English or Roman text (`Chole Bhature`, `Paneer Tikka`).
Soniox TTS with `language="pa"` **mispronounces Roman dish names** but speaks **Gurmukhi script**
correctly (`ਛੋਲੇ ਭਟੂਰੇ`).

This is already solved in today's static menu — each item has two fields:

```python
{"name": "Chole Bhature", "punjabi": "ਛੋਲੇ ਭਟੂਰੇ", "price": 14}
```

When menu comes from Clover, we keep the same **split**:

| Field | Source | Used for |
|---|---|---|
| `clover_item_id` | Clover API | Order submit (atomic order) |
| `clover_name` | Clover `item.name` | Receipt, kitchen, LLM matching |
| `speak_as` | Tenant config (Gurmukhi) | **Soniox TTS output** |
| `aliases` | Tenant config (Roman/Hindi) | STT + LLM fuzzy match ("chhole bhature") |

```
Clover sync                    Voice cache (per item)
─────────────                  ──────────────────────
name: "Chole Bhature"    →     clover_name: "Chole Bhature"
id:   "ABC123..."        →     clover_item_id: "ABC123..."
                               speak_as: "ਛੋਲੇ ਭਟੂਰੇ"     ← YOU configure (or import from menu.py)
                               aliases: ["chhole", "chole bhature", "bhature"]
```

### Rules for Sierra

1. **Orders to Clover** always use `clover_item_id` + `clover_name` — never Gurmukhi in API payloads.
2. **Spoken replies** use `speak_as` when present; fall back to `clover_name` only if missing (sounds worse).
3. **LLM system prompt** instructs: when saying dish names aloud, use the `speak_as` field from tool responses.
4. **STT context** (Soniox `context` param): include top `aliases` + Gurmukhi names so recognition improves.
5. **New Clover items** without `speak_as` → Sierra can still take orders; owner adds Gurmukhi label in tenant config (Phase 8b admin / JSON file).

### Pilot / sandbox

- Copy Gurmukhi labels from existing `restaurant/menu.py` where items match.
- Sandbox Clover items can stay English; **speech layer lives in our cache**, not in Clover.
- Optional later: merchant UI to edit `speak_as` per item (SaaS onboarding).

### Modifiers

Same pattern: Clover modifier `name` = `"Medium Spicy"` → `speak_as` = `"ਮੀਡੀਅਮ ਸਪਾਈਸੀ"` or keep English for spice levels (often spoken in English on Canadian Punjabi calls anyway — product decision per tenant).

---

| Event key | Trigger |
|---|---|
| `I` | Item created/updated/deleted |
| `IC` | Category change |
| `IG` | Modifier group change |
| `IM` | Modifier change |

Requires **Read inventory** permission.

## Related docs

- [clover-orders-api.md](clover-orders-api.md) — how items become line items
- [clover-oauth-and-api.md](clover-oauth-and-api.md) — webhooks setup
- [clover-sierra-integration-notes.md](clover-sierra-integration-notes.md) — architecture mapping
