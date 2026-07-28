# PR 098 — Sierra stops denying dishes that ARE on the menu

## Branch
`pr_098_menu-availability-false-denials`

## What This PR Does

When a caller asked "do you have X?", Sierra repeatedly answered *"we don't have X, but we
have A and B"* — for dishes sitting in the live menu. The same dish then added fine a
moment later. Live-call examples: **Student Combo**, **Veg Lunch Thali**, **Gajar Halwa**.

The tell in the transcript: the denying turns called `search_menu`; the succeeding turn
called `check_menu_item` + `add_item`. Those two tools took different code paths, and only
one of them could see the dish.

### Root cause

`search_menu` → `menu_provider.browse_menu_options` called `resolve_browse_target` **first**,
and that resolver fires on any category alias appearing anywhere in the query — it never
checked whether the query named a specific dish. The whole query collapsed into a category
listing in raw cache order, and `_format_browse_tool_result` speaks only the first two:

| query | resolved to | items returned (category order) |
|---|---|---|
| `student combo` | CATEGORY *Combos & Platters* | Office Party Tray, Non-Veg Deluxe Platter, Family Veg Platter, Couple Combo, **Student Combo** |
| `veg lunch thali` | CATEGORY *Combos & Platters* | (same list — **Veg Lunch Thali Combo** is 7th) |
| `gajar halwa` | CATEGORY *Desserts* | Mango Kulfi, Rasmalai, **Gajar Halwa**, Kheer, Gulab Jamun |

So the dish was **outranked and truncated, never missed**. The model saw a browse result
that omitted the dish it asked about and concluded it was unavailable. `check_menu_item`
worked because it goes through the PR-032 cross-script confidence matcher, which has no
category step at all.

Four contributing factors, all fixed here: the wrong tool was reachable for the job, the
browse path skipped availability-phrase normalization, the "nothing found" strings were
absolute negatives the prompt told the model to relay verbatim, and the masculine Punjabi
`ਹੈਗਾ`/`ਹੈਗੇ` ("is there?") was missing everywhere — only feminine `ਹੈਗੀ` was listed.

## Files Modified

### `restaurant/menu_provider.py`
The core fix.

- **`_named_dish_hit()` (new)** — resolves the one specific dish a query names, via the same
  `find_item_scored` matcher `check_item`/`add_item` use, so browse can never disagree with
  them about whether a dish exists. Scores the **whole utterance** (availability phrasing
  and stopwords removed), deliberately *not* `extract_dish_query`'s n-gram candidates:
  those match `ਮਿਲ` in "ਕੀ ਕੁਝ ਮਿਲ ਜਾਏਗਾ?" to *Malai Kofta*, which would turn a browse into
  a dish the caller never named.
- **`_pin_named()` / `_as_options()` (new)** — put the named dish at the front of every
  branch of `browse_menu_options`, so it can never be truncated away.
- **`browse_menu_options()`** — resolves the specific dish before the category browse, and
  skips the pin when the query is a bare category term (see `is_bare_browse_term` below),
  so "combo"/"dessert"/"paneer" still browse normally.
- **`_format_browse_tool_result()`** — a pinned hit now yields a `YES — '<query>' IS on the
  menu` result that tells the model to confirm we have it *first*, then optionally offer one
  sibling. The empty result is no longer an absolute negative: it states that a browse miss
  is not proof of absence and to call `check_menu_item` before saying anything. The
  `No menu items found` prefix is preserved — `search_menu` keys its `menu_search_empty`
  analytics event off that substring. Truncated extras are now **named** for the model
  instead of `(+3 more)`, so it can never conclude a hidden item is absent.
- **`check_item()`** — the two `'X' is not on our menu.` dead-ends now carry guidance to ask
  the caller to repeat or offer something close, rather than flatly denying.
- **Availability regexes** — `ਹੈਗਾ`, `ਹੈਗੇ`, `ਹੈਗੇ ਨੇ`, `haiga`, `hainge` added to
  `_AVAIL_QUERY_SUFFIX_RE`, `_AVAIL_Q_RE`, and `_is_availability_question`.

### `restaurant/menu_browse.py`
- **`BrowseTarget.matched_alias` (new field)** — records which alias won, so callers can tell
  a bare category term from a dish that merely contains one.
- **`is_bare_browse_term()` (new)** — true when the query is *only* the category term
  ("combo", "thali", "rice") and names nothing beyond it. `student combo` and `rice pudding`
  carry a word the alias doesn't cover, so they resolve to their dish instead.
- **Dessert aliases** — added `ਡਿਜ਼ਰਟ` / `ਡਿਸਰਟ`; Soniox transcribes the word with either
  vowel and only the `ਡੈਜ਼ਰਟ` spelling was listed, so dessert questions missed the category.
- **`naan` and `lassi` family specs (new)** — these fell through to their whole category, so
  asking for naan offered *Saffron Rice* and asking for lassi offered *Nimbu Pani*.

### `restaurant/clover/match.py`
- `STOPWORDS` — added `ਹੈਗਾ`/`ਹੈਗੇ`/`ਨੇ`/`haiga`/`hainge` (only feminine `ਹੈਗੀ` was there, so
  `ਹੈਗਾ` scored as a content token and diluted match confidence), plus the question and
  availability verbs `ਕੀ`, `ਮਿਲ`, `ਮਿਲੇਗਾ`, `ਜਾਏਗਾ`, `ਤੁਹਾਡੇ`, `ਕਿਹੜਾ` and their Devanagari
  equivalents.

### `restaurant/clover/menu.py`
- `list_by_category()` now filters on `available`, matching `items_by_name_contains` and
  `disambiguation_options`. It could otherwise surface an 86'd dish as available.

