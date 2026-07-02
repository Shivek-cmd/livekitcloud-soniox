# PR 032 — Menu match confidence (cross-script phonetic matching + abstain)

## Branch
`pr_032_menu-match-confidence`

## Status
⬜ **Open** — in implementation.

## The bug (live transcript, 2026-07-02)

> Caller: ਹਾਂ ਜੀ, ਆਪਣੇ ਇੱਕ **ਮਿਕਸ ਪਕੌੜਾ ਪਲੈਟਰ** ਕਰ ਦਿਓ, ਤੇ ਇੱਕ ਸਮੋਸਾ ਚਾਟ ਕਰ ਦਿਓ।
> Sierra: ਠੀਕ ਹੈ — one **ਪੰਜਾਬੀ ਮੱਛੀ ਕਰੀ** ਤੇ one ਸਮੋਸਾ ਚਾਟ. ਹੋਰ ਕੁਝ?

Reproduced deterministically on `main`. Root cause chain:

1. **Real item scored zero.** Data stores the item as `ਮਿਸ਼ਰਿਤ ਪਕੋੜਾ ਪਲੇਟਰ`; caller/STT said
   `ਮਿਕਸ ਪਕੌੜਾ ਪਲੈਟਰ`. Every word differs (translated word + two matra variants:
   ੌ vs ੋ, ੈ vs ੇ). `find_item()` matches raw Unicode substrings — one matra difference = no match.
   Latin aliases (`"pakora platter"`) never fire against Gurmukhi queries.
2. **A courtesy verb won instead.** Token scoring counts any query token that is a *substring*
   of item text, and returns best item while `score > 0`. `ਕਰ` (from "ਕਰ ਦਿਓ" = "please make it")
   ⊂ `ਕਰੀ` (curry) → Punjabi Fish Curry scores 1 and wins. `find_item("ਕਰ")` → Punjabi Fish Curry.
3. **Auto-add trusted it blindly.** `can_auto_add_lines()` checks only "2+ lines, no required
   modifiers" — match quality is never consulted. Code-owned speech confirmed the wrong item
   confidently, bypassing the LLM.

Architectural summary: **probabilistic input (STT spelling variance) consumed by an
exact-match layer with no confidence concept and no ability to abstain.**

## What This PR Does

Replaces the fuzzy tail of `MenuCache.find_item()` with a **confidence-scored, cross-script,
stopword-aware token matcher** that can **abstain**, and gates the auto-add fast path on match
confidence. Pure in-process string ops — **no new dependencies, no network calls, no added
latency** (index precomputed once per cache load; per-query cost is microseconds over ~61 items).

### Matcher design (`restaurant/clover/match.py`)

| Layer | What it does |
|-------|--------------|
| `normalize()` | Lowercase, strip punctuation incl. danda `।`, collapse whitespace |
| `transliterate()` | Gurmukhi + Devanagari → Latin approximation (static char map, no deps) |
| `phonetic_key()` | Folds spelling variance: aspiration (`bh→b`, `th→t`…), `x→ks`, vowels dropped (keep leading), doubles collapsed. `ਪਕੌੜਾ`, `ਪਕੋੜਾ`, `pakora` → same key `pkr` |
| Stopwords | en/hi/pa function + courtesy words (`ਕਰ`, `ਦਿਓ`, `ਹਾਂ`, `ਜੀ`, `please`, `जी`, `करो`, qty words, `pcs`, `serves`…) removed from queries **and** labels |
| Scoring | Per item label (name / speak_as / voice_line / each alias): token weights — exact 1.0, phonetic key 0.85, phonetic prefix 0.75 (ਮਿਕਸ→`mks` matches mixed→`mksd`). Confidence = **F-measure of label coverage × query coverage**, so "ਛੋਲੇ" can't beat "ਛੋਲੇ ਭਟੂਰੇ ਕੌਂਬੋ" on the query "ਛੋਲੇ ਭਟੂਰੇ" |
| Abstain | Match requires ≥2 matched tokens **and** ≥60% label coverage; OR full match of a single-token label (exact text, or phonetic key ≥3 chars — 2-char keys like ਕਰੀ/ਖੀਰ→`kr` collide); OR a single matched token whose phonetic key is **unique across the whole menu**. Otherwise → `None` |
| Determinism | Ties broken by confidence → exact-token count → shorter label → name. No menu-order dependence |

### Behaviour changes

| Input | Before | After |
|-------|--------|-------|
| `ਹਾਂ ਜੀ, ਆਪਣੇ ਇੱਕ ਮਿਕਸ ਪਕੌੜਾ ਪਲੈਟਰ ਕਰ ਦਿਓ, ਤੇ ਇੱਕ ਸਮੋਸਾ ਚਾਟ ਕਰ ਦਿਓ।` | Punjabi Fish Curry + Samosa Chaat | **Mixed Pakora Platter + Samosa Chaat** |
| `ਕਰ` / `ਕਰ ਦਿਓ` / courtesy-only text | Punjabi Fish Curry | **None** (abstain) |
| `ਮੱਛੀ` alone (ambiguous — fish curry AND fish pakora) | First substring hit | **None** → LLM asks which one |
| `ਪਕੌੜਾ` alone | Substring luck | Mixed Pakora Platter — data explicitly aliases bare `"pakora"` to it; explicit aliases are respected |
| Low-confidence multi-item turn | Auto-added silently | **No auto-add** → normal LLM path with tools |

