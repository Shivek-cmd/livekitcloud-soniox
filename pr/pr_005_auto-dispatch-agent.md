# PR 005 — Fix: Auto-dispatch agent on token request

## Problem
Joining a LiveKit room does not automatically assign an agent worker.
The worker sits idle waiting for an explicit dispatch job.
The LiveKit Cloud Console was dispatching it manually; the web frontend was not.

## Fix
`token_server.py` now calls `lk.agent_dispatch.create_dispatch()` after
minting the room token, so the agent joins before the customer even connects.

## Files Changed
- `token_server.py` — added `LiveKitAPI` + `CreateAgentDispatchRequest` dispatch call
