# LiveKit Noise & Echo Cancellation Reference

> Source: LiveKit docs › Media › Noise & echo cancellation (`/transport/media/noise-cancellation`)
> and SIP troubleshooting (`/reference/telephony/troubleshooting`). Captured 2026-06-26.

## ⚠️ The critical fact for OUR setup (self-hosted LiveKit)

**Enhanced noise cancellation (Krisp BVC / BVCTelephony) is a LiveKit _Cloud_ feature.**
We self-host the LiveKit server on a VPS (`lk.bizbull.ai`, `devkey`), so:

- `noise_cancellation.BVC()` / `BVCTelephony()` in agent code → **needs LiveKit Cloud transport.** Not available to us as-is.
- SIP-trunk Krisp (`krisp_enabled: true` on the inbound trunk) → **also a LiveKit Cloud feature.** Not available on our self-hosted SIP service.

So any "just turn on Krisp" advice does **not** directly apply to us. This is a likely reason
a month of echo tuning hasn't produced a clean fix — the recommended cloud lever isn't on the table.

### What IS available to a self-hosted deployment

| Option | Works self-hosted? | Cost | Notes |
|---|---|---|---|
| Krisp BVC / BVCTelephony (agent) | ❌ (Cloud only) | Cloud pricing | Telephony-tuned voice isolation. |
| Krisp NC at SIP trunk (`krisp_enabled`) | ❌ (Cloud only) | Cloud pricing | Trunk-level noise cancellation. |
| **ai-coustics** voice isolation / noise suppression | ✅ with **own license key** | Billed by ai-coustics | Pass `auth=Auth.ai_coustics_api(license_key=...)`. Self-hosts the metering. Get key at developers.ai-coustics.io. |
| WebRTC `echoCancellation` / `noiseSuppression` | ✅ (browser only) | Free | Client-side; applies to **web** channel only, NOT phone. We already enable this in `web/src/App.tsx`. |
| SDK-level interruption tuning (min_words, false-interruption resume) | ✅ | Free | No NC model needed. See `livekit-turn-detection-interruptions.md`. **This is our most realistic lever for phone echo.** |

## Concepts

- **Voice isolation** — emphasizes the primary speaker, suppresses competing voices + noise. Best for single-speaker. Models: Krisp BVC, Krisp BVCTelephony (SIP), ai-coustics QUAIL_VF_S/L.
- **Background noise suppression** — removes non-speech noise (traffic, fans, music). Best for multi-speaker / diarization. Models: Krisp NC, ai-coustics QUAIL_L.
- **WebRTC AEC/NS** — browser-only, client-side, runs before audio is sent to the room.

WER improvement example from docs (noisy "gym membership" sample): Original 117.6% → Krisp BVC 23.5% → ai-coustics QUAIL_VF_S 7.1%.

## ai-coustics self-hosted setup (the realistic NC path for us)

```python
import os
from livekit.agents import room_io
from livekit.plugins.ai_coustics import audio_enhancement, Auth, EnhancerModel

await session.start(
    room_options=room_io.RoomOptions(
        audio_input=room_io.AudioInputOptions(
            noise_cancellation=audio_enhancement(
                model=EnhancerModel.QUAIL_VF_S,                 # voice isolation, lightweight
                auth=Auth.ai_coustics_api(license_key=os.environ["AI_COUSTICS_API_KEY"]),
            ),
        ),
    ),
)
# Install: uv add "livekit-plugins-ai-coustics"
```

> ⚠️ Don't stack NC: if NC runs in the agent, do NOT also run NC in the frontend, and vice versa.
> NC models are trained on raw audio and behave badly on already-processed audio.

## SIP troubleshooting — "bad audio quality" (official)

If audio flows both ways but sounds choppy/robotic/distorted, it's usually **network quality**
(RTP over UDP, no retransmits). Healthy thresholds:

| Metric | Healthy | Degraded |
|---|---|---|
| Packet loss | < 1% | > 3% → audible breakup |
| Jitter (mean) | < 5ms | > 20ms → choppy audio |
| One-way latency | < 150ms | > 300ms → both parties talk over each other |

Other checks: codec/payload-type match (PCMU = PT 0), `use_external_ip: true` for self-hosted SIP
(one-way audio / NAT), RTP UDP port range open in firewall (default `10000-20000`; ours is `20000-30000`).

Only after network + codec are clean: "Background noise, echo, and double-talk from the caller's
environment can degrade quality independently of the network. Enable BVC for your agent and rely
on client-side echo cancellation on the caller's device." (BVC = Cloud — see caveat above.)

> ⚠️ PCAP download + Wireshark RTP analysis is documented as a **LiveKit Cloud dashboard** feature.
> Self-hosted, we'd capture RTP on the VPS ourselves (e.g. `tcpdump` on the SIP RTP port range).
