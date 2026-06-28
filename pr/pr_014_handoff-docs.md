# PR 014 — Session handoff + docs sync (2026-06-28)

## Branch
`pr_014_handoff-docs`

## What This PR Does

Doc-only PR so a **new session can start from `docs/HANDOFF.md`** without re-discovering
this week's web work. No code or runtime behavior changes.

Updates reflect everything shipped in PRs **009–013**:

- Domain **`voice.bizbull.ai`** (retired `sarvam.bizbull.ai`)
- Web **W1** (shell, menu, captions) and **W2** (live order, hybrid tap-to-add)
- Web **shared turn latency** with phone (0.8s max endpointing)
- **Mango Kulfi** English TTS fix
- VPS deploy notes (npm build, Caddy routes, OOM warning)
- PR index through 013

## Files Modified

### `docs/HANDOFF.md`
Full refresh — current URLs, web architecture, key files, PR history, next priorities (W3, Tier B, 8c).

### `docs/README.md`
Index updated for plan 11, PR 011–013, `voice.bizbull.ai`.

### `docs/plan/06-milestones.md`
Phase 2 web expansion; Phase 7 web W1–W6 tracker; web shared latency in Phase 6.

### `docs/vps-config.md`
`voice.bizbull.ai` Caddy block, npm build in deploy, production commit, VPS OOM tip.

### `pr/pr_013_web-shared-latency.md`
Retroactive note: Mango Kulfi + package-lock entries.

### `pr/README.md` (new)
PR index table 001–014.

## What's NOT in This PR
- W3 implementation, Tier B fixes, Clover 8c.

## Post-Merge
No deploy needed — docs only.