Abstaining is the correct product behaviour: an unresolved item falls through to the existing
LLM + `check_menu_item` / `search_menu` path, where the model clarifies with the caller instead
of the code confirming a wrong dish.

### Auto-add confidence gate

`ParsedOrderLine` gains `confidence: float` (from `match_confidence` on the resolved item;
static-menu path defaults to 1.0 — unchanged behaviour). `can_auto_add_lines()` additionally
requires `min(confidence) >= AUTO_ADD_MIN_CONFIDENCE` (default **0.8**) — only near-complete
label matches may speak code-owned confirmations. Mid-confidence resolutions still work through
the LLM tool path where the model confirms aloud.

### Kill switch / env

| Var | Default | Purpose |
|-----|---------|---------|
| `MENU_MATCH_LEGACY` | `0` | `1` restores the old substring/token matcher verbatim (rollback) |
| `MENU_MATCH_MIN_CONF` | `0.55` | Floor below which `find_item` abstains |
| `AUTO_ADD_MIN_CONFIDENCE` | `0.8` | Min per-line confidence for the auto-add fast path |

## Latency contract

- Match index built **once** lazily per `MenuCache` instance (~61 items → sub-millisecond build).
- Per-query work: tokenize + dict lookups, zero awaits, zero I/O, zero network.
- `on_user_turn_completed` → auto-add path timing unchanged; no effect on filler timing (PR 031),
  turn guidance, or LLM preemptive generation.

## Files Added

### `restaurant/clover/match.py`
Normalization, Gurmukhi/Devanagari transliteration, phonetic keys, stopwords, `MatchIndex`
(prebuilt per menu), `best_match(query) -> (item, confidence) | None`.

### `tests/test_menu_match.py`
- Exact live-transcript regression (wrong-item bug) against a synthetic cache mirroring real data
- Abstain on courtesy words / stopword-only queries / ambiguous single tokens
- Matra-variant and cross-script (Gurmukhi query ↔ Latin alias) matching
- Unique-single-token rule (`jamun` → Gulab Jamun)
- Auto-add confidence gate blocks low-confidence lines
- `MENU_MATCH_LEGACY=1` restores old behaviour
- Determinism (menu order shuffled → same result)

## Files Modified

### `restaurant/clover/menu.py`
`find_item()` → exact pass then confidence matcher (abstains); old implementation preserved as
`_find_item_legacy()` behind `MENU_MATCH_LEGACY=1`. New `find_item_scored()` returns
`(item, confidence)`.

### `restaurant/menu_provider.py`
`find_item()` passes `match_confidence` through in the cart dict (Clover path). Static path
unchanged (no key → treated as 1.0).

### `restaurant/order_parse.py`
`ParsedOrderLine.confidence`; `can_auto_add_lines()` requires min confidence ≥
`AUTO_ADD_MIN_CONFIDENCE`.

### `.env.example`
New vars documented (defaults are safe — no VPS `.env` change required to deploy).

### `pr/README.md`
Index row for PR 032.

## Files Deleted
None.

## What's NOT in This PR

- **STT vocabulary biasing** (Soniox context/keyword hints so transcripts come out closer to
  menu spellings) — recommended follow-up PR
- Alias/data batch fixes (shikanji → Nimbu Pani etc.) — planned PR 033
- `search_menu()` / `search()` rescoring (LLM-mediated; lower blast radius) — follow-up
- Static `restaurant/menu.py` matcher changes (VPS runs `USE_CLOVER_MENU=1`)
- Embedding/vector retrieval — unnecessary at 61 items; revisit multi-tenant

## How to Test

```bash
# New matcher tests
PYTHONPATH=. uv run pytest tests/test_menu_match.py -q

# Regression
PYTHONPATH=. uv run pytest tests/test_order_parse.py tests/test_conversation.py tests/test_language.py -q

# Full suite
PYTHONPATH=. uv run pytest -q
```

### Manual — phone

1. Punjabi: "ਹਾਂ ਜੀ, ਇੱਕ ਮਿਕਸ ਪਕੌੜਾ ਪਲੈਟਰ ਤੇ ਇੱਕ ਸਮੋਸਾ ਚਾਟ" → both items correct in read-back.
2. "ਇੱਕ ਪਕੌੜਾ ਦੇ ਦਿਓ" (ambiguous) → Sierra asks which pakora, does not pick one.
3. English: "one butter chicken and one kheer" → auto-add works as before.
4. Watch logs: `journalctl -u restaurant-agent -f | grep -E 'MENU_MATCH|AUTO_ADD'` — every match
   logs query, item, confidence; abstains log at info level.

## Post-Merge: VPS Pull Command

```bash
cd /opt/livekit-sarvam && git fetch origin && git checkout main && git reset --hard origin/main && uv sync && systemctl restart restaurant-agent
```

No `.env` changes needed (defaults active). Rollback without redeploy:
`MENU_MATCH_LEGACY=1` in `/opt/livekit-sarvam/.env` + `systemctl restart restaurant-agent`.

## Verification checklist

- [ ] `tests/test_menu_match.py` passes; full suite green
- [ ] Live transcript case resolves to Mixed Pakora Platter + Samosa Chaat
- [ ] `find_item("ਕਰ")` → None
- [ ] Ambiguous "ਪਕੌੜਾ" → None (LLM clarifies)
- [ ] Auto-add refuses low-confidence lines
- [ ] `MENU_MATCH_LEGACY=1` restores old matcher
- [ ] No latency regression in `user_stop→speaking` logs
