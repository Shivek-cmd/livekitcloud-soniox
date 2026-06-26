# Phone Channel — Twilio → LiveKit Cloud SIP

## How It Works

Twilio is a **SIP relay only**. Inbound calls are handed to **LiveKit Cloud's** SIP service (not a
self-hosted SIP container).

```
Caller's Phone (Canada)
    │ PSTN
    ▼
Twilio (+15878175156)
    │ SIP trunk
    ▼
LiveKit Cloud SIP  (sip:<project>.sip.livekit.cloud)
    │ creates a SIP participant in a per-caller room
    ▼
LiveKit Cloud room
    │ agent subscribes over wss
    ▼
Agent Worker (Python on VPS) → Soniox STT → GPT → Soniox TTS
```

Twilio is unaware of Soniox/GPT or the agent — it just routes SIP audio. Echo cancellation is handled
inside LiveKit Cloud (telephony media path + trunk-level Krisp).

---

## LiveKit Cloud SIP setup

Configured against the **Cloud** project credentials via `scripts/setup_sip.py`, which creates:
- an **inbound trunk** bound to the Twilio number (`krisp_enabled=True` for trunk-level NC), and
- a **dispatch rule** that gives each caller their own room and dispatches
  `RoomAgentDispatch(agent_name="restaurant-agent")`.

```bash
# Run with the Cloud LIVEKIT_URL/API_KEY/API_SECRET in the environment
KRISP_ENABLED=1 uv run python scripts/setup_sip.py
```

> The explicit `agent_name="restaurant-agent"` is important: it ensures *our* agent (not another
> worker on the same project) answers, and avoids non-deterministic routing.

---

## Twilio setup

1. **Elastic SIP Trunk** (`parkash-liveket`) → Origination URI must point at LiveKit Cloud:
   `sip:5qg9858y0ak.sip.livekit.cloud` (not the old self-hosted `lk.bizbull.ai:5060`).
2. **Phone number** `+15878175156` assigned to that trunk.
3. Codec: G.711 µ-law (PCMU) — standard for LiveKit SIP.

Reconfigure with:

```bash
uv run python scripts/setup_twilio_sip.py --apply   # Twilio origination → Cloud
KRISP_ENABLED=1 uv run python scripts/setup_sip.py  # LiveKit Cloud trunk + dispatch
```

---

## Testing

Place an outbound test call (Twilio dials your phone and bridges to the Cloud SIP URI):

```bash
LIVEKIT_SIP_URI='sip:+15878175156@<project-id>.sip.livekit.cloud' \
  uv run python scripts/test_call.py +91XXXXXXXXXX
```

`scripts/test_call.py` reads `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` from `.env` and
`LIVEKIT_SIP_URI` from the environment.

---

## Detect channel in code

`agent.py` detects a phone call from the SIP participant:

```python
is_phone = (
    participant.identity.startswith("sip_")
    or participant.attributes.get("sip.callStatus") is not None
)
```

---

## Outbound calls (future)

LiveKit Cloud SIP can also originate calls (`create_sip_participant`) for proactive outbound dialing —
deferred for now (inbound only).
