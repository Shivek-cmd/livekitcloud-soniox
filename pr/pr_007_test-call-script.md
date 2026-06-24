# PR 007 — Twilio outbound test call script

## Summary
Script to have Twilio call a phone number and connect them to the LiveKit
voice agent. Avoids international call charges — Twilio dials the recipient,
and when they pick up they're bridged into the LiveKit SIP agent.

## Files Changed
- `scripts/test_call.py` — outbound call script
- `pyproject.toml` — added `twilio>=9.0` dependency

## .env additions required on VPS
```
TWILIO_ACCOUNT_SID=AC02b35d544672eb20c553c7c0b7d2291e
TWILIO_AUTH_TOKEN=ef3bf837081b393a37d24654ff6eecbf
```

## VPS setup after merge
```bash
cd /opt/livekit-sarvam && git pull origin main && uv sync
```

## Usage
```bash
# Calls default number (+919413752688)
uv run python scripts/test_call.py

# Calls any number
uv run python scripts/test_call.py +919999999999
```
