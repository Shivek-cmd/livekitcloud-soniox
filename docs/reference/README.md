# Reference Knowledge Base

Captured external knowledge (Soniox + LiveKit) so we don't re-paste docs each session.
Each file lists its source URL and capture date. **Keep these updated** when plugin/pinned versions
or upstream docs change.

| File | What it covers |
|---|---|
| [soniox-stt-tts-plugin.md](soniox-stt-tts-plugin.md) | Soniox STT + TTS (US/EU/JP hosted), Punjabi/code-mix support, voices, params, telephony notes. |
| [livekit-turn-detection-interruptions.md](livekit-turn-detection-interruptions.md) | Turn detection modes, endpointing, interruptions, false-interruption recovery, tuning matrix. |
| [livekit-noise-cancellation.md](livekit-noise-cancellation.md) | Noise/echo cancellation on LiveKit Cloud (trunk-level Krisp) + SIP audio-quality troubleshooting. |

Related:
- [../plan/01-overview.md](../plan/01-overview.md) — what we're building + the current stack.
- [../plan/02-architecture.md](../plan/02-architecture.md) — current architecture and call flow.
- [../vps-config.md](../vps-config.md) — deployment, services, SIP IDs, env, ops.

## How to refresh a doc

Use the LiveKit Docs MCP (`docs_search` → `get_pages`) or the Soniox docs, then update the matching
file and bump its "Captured" date.
