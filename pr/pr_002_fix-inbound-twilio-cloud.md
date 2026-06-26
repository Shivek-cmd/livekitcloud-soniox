# PR 002 — Fix inbound calls (Twilio → LiveKit Cloud)

## Branch
`pr_002_fix-inbound-twilio-cloud`

## What This PR Does
Fixes inbound phone calls to `+15878175156`. Twilio's Elastic SIP Trunk origination URI still pointed at the old self-hosted LiveKit SIP (`lk.bizbull.ai:5060`), so dialing the number never reached the Cloud agent. Adds a reproducible script to point Twilio at LiveKit Cloud and updates the test-call default URI.

## Files Added

### `scripts/setup_twilio_sip.py`
Inspects the Twilio trunk (`parkash-liveket`) and origination URIs. With `--apply`, replaces them with `sip:5qg9858y0ak.sip.livekit.cloud`.

## Files Modified

### `scripts/test_call.py`
Default `LIVEKIT_SIP_URI` changed from self-hosted `lk.bizbull.ai:5060` to LiveKit Cloud.

### `docs/plan/07-twilio-sip.md`, `docs/vps-config.md`
Document the Twilio setup script and the inbound routing requirement.

## What's NOT in This PR
- Renaming `sarvam.bizbull.ai` domain or repo folder.
- Twilio credential changes (uses existing `.env` on VPS).

## How to Test

```bash
# On VPS — apply Twilio + confirm LiveKit Cloud SIP
uv run python scripts/setup_twilio_sip.py --apply
KRISP_ENABLED=1 uv run python scripts/setup_sip.py

# Real inbound test: dial +15878175156 from a phone
# Sierra should greet within a few seconds
```

## Post-Merge: VPS Pull Command
```bash
cd /opt/livekit-sarvam && git pull origin main && systemctl restart restaurant-agent
```
