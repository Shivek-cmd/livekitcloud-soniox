# LiveKit Noise & Echo Cancellation Reference

> Source: LiveKit docs › Media › Noise & echo cancellation (`/transport/media/noise-cancellation`)
> and SIP troubleshooting (`/reference/telephony/troubleshooting`). Updated 2026-06-27.

## How echo is handled in our setup (LiveKit Cloud)

We run on **LiveKit Cloud**, so the Krisp features are available and **echo is solved**:

- **Trunk-level Krisp NC** — `krisp_enabled=True` on the Cloud SIP inbound trunk. Cleans the caller's
  audio server-side before it reaches the agent. **This is what we use** (set via `scripts/setup_sip.py`).
- **Cloud telephony media path** — Cloud handles the SIP/RTP media, which removed the self-echo
  barge-in that plagued the old self-hosted setup.

Verified on a real call: clean, multi-turn Punjabi conversation, no self-echo interruption.

### Agent-side voice isolation (optional, currently OFF)
`noise_cancellation.BVCTelephony()` in `RoomInputOptions` adds telephony-tuned voice isolation in the
agent process. We tried it and it **failed to initialize** (`failed to initialize the audio filter`)
and broke audio input — and it isn't needed, since trunk-level Krisp + the Cloud media path already
deliver a clean call. So we leave it off. If we ever want it, revisit the plugin/runtime first.

## Concepts

- **Voice isolation** — emphasizes the primary speaker, suppresses competing voices + noise. Models:
  Krisp BVC, Krisp BVCTelephony (SIP-tuned).
- **Background noise suppression (NC)** — removes non-speech noise (traffic, fans, music). Model: Krisp NC.
  This is what the trunk-level `krisp_enabled` applies.
- **WebRTC AEC/NS** — browser-only, client-side; applies to the **web** channel, not phone.

> ⚠️ Don't stack NC: if NC runs at the trunk/agent, don't also run NC in the frontend, and vice versa.

## SIP troubleshooting — "bad audio quality" (official)

If audio flows both ways but sounds choppy/robotic/distorted, it's usually **network quality**
(RTP over UDP). Healthy thresholds:

| Metric | Healthy | Degraded |
|---|---|---|
| Packet loss | < 1% | > 3% → audible breakup |
| Jitter (mean) | < 5ms | > 20ms → choppy audio |
| One-way latency | < 150ms | > 300ms → parties talk over each other |

On LiveKit Cloud you can capture per-call PCAPs and inspect RTP from the telephony dashboard, which
makes diagnosing network-quality issues much easier than on self-hosted.
