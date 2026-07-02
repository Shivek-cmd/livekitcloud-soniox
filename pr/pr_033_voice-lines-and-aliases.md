# PR 033 — Voice lines speak the customer's word + slang aliases

## Branch
`pr_033_voice-lines-and-aliases`

## Status
⬜ **Open** — in implementation.

## The problem (live call, 2026-07-02)

Caller ordered **Saffron Rice**; Sierra confirmed "**ਕੇਸਰ ਚਾਵਲ**" (Kesar Chawal) — a
*translated* word the customer never said. Full-menu review found this class in 7 items:
the voice_line substitutes a translation (Kesar, Mishrit, Bakre da Masala, Sada Chawal)
for the word customers actually use.

**Principle established:** transliteration is fine (ਸਟੂਡੈਂਟ ਕੌਂਬੋ *sounds like* "Student
Combo"), **translation is the bug** (ਕੇਸਰ ≠ Saffron). Punjabi dish names that have no
English (ਛੋਲੇ ਭਟੂਰੇ, ਦਾਲ ਮੱਖਣੀ, ਖੀਰ…) stay Punjabi. Natural Punjabi terms reviewed and
deliberately kept: ਮਿੱਠੀ/ਨਮਕੀਨ ਲੱਸੀ, ਗਾਜਰ ਦਾ ਹਲਵਾ.

## What This PR Does

### 1. Voice line fixes (7 items — owner-approved 2026-07-02)

| Item | Was spoken | Now spoken | Mechanism |
|---|---|---|---|
| Saffron Rice | ਕੇਸਰ ਚਾਵਲ | **Saffron Rice** | `ENGLISH_VOICE_KEYS` |
| Plain Rice | ਸਾਦਾ ਚਾਵਲ | **Plain Rice** | `ENGLISH_VOICE_KEYS` |
| Jeera Rice | ਜੀਰਾ ਚਾਵਲ | **Jeera Rice** | `ENGLISH_VOICE_KEYS` |
| Goat Curry | ਬਕਰੇ ਦਾ ਮਸਾਲਾ | **Goat Curry** | `ENGLISH_VOICE_KEYS` |
| Punjabi Fish Curry | ਪੰਜਾਬੀ ਮੱਛੀ ਕਰੀ | **Punjabi Fish Curry** | `ENGLISH_VOICE_KEYS` |
| Mixed Pakora Platter | ਮਿ**ਸ਼ਰਿਤ** ਪਕੋੜਾ ਪਲੇਟਰ | ਮਿ**ਕਸ** ਪਕੋੜਾ ਪਲੇਟਰ | `speak_as` (stays Gurmukhi) |
| Mixed Pickle | ਮਿਸ਼ਰਿਤ ਅਚਾਰ | ਮਿਕਸ ਅਚਾਰ | `speak_as` (stays Gurmukhi) |
| Tandoori Chicken (Half) | Tandoori Chicken (identical to Full!) | **Half Tandoori Chicken** | `VOICE_LINE_OVERRIDES` |
| Tandoori Chicken (Full) | Tandoori Chicken (identical to Half!) | **Full Tandoori Chicken** | `VOICE_LINE_OVERRIDES` |

The Tandoori pair was found by the new duplicate-voice-line audit test: both items spoke
the same words, so a read-back could not tell the caller which one was on the order.

Old Gurmukhi names remain matchable: `speak_as` keeps ਬਕਰੇ ਦਾ ਮਸਾਲਾ / ਕੇਸਰ ਚਾਵਲ etc.
in the match index, and roman aliases are added — a caller saying "kesar chawal" still
gets Saffron Rice; Sierra just confirms it by the menu-card name.

### 2. Slang / STT aliases (matching only, changes nothing spoken)

| Item | New aliases |
|---|---|
| Nimbu Pani | `shikanji`, `shikanjvi` |
| Saffron Rice | `kesar chawal` |
| Goat Curry | `bakra`, `bakre da masala` |
| Mixed Pakora Platter | `mix pakora platter`, `mixed pakora` |
| Plain Rice | `sada chawal` |
| Sweet Lassi | `mitthi lassi` |
| Salted Lassi | `namkeen lassi` |
| Punjabi Fish Curry | `machhi` |

Roman aliases are sufficient for Gurmukhi speech (ਸ਼ਿਕੰਜੀ → `shikanji`) because the
PR 032 matcher is cross-script.

## Files Modified

### `restaurant/clover/speech_policy.py`
`saffron_rice`, `plain_rice`, `jeera_rice`, `goat_curry`, `fish_curry` added to
`ENGLISH_VOICE_KEYS` (spoken line = menu name; no overrides needed).

### `restaurant/clover/seed_menu.py`
`speak_as` ਮਿਸ਼ਰਿਤ→ਮਿਕਸ for `pakora_platter` and `mixed_pickle`; alias additions above.

### `data/clover_voice_labels.json`
Regenerated via `scripts/rebuild_voice_labels.py` (voice_line/speech_mode/speak_as)
plus alias additions (rebuild script preserves aliases; kept in sync with seed specs).

### `tests/test_menu_match.py`
Real-labels-file audit tests: every item's name/voice_line/speak_as/alias resolves to
itself; shikanji→Nimbu Pani; kesar chawal→Saffron Rice; bakre da masala→Goat Curry;
changed items report correct new voice_line.

## Files Deleted
None.

## What's NOT in This PR

- Soniox STT vocabulary biasing (menu terms as context hints) — next PR
- `data/menu_cache_bizbull.json` — not committed; VPS deploy re-syncs it from Clover +
  labels via `scripts/clover_sync_menu.py`
- Verify-before-add for mid-confidence matches — candidate follow-up

## How to Test

```bash
PYTHONPATH=. uv run pytest tests/test_menu_match.py tests/test_speech_policy.py -q
PYTHONPATH=. uv run pytest tests/ -q
```

Manual (phone, after deploy): order "saffron rice" → Sierra confirms "Saffron Rice";
order "ਸ਼ਿਕੰਜੀ" → Sierra offers Nimbu Pani; order "mix pakora platter" → confirm says
ਮਿਕਸ (not ਮਿਸ਼ਰਿਤ).

## Post-Merge: VPS Pull Command

```bash
cd /opt/livekit-sarvam && git fetch origin && git checkout main && git reset --hard origin/main && uv sync && bash scripts/vps_deploy.sh
```

(`vps_deploy.sh` required — it re-syncs the menu cache so new voice lines/aliases load.)

## Verification checklist

- [ ] Full-menu self-audit: 61 items, all labels resolve to themselves, 0 wrong
- [ ] shikanji / kesar chawal / bakre da masala / mitthi lassi resolve correctly
- [ ] Changed items speak menu-card names; ਮਿਸ਼ਰਿਤ gone from voice lines
- [ ] Old Gurmukhi words still match their items (speak_as indexed)
- [ ] Full test suite green (minus 4 pre-existing failures on main)
