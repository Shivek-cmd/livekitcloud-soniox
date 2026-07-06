# PR 049 — STT noise filter discarding genuine orders

## Branch
`pr_049_stt-noise-order-verb-fix`

## Problem (live call, 2026-07-06)

Two clear, correctly-transcribed multi-item orders were silently thrown away
before ever reaching the LLM or menu matching, both times triggering a "sorry,
please repeat" fallback:

```
USER: आपके अपने एक प्लेन राइज़ के दो गार्लिक नान, और अपने ਤੁਸੀਂ ਚਾਰ ਚਿਕਨ ਟਿੱਕਾ ਮਸਾਲਾ ਕਰ ਦਿਓ।
LOG:  STT_NOISE rejected turn: आपके अपने एक प्लेन राइज़ के...
SIERRA: Sorry ji — phir se bol sakte hain?

USER: ਓਕੇ, ਵਨ ਚਿਕਨ ਟਿੱਕਾ ਮਸਾਲਾ, ਦੋ ਮਟਰ ਨਾਨ, ਤੇ ਤਿੰਨ ਗਾਰਲਿਕ ਨਾਨ ਕਰ ਦਿਓ।
LOG:  STT_NOISE rejected turn: ਓਕੇ, ਵਨ ਚਿਕਨ ਟਿੱਕਾ ਮਸਾਲਾ...
SIERRA: ਮਾਫ ਕਰਨਾ ਜੀ — ਦੁਬਾਰਾ ਦੱਸੋ?
```

Root cause: `is_likely_stt_noise()` in `restaurant/stt_noise.py` has a "long
mixed-script ramble with no order verb" heuristic meant to filter TV/background
media bleeding into the phone mic — any utterance over 40 characters that mixes
2+ scripts (Gurmukhi/Devanagari/Latin) and doesn't match a small inline
keyword list (`chahid|chaah|order|add|menu|ਚਾਹੀ|ਆਰਡਰ|ਐਡ|ਖਾਣ`) gets discarded.

Both utterances above use **"ਕਰ ਦਿਓ"** ("do it/make it") — an extremely
common, completely normal Punjabi way to place an order — which wasn't in that
list. Verified directly: `is_likely_stt_noise()` returned `True` for both real
orders before this fix. This is unrelated to the checkout-ladder/allergies
fixes in PR 047/048 — a separate, narrower filter in a different module.

## Fix

### `restaurant/conversation.py`
- New `looks_like_order_phrasing(text)` — thin public wrapper around the
  already-existing, more complete `_ADD_RE` (covers `ਕਰ ਦ`, `ਪਾ ਦ`, `ਜੋੜ`,
  `ਲੈ`, `ਚਾਹੀ(ਦਾ/ਦੀ/ਦੇ)`, `dedo`, `de do`, `lao`, etc., not just the narrow
  list `stt_noise.py` had). Single source of truth for "does this sound like
  an order attempt" instead of two independently-drifting keyword lists.

### `restaurant/stt_noise.py`
- `is_likely_stt_noise()`'s mixed-script-ramble branch now calls
  `looks_like_order_phrasing()` instead of its own narrow inline regex.

### `tests/test_stt_noise.py`
- `test_stt_noise_does_not_reject_kar_dio_multi_item_order` — reproduces both
  exact live-call transcripts, asserts neither is flagged as noise anymore.
- `test_stt_noise_still_rejects_actual_background_media` — confirms the
  filter still catches genuine TV/subscribe-spam noise (no regression).

## What's NOT in This PR

- Does not touch the `_STT_NOISE_RE` explicit noise-signature list
  (subscribe/breaking news/etc.) — unrelated, still works as before.
- Does not address the compound-utterance gap or the background-speech
  filter issues flagged earlier — separate, already-tracked items.

## How to Test

```bash
PYTHONPATH=. pytest tests/test_stt_noise.py tests/test_conversation.py tests/test_order_flow.py -q
```

Live: place a multi-item order using natural Punjabi phrasing with "ਕਰ ਦਿਓ"
(e.g. "one chicken tikka masala te do garlic naan kar dio") — confirm it's
recognized and added instead of triggering a "please repeat" fallback.

```bash
journalctl -u restaurant-agent -f | grep -E 'USER:|SIERRA:|STT_NOISE'
```

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
