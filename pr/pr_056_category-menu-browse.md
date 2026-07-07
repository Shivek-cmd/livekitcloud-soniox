# PR 056 — Category-wise menu browse (production)

## Branch
`pr_056_category-menu-browse`

## What This PR Does

Implements **production-grade category / family browse** so when a caller asks
vaguely — *"what fish do you have?"*, *"mithai kya hai?"*, *"desserts?"*,
*"paneer dishes?"* — Sierra **lists real options from the menu** instead of
guessing one dish or saying "not on our menu."

Closes **Tier B backlog B-2** (`docs/plan/10-voice-quality-tier-b.md`).

### Relationship to PR #91 (fish-fix, merged)

PR #91 added `disambiguation_options()` — when `add_to_order("fish")` is called,
the tool **blocks the add** and tells the LLM to ask curry vs pakora. That stops
the worst guess-on-add bug but is **reactive** (only fires when the model tries
to add). This PR adds **proactive browse**:

| Situation | PR #91 | PR 056 |
|-----------|--------|--------|
| Caller: "one fish" → model calls `add_to_order` | Blocked, ask which | Same (keep) |
| Caller: "what fish do you have?" | LLM may or may not call `search_menu_items` | **Code-owned browse reply** |
| Caller: "mithai kya hai?" | Returns "no items found" | Maps `mithai` → Desserts, lists items |
| Caller: "desserts?" | Partial (substring on item names) | Full category list (up to 2 spoken) |

---

## Problem statement (live evidence)

