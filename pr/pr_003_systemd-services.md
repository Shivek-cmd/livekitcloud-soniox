# PR 003 — Systemd services for agent and token server

## Summary
Add systemd service files so the agent worker and token server run permanently
on the VPS and restart automatically on failure or reboot.

## Files Added
- `deploy/restaurant-agent.service` — systemd unit for the voice agent worker
- `deploy/restaurant-token.service` — systemd unit for the FastAPI token server

## VPS Install Commands
Run these once after pulling to main:

```bash
# Copy service files
cp /opt/livekit-sarvam/deploy/restaurant-agent.service /etc/systemd/system/
cp /opt/livekit-sarvam/deploy/restaurant-token.service /etc/systemd/system/

# Reload systemd and enable + start both
systemctl daemon-reload
systemctl enable restaurant-agent restaurant-token
systemctl start restaurant-agent restaurant-token

# Check status
systemctl status restaurant-agent
systemctl status restaurant-token
```

## Logs
```bash
journalctl -u restaurant-agent -f    # agent logs (live)
journalctl -u restaurant-token -f    # token server logs (live)
```
