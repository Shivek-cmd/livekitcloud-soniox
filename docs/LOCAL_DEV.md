# Local development — processes & commands

Run Sierra locally with **three terminals** (plus optional admin).  
Windows PowerShell examples below; bash is the same except path separators.

> **VPS production** is separate — see [`vps-config.md`](vps-config.md).  
> Never commit `.env` files.

---

## Prerequisites

| Tool | Notes |
|------|--------|
| Python 3.10+ | Managed with [uv](https://github.com/astral-sh/uv) |
| Node.js 18+ | For `web/` and `admin/` |
| Secrets | Copy from VPS (below) or fill `.env.example` |

```powershell
cd "D:\Chrishan Solution\livekitcloud-soniox"   # or your clone path
uv sync
cd web; npm install; cd ..
cd admin; npm install; cd ..
```

---

## Env files (from VPS)

Production secrets live on the VPS. Capture them once:

```bash
ssh root@89.117.18.192
cd /opt/livekit-sarvam

# Agent + token server → paste into repo root `.env`
cat .env

# Admin dashboard → paste into `admin/.env`
cat admin/.env

# Web usually has no env (same-origin /token)
ls -la web/.env* 2>/dev/null
```

| VPS path | Local path |
|----------|------------|
| `/opt/livekit-sarvam/.env` | `.env` (repo root) |
| `/opt/livekit-sarvam/admin/.env` | `admin/.env` |
| `web/.env*` | not required |

Root `.env` must include at least: `LIVEKIT_*`, `SONIOX_API_KEY`, `OPENAI_API_KEY`, `USE_CLOVER_MENU=1`, `MENU_CACHE_PATH`, `VOICE_LABELS_PATH`, and (for analytics) `SUPABASE_*`.

---

## What to run (cheat sheet)

| # | Process | Port | Required for |
|---|---------|------|----------------|
| 1 | **Token server** | `8001` | Menu + LiveKit token for web |
| 2 | **Web frontend** | `5173` | UI at localhost |
| 3 | **Agent worker** | (LiveKit) | Voice / Order with Sierra |
| 4 | Admin (optional) | `5173` or next free | `admin.bizbull.ai` locally |

For **menu only**: terminals 1 + 2.  
For **voice ordering**: terminals 1 + 2 + 3.

---

## Terminal 1 — Token server

```powershell
cd "D:\Chrishan Solution\livekitcloud-soniox"
uv run python -m uvicorn token_server:app --host 0.0.0.0 --port 8001 --reload
```

Check:

```powershell
curl.exe -s http://127.0.0.1:8001/health
# {"status":"ok"}

curl.exe -s -o NUL -w "%{http_code}\n" http://127.0.0.1:8001/menu
# 200
```

### Windows note (`uv trampoline`)

Do **not** use:

```powershell
uv run uvicorn token_server:app ...   # fails: "uv trampoline failed to canonicalize script path"
```

Use `uv run python -m uvicorn ...` instead (path with spaces / Windows shim bug).

---

## Terminal 2 — Web frontend (`voice.bizbull.ai`)

```powershell
cd "D:\Chrishan Solution\livekitcloud-soniox\web"
npm run dev
```

Open: **http://localhost:5173**

Vite proxies `/token`, `/menu`, `/health`, `/store` → `http://127.0.0.1:8001` (see `web/vite.config.ts`).  
If you change the proxy, **restart** `npm run dev`.

**Store tab:** needs token server + web only (no agent). Full place uses `POST /store/checkout` (Clover + n8n kill switches same as voice). Confirm SMS fires for **pickup and delivery** when `N8N_SYNC_ENABLED=1`. Optional **Pay now** when `STORE_PAY_NOW_ENABLED=1` + Ecommerce token (see [`plan/15-store-optional-payment.md`](plan/15-store-optional-payment.md)). Demo dish photos: `STORE_DEMO_IMAGES=1` (default) fills missing Clover images via Unsplash on `GET /menu`.

Theme: light default; dark/light toggle in the header.

---

## Terminal 3 — Agent (voice)

```powershell
cd "D:\Chrishan Solution\livekitcloud-soniox"
uv run python agent.py dev
```

Phone-style session (optional):

```powershell
uv run python agent.py dev --phone
```

Without this process, the UI and menu work, but **Order with Sierra** cannot join a LiveKit room with the agent.

---

## Optional — Admin dashboard

```powershell
cd "D:\Chrishan Solution\livekitcloud-soniox\admin"
npm run dev
```

Needs `admin/.env` with `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY`.  
Login: same credentials as production `admin.bizbull.ai` (from project owner).

---

## Quick troubleshooting

| Symptom | Fix |
|---------|-----|
| “Couldn’t load the menu” | Token server not running, or Vite proxy missing / frontend not restarted |
| Store checkout 404 / HTML response | Vite `/store` proxy missing, or VPS Caddy missing `handle /store*` |
| Store “too many attempts” | Rate limit — wait ~60s or raise `STORE_CHECKOUT_RATE_LIMIT` |
| Pay now button missing | `STORE_PAY_NOW_ENABLED` off or `/store/config` unreachable |
| Pay now places but no Clover page | Missing `CLOVER_ECOM_PRIVATE_TOKEN` / HCO create failed (order still placed) |
| No receipt after pay | Clover webhook URL/secret not set, or n8n `order.paid` branch missing |
| Menu OK, call fails | Start agent (`agent.py dev`) |
| `uv trampoline failed…` | Use `uv run python -m uvicorn ...` |
| Empty menu / 500 on `/menu` | Ensure `USE_CLOVER_MENU=1` and `data/menu_cache_bizbull.json` exists; sync from Clover if needed |
| Admin blank / auth fail | Check `admin/.env` anon key |

Sync menu from Clover (if cache missing/stale):

```powershell
uv run python scripts/clover_sync_menu.py
uv run python scripts/rebuild_voice_labels.py
```

---

## Tests

```powershell
$env:PYTHONPATH = "."
uv run pytest tests/ -q
```

---

## Related docs

- [`DEVELOPER_ONBOARDING.md`](DEVELOPER_ONBOARDING.md) — architecture, env map, VPS deploy  
- [`vps-config.md`](vps-config.md) — production services & Caddy  
- [`HANDOFF.md`](HANDOFF.md) — current product state  