| Caller says | Current behaviour | Expected |
|-------------|-------------------|----------|
| `ਇੱਕ ਫਿਸ਼ ਆਰਡਰ` | Was: guessed Fish Curry (fixed by #91 on add) | Ask curry or pakora |
| `ਮਿੱਠੇ ਚ ਕੀ ਹੈ?` / `mithai` | `search_menu_items` → no results | Gulab Jamun, Gajar Halwa, … |
| `sweet` | Matches **Sweet Lassi** (item name) | Desserts category |
| `what desserts do you have?` | Depends on LLM calling tool | Always lists 2 desserts |
| `paneer dishes?` | Item substring search (OK-ish) | Consistent family browse |
| `drinks?` | Partial | All drink types, capped at 2 spoken |

**Root cause:** `search_menu()` only does substring match on item
name/alias/category text. There is no **category alias map**, and
`MenuCache.list_by_category()` exists but is **never wired to voice**.

---

## Design (production)

### 1. Category & dish-family registry — `restaurant/menu_browse.py` (new)

Single source of truth for browse queries. Two lookup types:

**A. Clover category browse** — maps caller terms → `category_name` in cache:

```python
CATEGORY_ALIASES = {
    "desserts": ["dessert", "desserts", "mithai", "mitha", "sweet", "sweets",
                   "ਮਿੱਠਾ", "ਮਿੱਠੇ", "ਮਿਠਾਈ", "हलवा", "मिठाई"],
    "drinks": ["drink", "drinks", "beverage", "peena", "ਸ਼ਰਬਤ", "पीना"],
    "starters": ["starter", "starters", "snack", "snacks", "appetizer",
                 "ਸ਼ੁਰੂਆਤ", "नाश्ता"],
    "veg_mains": ["veg main", "vegetarian", "sabzi", "ਸਬਜ਼ੀ"],
    "nonveg_mains": ["non veg", "nonveg", "chicken", "mutton", "goat"],
    "breads_rice": ["naan", "roti", "bread", "rice", "chawal", "ਨਾਨ", "ਰੋਟੀ"],
    "combos": ["combo", "combos", "platter", "thali", "ਕੰਬੋ"],
    "tandoor": ["tandoor", "tikka", "kebab", "grill"],
    "extras": ["side", "sides", "extra", "raita", "papad"],
}
```

Keys map to Clover `category_name` values from cache
(`Desserts`, `Drinks`, `Starters & Snacks`, etc.).

**B. Dish-family browse** — when category is too broad or items span categories:

```python
DISH_FAMILIES = {
    "fish": {
        "items": ["Amritsari Fish Pakora", "Punjabi Fish Curry"],
        # aliases: fish, machhi, machi, ਮੱਛੀ, ਫਿਸ਼, मछी
    },
    "paneer": {
        "match": "paneer",  # all items with paneer in name/alias
    },
    "chicken": {
        "match": "chicken",
    },
    ...
}
```

`fish` is a **family**, not a Clover category (curry = Non-Veg Mains,
pakora = Starters). Reuse logic already proven in PR #91
`disambiguation_options("fish")`.

### 2. Unified `browse_menu(query)` — `restaurant/menu_provider.py`

New function; `search_menu()` becomes a thin wrapper (backward compatible).

```
browse_menu(query):
  1. normalize query (fold script, strip courtesy words)
  2. if query matches CATEGORY_ALIASES → list_by_category(category, limit=6)
  3. elif query matches DISH_FAMILIES → resolve family item list
  4. elif find_item(query) abstains AND disambiguation_options >= 2 → use those
  5. else → existing cache.search() fallback
  6. format result: max 2 items spoken, rest as INTERNAL for LLM
```

**Spoken format** (one sentence, no numbered list — matches existing tool style):

```
Browse result for 'mithai': Gajar Halwa → say "ਗਾਜਰ ਦਾ ਹਲਵਾ" |
Gulab Jamun (2 pcs) → say "ਗੁਲਾਬ ਜਾਮੁਨ".
Mention at most TWO in ONE casual sentence. Ask which they'd like.
(+3 more in Desserts — INTERNAL, offer if they want more)
```

### 3. Code-owned browse handler — `agent.py`

New `_try_menu_browse()` — runs **before** `_try_auto_add()` on collecting phases.

**Trigger conditions** (any of):
- `UserIntent.ASK_AVAILABILITY` AND query looks like category/family
  (`is_category_browse_query(text)`)
- `UserIntent.GENERAL` + browse phrases:
  `what do you have`, `kya hai`, `ਕੀ ਹੈ`, `options`, `types`, `menu`
- `find_item` abstains + `disambiguation_options >= 2` + **no add verb**
  (distinguish "fish" browse vs "one fish" add)

**Action:**
1. Call `menu_provider.browse_menu(extracted_query)`
2. Build short spoken line via `format_browse_reply(options, lang)` in
   `conversation.py` (cashier style, max 2 dishes)
3. `session.say()` + `StopResponse()` — same pattern as auto-add

**Do NOT add to cart.** Browse only.

### 4. Intent helper — `restaurant/conversation.py`

- `is_category_browse_query(text) -> bool`
- `extract_browse_query(text) -> str | None` — strips
  "what do you have", "kya hai", "ਕੀ ਹੈ", "options for", etc.
- Extend `_AVAIL_RE` or add `_BROWSE_RE` for:
  `what X do you have`, `X options`, `X types`, `X menu`

**Critical:** `"ਇੱਕ ਫਿਸ਼ ਆਰਡਰ"` must stay `ADD_ITEM`, not browse.
Browse = question; add = imperative (`ਚਾਹੀਦਾ`, `ਕਰ ਦਿਓ`, `order`, qty + dish).

### 5. Tool path alignment

`search_menu_items` tool → call `browse_menu()` instead of raw `search()`.
`check_menu_item` disambiguation path unchanged (PR #91).

`add_to_order` disambiguation unchanged (PR #91).

### 6. Turn guidance injection — `order_flow.py`

When last turn was browse (store `last_browse_topic` in flow state):
inject `[ORDER STATUS]` hint: *"Waiting for customer to pick from {topic}
options — do NOT add until they name one."*

---

## Files Added

### `restaurant/menu_browse.py`
- `CATEGORY_ALIASES`, `DISH_FAMILIES` constants
- `resolve_browse_target(query) -> BrowseTarget | None`
- `BrowseTarget` dataclass: `kind` (category|family|disambiguation), `label`, `items`

### `tests/test_menu_browse.py`
- Category alias resolution (mithai → Desserts)
- Family browse (fish → 2 fish dishes)
- Browse vs add intent separation
- Spoken format obeys 2-item cap
- Regression: `sweet` → desserts not Sweet Lassi

---

## Files Modified

### `restaurant/menu_provider.py`
- Add `browse_menu(query) -> str`
- Refactor `search_menu()` to delegate to `browse_menu()`
- Wire `list_by_category()` through browse path

### `restaurant/conversation.py`
- `is_category_browse_query()`, `extract_browse_query()`
- `format_browse_reply(options, lang) -> str`

### `agent.py`
- `_try_menu_browse()` handler in `on_user_turn` pipeline
- `search_menu_items` tool uses `browse_menu()`

### `restaurant/order_flow.py`
- `last_browse_topic` state + turn guidance when set

### `restaurant/prompts.py`
- One line: *"For 'what X do you have?' the system may answer automatically —
  do NOT repeat the list."*

---

## Files NOT Modified
- `data/menu_cache_bizbull.json` — no menu data changes
- `data/clover_voice_labels.json` — alias fixes stay separate data PRs
- Auto-add / checkout ladder / `place_order()` gates
- Web menu panel (`catalog()` already works for UI)

---

## Test plan

```bash
PYTHONPATH=. pytest tests/test_menu_browse.py tests/test_menu_match.py \
  tests/test_conversation.py -q
```

### Unit cases
| Query | Expected browse result |
|-------|------------------------|
| `mithai` | ≥2 Desserts items |
| `ਮਿੱਠੇ ਚ ਕੀ ਹੈ` | Desserts items |
| `desserts` | Desserts items |
| `sweet` | Desserts (NOT Sweet Lassi) |
| `fish` | Fish Pakora + Fish Curry |
| `machhi` | Fish Pakora + Fish Curry |
| `paneer` | ≥2 paneer dishes |
| `drinks` | Drinks category items |
| `unicorn` | no results |

### Intent separation
| Utterance | Intent | Handler |
|-----------|--------|---------|
| `what fish do you have` | ASK_AVAILABILITY / browse | `_try_menu_browse` |
| `ਇੱਕ ਫਿਸ਼ ਆਰਡਰ ਕਰਨੀ` | ADD_ITEM | add path + #91 disambiguation |
| `fish pakora` | ADD_ITEM | direct add |

### Live call script
1. "What desserts do you have?" → hear 2 dessert names, no add
2. "Gulab Jamun" → adds one
3. "Fish?" → hear curry + pakora, no add
4. "Pakora" → adds Fish Pakora (not Mixed Pakora Platter unless they say that)
5. "Mithai?" → hear dessert names

---

## Rollout / VPS

```bash
cd /opt/livekit-sarvam && git pull origin main && uv sync
systemctl restart restaurant-agent
```

No new env vars required. Optional kill switch:
`MENU_BROWSE_ENABLED=0` (default 1) if we need to disable code-owned browse.

---

## Risk & mitigations

| Risk | Mitigation |
|------|------------|
| Browse fires on add intent | Require no add-imperative; test Punjabi add phrases |
| Lists too many items (phone fatigue) | Hard cap 2 spoken, rest INTERNAL |
| `sweet` → wrong category | Explicit alias → Desserts, exclude drink names |
| Duplicates PR #91 fish logic | Reuse `disambiguation_options()` inside `browse_menu()` |
| Over-talking after browse | `last_browse_topic` guidance tells LLM not to repeat |

---

## Post-merge checklist
- [ ] Update `pr/README.md` index
- [ ] Update `docs/HANDOFF.md` — mark B-2 done
- [ ] Deploy VPS + one live test per category family