### `restaurant/agent/core.py`
Second, independent denial path — an **AMBIGUOUS** refusal was being spoken as a denial.

- `_resolve_menu_item()` now returns a third element, the **refusal kind**
  (`ambiguous` / `not_found` / `unavailable` / `empty`). AMBIGUOUS means the dish *exists*
  and we only failed to pin down which one, so it must never reach the customer as "we don't
  have that".
- `_refusal_kinds` map on the agent, armed alongside `pending_add_refusals` and cleared with it.
- The PR-081 `RE-ANCHOR` system message branches on the kind: AMBIGUOUS now says *do NOT say
  we don't have it — ask which one*, instead of the previous unconditional "tell the customer
  it isn't available".
- `search_menu` docstring — states it is for browsing a **category or keyword**, that a
  question about ONE named dish belongs to `check_menu_item`, and that a dish is never to be
  called unavailable unless a tool said so.

### `restaurant/agent/replies.py`
- `false_add_correction_phrase()` takes `ambiguous=`. This line is **code-owned speech** — it
  reaches the caller regardless of what the LLM would have said — and it previously spoke
  *"I actually don't have {query} on our menu"* on an AMBIGUOUS refusal too. The new
  clarify variant (en/hi/pa) asks which dish they meant and confirms nothing was added.

### `restaurant/agent/prompt.py`
- Tool contract: `search_menu` marked as a CATEGORY/keyword browse; `check_menu_item` marked
  as the tool for "do you have <one named dish>?", with an explicit rule never to call a dish
  unavailable unless a tool said so in those words. Applied to both the persona and legacy
  prompt blocks.

### Tests
- `tests/test_menu_browse.py` — named-dish pinning (Roman, alias, and Gurmukhi availability
  question), bare category terms still browsing, the miss string not being an absolute
  negative, hidden extras named, naan/lassi families, and **`test_search_and_check_agree_on_every_dish`**
  — the invariant behind the whole bug: the two lookups must never disagree.
- `tests/test_agent_tools.py` — AMBIGUOUS re-anchor does not claim unavailable, NOT FOUND
  still does, and the refusal kind is recorded. Two existing tests updated for the
  `_false_add_reanchor` tuple.
- `tests/test_agent_replies.py` — the ambiguous correction line never denies the dish in any
  language; not-found still does.
- `tests/test_menu_match.py` — masculine availability words are stopwords.

## Files Added
### `pr/pr_098_menu-availability-false-denials.md`
This document.

## Files Deleted
None.

## What's NOT in This PR

- **Category ordering in general.** `list_by_category` still returns raw cache order, so a
  bare "bread" browse leads with the rices. Not a denial — and the extras are now named in
  the tool result — but the ordering itself is untouched.
- **`MenuCache.search()` remains script-naive.** It uses plain `_norm` (no transliteration,
  no phonetic folding, no stopwords), unlike `MatchIndex`. The named-dish pin routes around
  it for the case that mattered rather than rewriting the search index.
- **`extract_dish_query`'s greedy n-gram behaviour** is unchanged; `_named_dish_hit` simply
  does not use it. Other callers keep today's semantics.
- No prompt-only fixes were relied on. Per the PR 030 lesson, the guarantee lives in code —
  the prompt and docstring changes are defence-in-depth on top of it.

## How to Test

```bash
uv run python -m pytest tests/ -q
```

629 passing. Two pre-existing failures in `tests/test_hosted_checkout.py`
(`test_place_pay_now_disabled_no_url`, `test_place_pay_now_hco_failure_still_places`) are
unrelated Clover sandbox payment tests and fail identically on clean `main`.

Reproduce the original bug against the real menu cache — every one of these answered "no"
before this PR:

```bash
USE_CLOVER_MENU=1 python3 -c "
import restaurant.menu_provider as mp
for q in ['ਸਟੂਡੈਂਟ ਕੌਂਬੋ ਚਾਹੀਦਾ','ਵੈਜ ਲੰਚ ਥਾਲੀ ਕੌਂਬੋ ਹੈਗੀ?','ਗਾਜਰ ਹਲਵਾ ਹੈਗਾ?','ਖੀਰ ਹੈਗੀ?','student combo','gajar halwa','rice pudding']:
    print(q, '->', mp.search_menu(q)[:90])
"
```

Each must start with `YES — ... IS on the menu`. Vague browses must NOT:

```bash
USE_CLOVER_MENU=1 python3 -c "
import restaurant.menu_provider as mp
for q in ['combo','dessert','paneer','ਡਿਜ਼ਰਟ ਦੇ ਵਿੱਚ ਕੀ ਕੁਝ ਮਿਲ ਜਾਏਗਾ?']:
    print(q, '->', mp.search_menu(q)[:90])
"
```

Full agreement invariant across all 61 live menu items — expect `failures: 0`:

```bash
USE_CLOVER_MENU=1 python3 -c "
import restaurant.menu_provider as mp
c = mp._get_cache(); bad = []
for it in c._items:
    for q in [it.name] + list(it.aliases):
        if 'No menu items found' in mp.search_menu(q) or 'is not on our menu' in mp.check_item(q):
            bad.append((q, it.name))
print('items:', len(c._items), '| failures:', len(bad))
"
```

### Live call

Ask, in Punjabi: "ਸਟੂਡੈਂਟ ਕੌਂਬੋ ਹੈਗਾ?", "ਵੈਜ ਲੰਚ ਥਾਲੀ ਹੈਗੀ?", "ਗਾਜਰ ਹਲਵਾ ਹੈਗਾ?" — each must get a
"yes". Then "ਡਿਜ਼ਰਟ ਵਿੱਚ ਕੀ ਹੈ?" must still get a normal two-item browse. Verify the **spoken
line**, not just that the tool fired — a tool-call gate clears silently.

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
