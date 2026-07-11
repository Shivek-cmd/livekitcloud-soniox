# Local testing — run Sierra fully on your machine

How to test the voice agent end-to-end on localhost **without touching the
VPS/production**, and how to clean up afterwards. Companion to
[`docs/LOCAL_DEV.md`](docs/LOCAL_DEV.md) (setup details, env file sources,
troubleshooting).

> Written while testing PR 064 (Soniox endpoint tuning), but the procedure is
> general — use it for any PR that changes voice behavior.

---

## Why the agent-name swap matters

Your local worker and the production VPS worker register with the **same
LiveKit Cloud project**. If both use the agent name `restaurant-agent`,
LiveKit load-balances dispatch between them — a call from your local web UI
can silently land on the **VPS worker running old code**, and a production
call can land on your laptop.

Both dispatch points read an `AGENT_NAME` env var (default
`restaurant-agent`): the worker registration (`restaurant/agent/worker.py`)
and the token server's room dispatch (`token_server.py`). Setting a
local-only name isolates you completely.

---

## 1. One-time setup

```bash
uv sync
cd web && npm install && cd ..
```

`.env` at the repo root must exist (copy values from the VPS — see
`docs/LOCAL_DEV.md` "Env files"). Then add the local-testing block:

```bash
# TEMP local dev — route dispatch to local worker only (remove before deploy)
AGENT_NAME=restaurant-agent-local
```

Safety checks before testing orders:

| Var | Safe local value | Why |
|-----|------------------|-----|
| `AGENT_NAME` | `restaurant-agent-local` | Isolates you from the VPS worker |
| `CLOVER_BASE_URL` | `https://apisandbox.dev.clover.com` | Orders go to Clover **sandbox**, not a real kitchen |
| `CLOVER_SUBMIT_ORDERS` | `0` (or `1` only with sandbox URL) | `0` = log-only shadow mode |
| `SESSION_ANALYTICS_ENABLED` | `0` if you don't want test calls in prod Supabase | Analytics writes to the production admin dashboard |

## 2. Launch (three processes)

```bash
mkdir -p /tmp/sierra-logs

# Terminal/process 1 — token server (:8001)
uv run python -m uvicorn token_server:app --host 0.0.0.0 --port 8001 \
  > /tmp/sierra-logs/token_server.log 2>&1 &

# Terminal/process 2 — web frontend (:5173)
(cd web && npm run dev > /tmp/sierra-logs/web_dev.log 2>&1 &)

# Terminal/process 3 — agent worker
uv run python agent.py dev > /tmp/sierra-logs/agent.log 2>&1 &
```

## 3. Verify before calling

```bash
curl -s http://127.0.0.1:8001/health          # {"status":"ok"}
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8001/menu   # 200
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5173/       # 200

# Worker must be registered under the LOCAL name:
grep -o 'registered worker.*agent_name[^,]*' /tmp/sierra-logs/agent.log
# → "agent_name": "restaurant-agent-local"
```

If it says `restaurant-agent` (no `-local`), the worker didn't pick up
`AGENT_NAME` — check `.env` and restart the worker.

## 4. Test a call

Open **http://localhost:5173** → *Order with Sierra* → allow the mic → talk.
**Use headphones** — on speakers, the mic picks up Sierra's own voice and the
ambient music, which delays Soniox end-of-speech detection and skews any
latency measurement.

Confirm the session hit YOUR worker (a `Session started` line must appear):

```bash
grep "Session started" /tmp/sierra-logs/agent.log
```

Watch the conversation and latency live:

```bash
tail -f /tmp/sierra-logs/agent.log | grep -E "USER:|SIERRA:|LATENCY|Ignoring"
```

Latency lines to read (`turn-latency` logger):

```
LATENCY turn=2 | channel=web | user="..." | eou_delay=…s | user_stop→thinking=…ms | user_stop→speaking=…ms | llm_ttft=…s
```

- `user_stop→speaking` — the perceived gap (stop talking → Sierra's voice).
- `eou_delay` / `transcript_delay` (DEBUG `received user transcript`) — how
  long Soniox took to finalize after speech stopped. This is what
  `SONIOX_MAX_ENDPOINT_DELAY_MS` / `SONIOX_ENDPOINT_SENSITIVITY` tune (PR 064).

To A/B endpoint settings: change the values in `.env`, restart **only** the
worker (`pkill -f "agent.py dev"`, relaunch), call again, compare.

## 5. Restarting / stopping processes

```bash
pkill -f "uvicorn token_server"   # token server
pkill -f "agent.py dev"           # agent worker
pkill -f "vite"                   # web frontend
```

Only the worker needs a restart when you change agent code or `.env` voice
vars; the token server needs one only if you change `AGENT_NAME` or
token/menu code.

---

## When local testing is complete

1. **Stop all three processes** (commands above).
2. **Remove the temp block from `.env`** — delete the `AGENT_NAME=…` line
   (and its comment). If you disabled analytics or Clover submit for testing,
   restore the values you started with. `.env` is gitignored — never commit it.
3. **Run the test suite**: `uv run python -m pytest tests/ -q`.
4. **Check the working tree**: `git status` — only files that belong to the
   PR should be modified; temp experiments and scratch files must not be
   committed.
5. **Commit on the PR branch** and update the `pr/pr_NNN_*.md` doc in the
   same commit (`pr/pr_rules.md`). Do **not** push or open the PR without the
   repo owner's explicit OK.
6. **After merge, deploy** per `docs/vps-config.md`: on the VPS, add any new
   env vars to `/opt/livekit-sarvam/.env` (for PR 064:
   `SONIOX_MAX_ENDPOINT_DELAY_MS`, optional `SONIOX_ENDPOINT_SENSITIVITY`),
   then `bash scripts/vps_deploy.sh` (or `git pull` + `systemctl restart
   restaurant-agent`). The VPS `.env` needs **no** `AGENT_NAME` — the default
   is `restaurant-agent`.
7. **Verify on production**: make a phone test call (`uv run python
   scripts/test_call.py +1…`), watch
   `journalctl -u restaurant-agent -f | grep -E "USER:|SIERRA:|LATENCY"`.
8. **Analytics hygiene**: if test sessions were recorded
   (`SESSION_ANALYTICS_ENABLED=1`), they appear in admin.bizbull.ai as `web`
   channel sessions — ignore or note them when reviewing call quality.
