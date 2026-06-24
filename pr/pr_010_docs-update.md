# PR 010 — Docs update: reflect current production state

## Summary
Updated three docs to match the live system. Previously the docs had unchecked
installation tasks, missing services, wrong restaurant name, and phases marked as
future work that are actually done.

## Changes

### `docs/vps-config.md`
- Mark all installation tasks as done
- Add `sarvam.bizbull.ai` Caddy routing description
- Add port 8001 to ports table (now in use)
- Add Systemd Services section with unit names, exec paths, and common commands
- Add SIP Configuration section — trunk ID, dispatch rule ID, Twilio details
- Add Web App section — build command, how Caddy serves it
- Add deploy-after-changes cheatsheet
- Add Twilio env vars to credentials block
- Add twilio package to version table

### `docs/plan/01-overview.md`
- Restaurant is now Bizbull Restaurant, agent is Sierra
- Language section updated: natural Punjabi-English mix (not "always Punjabi")
- Channels table shows both as Live with actual URLs/numbers
- Agent capabilities updated to reflect spice level, special instructions, digit-by-digit phone

### `docs/plan/06-milestones.md`
- Phases 1, 2, 3 marked DONE with actual implementation notes
- Phase 4 shows what's done (prompt rewrite) vs still pending (latency profiling, STT testing)
- Phase 5 updated with deferred items and notes on why

## Files Changed
- `docs/vps-config.md`
- `docs/plan/01-overview.md`
- `docs/plan/06-milestones.md`
