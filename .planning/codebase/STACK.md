# Technology Stack

**Analysis Date:** 2026-07-14

## Languages

**Primary:**
- Python 3.10+ - Backend agent, token server, order processing, analytics
- TypeScript 5.5.3 - Web and admin frontends
- JavaScript/JSX - React component layer

**Secondary:**
- Shell scripts - Deployment and setup (scripts/)

## Runtime

**Environment:**
- Python 3.10+ (backend)
- Node.js 18+ (web/admin frontends)

**Package Manager:**
- `uv` (Python) - Configured via `pyproject.toml`
- `npm` (Node.js) - Managed via `package.json` in web/ and admin/
- Lockfile: `uv.lock` (Python dependencies)

## Frameworks

**Core Backend:**
- LiveKit Agents SDK 1.0–2.0 - Voice agent orchestration (`restaurant/agent/worker.py`)
- FastAPI - Token server and HTTP endpoints (`token_server.py`)
- Uvicorn with standard extras - ASGI server

**Frontend:**
- React 18.3.1 - Web UI (web/src) and admin dashboard (admin/src)
- Vite 5.4.1 - Development server and bundler (configured in `web/vite.config.ts`, `admin/vite.config.ts`)
- @livekit/components-react 2.0.0 - LiveKit UI primitives for web client
- react-router-dom 6.28.0 - Routing in admin dashboard

**Testing:**
- pytest with pytest_cache - Test runner for Python (tests/ directory)
- TypeScript via tsc - Type checking for frontends

**Build/Dev:**
- Vite with React plugin - Fast dev server and optimized builds
- TypeScript - Type checking (ES2020 target, strict mode)
- @vitejs/plugin-react 4.3.1 - JSX transformation

## Key Dependencies

**Critical Backend:**
- livekit-agents >=1.0,<2.0 - Voice agent framework
- livekit-plugins-soniox - Soniox STT/TTS integration (Punjabi/English/Hindi code-mixing)
- livekit-plugins-openai - GPT-4o-mini LLM integration
- livekit-plugins-noise-cancellation >=0.2.5 - Noise cancellation for phone calls

**Infrastructure:**
- fastapi - HTTP framework for token server
- uvicorn[standard] - ASGI server with C extensions
- python-dotenv - Environment variable loading
- supabase >=2.0 - Analytics database client (`restaurant/analytics/analytics_store.py`)
- twilio >=9.0 - SIP/phone integration (`scripts/setup_twilio_sip.py`)

**Frontend (web):**
- livekit-client 2.0.0 - LiveKit WebRTC client
- @livekit/components-react 2.0.0 - Reusable LiveKit React components
- @livekit/components-styles 1.0.0 - Default LiveKit component styling

**Frontend (admin):**
- @supabase/supabase-js 2.49.0 - Supabase client for calls/orders dashboard

## Configuration

**Environment:**
- Loaded via `python-dotenv` from `.env` file
- Required vars: `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `LIVEKIT_URL`
- Optional: `CLOVER_*` (Clover POS integration), `SUPABASE_*` (analytics), `SONIOX_*` (STT tuning), `TWILIO_*` (SIP)

**Build:**
- `web/tsconfig.json` - TypeScript strict mode, ES2020 target, JSX support
- `web/vite.config.ts` - Vite dev server proxies `/token`, `/menu`, `/health` → token server (127.0.0.1:8001)
- `admin/tsconfig.json` - Same config as web
- `admin/vite.config.ts` - Standard Vite + React plugin
- `pyproject.toml` - Defines Python project metadata, dependencies, and version

## Platform Requirements

**Development:**
- Python 3.10+
- Node 18+
- LiveKit local binary or Docker image (for local testing)
- Supabase account or docker-compose setup (for analytics)

**Production:**
- Docker (see deploy/ directory)
- LiveKit cloud or self-hosted server
- Caddy reverse proxy (for web/token/menu routing)
- Supabase cloud or PostgreSQL instance (for analytics)
- Clover POS account (optional, for order submission)
- Twilio account (for SIP phone integration)
- OpenAI API key (for LLM)
- Soniox account (for STT/TTS)

---

*Stack analysis: 2026-07-14*
