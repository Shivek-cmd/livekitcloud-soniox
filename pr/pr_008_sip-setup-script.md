# PR 008 — SIP setup script + phone channel working

## Summary
Phone channel fully working via Twilio → LiveKit SIP → agent.
Added reproducible setup script so SIP can be reconfigured after server wipes.

## What was configured (already live on VPS)
- LiveKit SIP inbound trunk `ST_ULoCL8A6UHRs` → `+15878175156`
- Dispatch rule `SDR_VJLPyAuaAwEv` → `phone-*` rooms
- `room_config.agents = [RoomAgentDispatch(agent_name="")]` → agent auto-dispatches on every call
- Twilio trunk `parkash-liveket` → origination `sip:lk.bizbull.ai:5060;transport=udp`

## Key fix
The SIP dispatch rule must include `room_config.agents` to auto-dispatch the agent.
Without it the room is created but the agent never joins.

## Files Added
- `scripts/setup_sip.py` — idempotent SIP setup script (safe to re-run)

## Usage
```bash
uv run python scripts/setup_sip.py
```
