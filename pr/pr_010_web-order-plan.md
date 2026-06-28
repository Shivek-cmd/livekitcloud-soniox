# PR 010 — Plan doc: Web "Order with Sierra"

## Branch
`pr_010_web-order-plan`

## What This PR Does

Adds the planning document for the next major workstream: rebuilding the web app into a
production-grade **"Order with Sierra"** experience (avatar + live menu + real-time order screen),
with a second **Store** tab to follow later. **Docs only — no code/behavior change.**

The plan is grounded in the current codebase (`agent.py`, `token_server.py`, `OrderCart`,
`menu_provider`) and LiveKit's realtime primitives (avatar `AvatarSession`, RPC, data packets,
participant attributes, transcriptions), mirroring LiveKit's official `drive-thru` example.

### Locked decisions captured in the plan
- Hybrid ordering (voice + tap-to-add; server `OrderCart` is the single source of truth)
- Prices shown openly on web; web prompt variant says them freely
- `place_order` log-only + pay at pickup for v1 (Clover POS submit deferred to Phase 8c)
- Fully responsive (desktop 3-col / mobile stacked)
- Avatar provider chosen at phase W4, behind a swappable abstraction with audio-only fallback

### Phasing (each future phase = its own PR)
W1 shell+tabs+menu+captions → W2 live order + hybrid cart → W3 highlight + modifier picker →
W4 avatar → W5 hardening → W6 web prompt variant.

## Files Added
### `docs/plan/11-web-order-with-sierra.md`
The full plan: product shape, target architecture, data contracts (push/pull + client→agent RPCs),
edge-case list, phasing, and decisions.

## Files Modified
### `docs/README.md`
Added the new plan doc to the documentation index.

## Files Deleted
None.

## What's NOT in This PR
- No frontend or agent code. Implementation starts at Phase W1 in a separate PR.
- Store tab, online payment, and Clover order submit (Phase 8c) are out of scope here.

## How to Test
Docs only — review `docs/plan/11-web-order-with-sierra.md` for correctness/completeness.

## Post-Merge: VPS
None (documentation only).
