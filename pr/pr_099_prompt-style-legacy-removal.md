# PR 099 — Retire the PROMPT_STYLE=legacy rollback prompt

## Branch
`pr_099_prompt-style-legacy-removal`

## What This PR Does

PR 077 replaced the single-block system prompt with ordered persona sections and kept the
old prompt behind `PROMPT_STYLE=legacy` "for one release" as a rollback. Twenty-two PRs
later the rollback has never been used, and it costs a mirrored edit on every prompt change
— PRs 084, 094, 095 and 096 each had to write the same rule into both copies. This deletes
the legacy builder and the env switch. The persona sections are now the only prompt.

The persona prompt itself is **unchanged** — byte-identical on both channels before and
after (verified below).

### Why this is safe

The legacy path was already unreachable in production:

- Nothing sets `PROMPT_STYLE`. It is absent from `.env` (local and VPS, confirmed identical),
  from `.env.example`, and from `deploy/restaurant-agent.service`, which passes no
  `Environment=` lines and only reads `EnvironmentFile=/opt/livekit-sarvam/.env`. No commit
  in the repo's history ever set the variable anywhere.
- Both production callers — `RestaurantAgent.__init__` and `llm_warmup` — called
  `build_system_prompt(is_phone=…)` with no `style`. The only `style=` call sites in the
  tree were in `tests/test_prompt.py`.
- `prompt_style()` already failed safe: any value other than the exact string `legacy`
  resolved to `persona`.

A stale `PROMPT_STYLE=legacy` left on some host is now inert rather than a silent prompt
downgrade, and there is a test pinning that.

## Files Modified

### `restaurant/agent/prompt.py`
- **Deleted `prompt_style()`** — the `PROMPT_STYLE` env reader, and with it the `os` import.
- **Deleted `_legacy_core_prompt()`** (~60 lines) — the pre-077 single-block prompt. It
  duplicated the hard speech rules and the entire tool contract inline (it shared only
  `_your_job()`), and the copies had already drifted: legacy still hardcoded the TRANSFER
  line `"Sure, let me connect you — one moment."` where the persona contract says to say one
  short warm line in the customer's language.
- **`build_system_prompt(*, is_phone)`** — the `style` parameter and the branch are gone; it
  assembles PERSONA → HARD SPEECH RULES → YOUR JOB → TOOL CONTRACT → CHANNEL unconditionally.
- `RESTAURANT_NAME` (the Gurmukhi name) dropped from the `restaurant.menu` import — it was
  used only by the legacy block. `RESTAURANT_NAME_EN` is still used by the tool contract.
- Module docstring updated.

### `restaurant/agent/core.py`
- Import narrowed to `build_system_prompt`.
- The PR 077 persona drift re-anchor guard loses its style check:
  `if n > 0 and prompt_style() == "persona" and …` → `if n > 0 and …`. The clause was always
  true in production, so behaviour is unchanged; this was the only coupling to the env var
  beyond prompt text.

### `tests/test_prompt.py`
- `test_non_negotiables_present_in_both_styles` → `test_non_negotiables_present_on_both_channels`
  — same rule list, now looped over phone/web only.
- `test_persona_style_uses_approved_persona` → `test_prompt_uses_approved_persona`.
- `test_legacy_style_is_the_old_prompt` deleted.
- `test_prompt_style_env` → **`test_prompt_style_env_is_inert`**: sets `PROMPT_STYLE=legacy`
  and asserts the built prompt is byte-identical to the default and contains none of the
  legacy markers. This is the regression guard for a stale env on a deployed host.
- `test_reanchor_skipped_in_legacy_style` → **`test_reanchor_still_fires_with_stale_legacy_env`**:
  same setup, inverted expectation — the re-anchor now fires on schedule regardless.
- Dropped a now-pointless `delenv("PROMPT_STYLE")` from `test_reanchor_injected_every_n_turns`.

## Files Added
None.

## Files Deleted
None.

## What's NOT in This PR

- **No prompt wording changes.** Any edit to the persona sections belongs in its own PR; this
  one only removes the dead alternative.
- **Historical PR docs are untouched.** `pr/pr_077…`, `pr_084`, `pr_086`, `pr_094`, `pr_095`,
  `pr_096` mention `PROMPT_STYLE=legacy`; they are ship records of what was true then.
- **`MENU_MATCH_LEGACY` is unrelated and stays.** It is a live, documented kill switch in
  `.env.example` for the PR 032 matcher.
- **No `.env.example` change** — `PROMPT_STYLE` was never documented there.

## How to Test

```bash
uv run python -m pytest tests/ -q
```

628 passing. The same two pre-existing failures in `tests/test_hosted_checkout.py`
(`test_place_pay_now_disabled_no_url`, `test_place_pay_now_hco_failure_still_places`) are
unrelated Clover sandbox payment tests and fail identically on clean `main`.

Prove the shipped prompt did not change — compares the new build against the pre-change
builder from git, on both channels:

```bash
uv run python - <<'EOF'
import subprocess, types
from restaurant.agent.prompt import build_system_prompt

old_src = subprocess.check_output(
    ["git", "show", "HEAD~1:restaurant/agent/prompt.py"], text=True)
mod = types.ModuleType("old_prompt")
exec(compile(old_src, "old_prompt.py", "exec"), mod.__dict__)
for is_phone in (True, False):
    old = mod.build_system_prompt(is_phone=is_phone)
    new = build_system_prompt(is_phone=is_phone)
    print("phone" if is_phone else "web", "identical:", old == new, "| len", len(new))
EOF
```

Both must print `identical: True` (14053 chars phone, 14295 web).

Confirm the env var is inert and nothing still reads it:

```bash
PROMPT_STYLE=legacy uv run python -c "
from restaurant.agent.prompt import build_system_prompt
p = build_system_prompt(is_phone=True)
assert 'ONE short sentence per turn' not in p
assert 'AI cashier' in p
print('legacy env ignored, persona prompt served')
"
grep -rn "PROMPT_STYLE\|prompt_style" restaurant scripts deploy .env.example
```

The only hit may be the one historical mention in `prompt.py`'s module docstring — no
executable reference, no config.

### Live call
Place one ordinary phone order end to end — the agent's tone, checklist and read-backs must
be exactly what they were before this PR. A tool-call gate clears silently, so listen to the
spoken lines: warm multi-sentence turns, not the clipped one-sentence-per-turn cadence the
legacy prompt enforced.

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
