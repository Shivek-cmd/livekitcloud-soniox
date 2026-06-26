# Reference Knowledge Base

Captured external knowledge (LiveKit + Sarvam) so we don't have to re-paste docs each session.
Each file lists its source URL and capture date. **Keep these updated** when the plugin versions,
our pinned versions, or the upstream docs change.

| File | What it covers |
|---|---|
| [sarvam-tts-plugin.md](sarvam-tts-plugin.md) | Sarvam Bulbul TTS params, speakers, latency/quality troubleshooting. |
| [sarvam-stt-plugin.md](sarvam-stt-plugin.md) | Sarvam Saaras STT params, modes, fine-grained VAD options. |
| [livekit-turn-detection-interruptions.md](livekit-turn-detection-interruptions.md) | Turn detection modes, endpointing, interruptions, false-interruption recovery, tuning matrix. |
| [livekit-noise-cancellation.md](livekit-noise-cancellation.md) | Noise/echo cancellation + the **self-hosted vs Cloud** caveat (Krisp is Cloud-only). |

Related:
- [../diagnosis/phone-call-quality.md](../diagnosis/phone-call-quality.md) — root-cause analysis of the slow-voice + voice-breaking phone issues.
- [../vps-config.md](../vps-config.md) — deployment, pinned versions, SIP/Twilio config.

## How to refresh a doc

Use the LiveKit Docs MCP (`docs_search` → `get_pages`) or the Sarvam MCP, then update the matching
file and bump its "Captured" date. Note our pinned versions from `../vps-config.md` when behavior is
version-specific.
