# Reference Knowledge Base

Captured external knowledge (Soniox, LiveKit, Clover) so we don't re-paste docs each session.
Each file lists its source URL and capture date. **Keep these updated** when plugin/pinned versions
or upstream docs change.

| File | What it covers |
|---|---|
| [soniox-stt-tts-plugin.md](soniox-stt-tts-plugin.md) | Soniox STT + TTS (US/EU/JP hosted), Punjabi/code-mix support, voices, params, telephony notes. |
| [livekit-turn-detection-interruptions.md](livekit-turn-detection-interruptions.md) | Turn detection modes, endpointing, interruptions, false-interruption recovery, tuning matrix. |
| [livekit-noise-cancellation.md](livekit-noise-cancellation.md) | Noise/echo cancellation on LiveKit Cloud (trunk-level Krisp) + SIP audio-quality troubleshooting. |
| [clover-platform-overview.md](clover-platform-overview.md) | Clover platform, data model, integration paths, sandbox/prod environments, Canada notes. |
| [clover-oauth-and-api.md](clover-oauth-and-api.md) | REST API basics, v2/OAuth tokens, permissions, rate limits, webhooks. |
| [clover-inventory-menu.md](clover-inventory-menu.md) | Inventory/items/modifiers, availability/stock, menu sync strategy for voice. |
| [clover-orders-api.md](clover-orders-api.md) | Atomic vs custom orders, checkout→create→print flow, totals, errors, production FAQs. |
| [clover-sierra-integration-notes.md](clover-sierra-integration-notes.md) | How Clover maps to Sierra — v1 scope, edge cases, open questions (planning only). |

Related:
- [../plan/01-overview.md](../plan/01-overview.md) — what we're building + the current stack.
- [../plan/02-architecture.md](../plan/02-architecture.md) — current architecture and call flow.
- [../vps-config.md](../vps-config.md) — deployment, services, SIP IDs, env, ops.

## How to refresh a doc

Use the LiveKit Docs MCP (`docs_search` → `get_pages`), Soniox docs, or Clover docs
(`https://docs.clover.com/llms.txt` for the full index), then update the matching file and bump
its "Captured" date.
