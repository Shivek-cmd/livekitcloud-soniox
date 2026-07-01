# PR 033 — Ladder single-speak + final confirm

## Branch
`pr_033_ladder-single-speak`

## What This PR Does

Production fixes after PR 032 live test:

1. **Stop double speech** — `session.interrupt(force=True)` before code-owned TTS cancels preemptive LLM/TTS that duplicated every ladder line.
2. **Punjabi name capture** — `ਨਾਮ ਹੈ ਸ਼ਿਵੇਕ` → extract name for code ladder.
3. **Punjabi pickup STT** — `ਪਿਕਅੱਪ` phrases → pickup intent at order_type.
4. **Final confirm after phone** — speak name + phone digits + order (no price) once, then `place_order()` on yes.
5. **Never re-read order at name step** — guidance + code path only ask phone.

## When order is read aloud (spec)

| Moment | Read order? |
|--------|-------------|
| After add / auto-add | Short cashier confirm only |
| After pickup/delivery | Full read-back once + "All good?" |
| User changes cart mid-call | Yes — fresh read-back |
| After name | **No** — phone question only |
| After phone | **Yes** — name + phone + items (final confirm) |
| Price on phone | **Never** unless ASK_PRICE |

## Post-Merge: VPS

```bash
cd /opt/livekit-sarvam && git fetch origin && git checkout main && git reset --hard origin/main && uv sync && systemctl restart restaurant-agent
```
