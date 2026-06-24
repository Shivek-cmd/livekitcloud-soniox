# Twilio SIP Integration

## How It Works

Twilio acts as a **SIP relay only** — it does not process audio. The flow is:

```
User's Phone
    │
    │ PSTN
    ▼
Twilio (+91 number)
    │
    │ SIP trunk (UDP/TCP, port 5060)
    ▼
LiveKit SIP Service
    │
    │ Creates SIP participant in LiveKit room
    ▼
LiveKit Server
    │
    │ Audio frames (internally as WebRTC)
    ▼
Agent Worker (same Python code as web channel)
```

Twilio is unaware of Sarvam or the agent. It just routes SIP audio.

---

## Twilio Setup Steps

### 1. Create Elastic SIP Trunk

In Twilio Console → Voice → SIP Trunking → Trunks → Create:

- **Friendly Name**: `livekit-punjabi-agent`
- **Origination SIP URI**: `sip:livekit.yourdomain.com:5060`
- **Codecs**: G.711 µ-law (PCMU) — default, works with LiveKit SIP

### 2. Buy Indian Phone Number

Twilio Console → Phone Numbers → Buy → India (+91):
- Select a local or toll-free number
- Assign to the SIP trunk above

### 3. Allowlist Twilio IPs on Firewall

Twilio's SIP signaling IPs (add to server firewall for port 5060):
```
54.172.60.0/30
54.244.51.0/30
54.171.127.192/30
52.215.127.0/30
54.65.63.192/30
54.169.127.128/30
54.252.254.64/30
177.71.206.192/30
```
*(Check Twilio docs for latest IP ranges — they update periodically)*

### 4. Configure LiveKit SIP Inbound Trunk

Using LiveKit CLI or REST API:

```bash
lk sip inbound create \
  --name "twilio-punjabi" \
  --numbers "+91XXXXXXXXXX" \
  --allowed-addresses "54.172.60.0/30,54.244.51.0/30"  # Twilio IPs
```

### 5. Create Dispatch Rule

Controls what happens when a call comes in — here every caller gets their own room and triggers a new agent session:

```bash
lk sip dispatch create \
  --trunk-id <inbound-trunk-id> \
  --rule-type individual-room \
  --room-prefix "phone-call-"
```

---

## Audio Codec Consideration

| Channel | Codec | Sample Rate |
|---|---|---|
| Web (WebRTC) | Opus | 48kHz |
| Phone (Twilio SIP) | G.711 PCMU | 8kHz |

LiveKit SIP Service handles the codec transcoding automatically. Sarvam STT accepts 16kHz — LiveKit upsamples from 8kHz internally before passing to the agent.

> This 8kHz→16kHz upsampling may slightly reduce STT accuracy for phone calls vs web. Monitor and compare.

---

## Agent Metadata: Detect Channel in Code

When a SIP participant joins, LiveKit sets participant attributes. You can detect the channel in `agent.py`:

```python
async def entrypoint(ctx):
    is_phone_call = any(
        p.attributes.get("sip.callStatus") == "active"
        for p in ctx.room.remote_participants.values()
    )

    if is_phone_call:
        # Phone-specific adjustments
        # e.g., shorter TTS sentences, no visual cues
        pass
```

---

## Outbound Calls (Future)

To have the agent call a user proactively:

```python
from livekit import api

lk = api.LiveKitAPI(url, api_key, api_secret)
await lk.sip.create_sip_participant(
    api.CreateSIPParticipantRequest(
        sip_trunk_id="<outbound-trunk-id>",
        sip_call_to="+91XXXXXXXXXX",
        room_name="outbound-room-1",
        participant_identity="caller",
    )
)
```

---

## Testing Without Real Twilio

Use a SIP softphone (e.g., Zoiper, Linphone) configured to point directly at `livekit.yourdomain.com:5060` — bypasses Twilio for local SIP testing.
