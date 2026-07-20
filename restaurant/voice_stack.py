"""Voice stack: Soniox STT + OpenAI (GPT) or Google (Gemini) LLM + Soniox TTS.

All three providers are US/EU/JP-hosted, so for North-America (Canada) callers the
whole pipeline stays on-continent → low latency. Soniox handles Punjabi/English/Hindi
code-mixing automatically.

Kept as small factory functions (rather than inlined into agent.py) so a future
multi-tenant build can vary voice/model per restaurant without touching agent logic.
"""

import json
import os

from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS
from livekit.plugins import openai, soniox
from livekit.plugins.soniox.stt import SpeechStream as _SonioxSpeechStream

# Sentinel env values that mean "explicitly no value — use the Soniox server
# default" (as opposed to an absent var, which gets our tuned default).
_EXPLICIT_UNSET = ("", "none", "unset", "default")


def stt_max_endpoint_delay_ms() -> int:
    """Soniox server-side endpoint delay cap (SONIOX_MAX_ENDPOINT_DELAY_MS).

    With no explicit VAD, the user's turn only commits once Soniox finalizes
    the transcript — which happens when its endpoint model fires. The plugin
    default of 2000ms adds up to ~2s of dead air before the LiveKit turn
    detector and endpointing window even start. Clamped to Soniox's valid
    500–3000 range so a bad env var can't crash the worker at startup.
    """
    raw = os.getenv("SONIOX_MAX_ENDPOINT_DELAY_MS", "").strip()
    if not raw:
        return 1000
    try:
        value = int(float(raw))
    except ValueError:
        return 1000
    return max(500, min(3000, value))


def stt_endpoint_sensitivity() -> float | None:
    """Soniox endpoint sensitivity (SONIOX_ENDPOINT_SENSITIVITY), -1.0 to 1.0.

    Higher = finalize sooner. Defaults to 0.3, Soniox's recommended voice-AI
    starting point — in continuous background noise (our deployment context)
    the neutral endpoint model can sit on a final for many seconds
    (turnwatchdog.md Part I). Set the var to ""/none/unset to fall back to the
    Soniox server default. Too aggressive cuts off callers who pause
    mid-sentence (phone-number dictation especially) — the PR 067 watchdog +
    order gates are the backstop.
    """
    if "SONIOX_ENDPOINT_SENSITIVITY" not in os.environ:
        return 0.3
    raw = os.environ["SONIOX_ENDPOINT_SENSITIVITY"].strip().lower()
    if raw in _EXPLICIT_UNSET:
        return None
    try:
        value = float(raw)
    except ValueError:
        return 0.3
    return max(-1.0, min(1.0, value))


def stt_endpoint_latency_adjustment_level() -> int | None:
    """Soniox endpoint latency adjustment (SONIOX_ENDPOINT_LATENCY_ADJUSTMENT_LEVEL).

    0–3; higher = lower endpoint latency. Defaults to 2 (Soniox voice-AI rec).
    Set to ""/none/unset to skip sending the field entirely (server default).
    The installed plugin (livekit-plugins-soniox 1.6.5) doesn't expose this
    knob, so build_stt injects it into the raw WS config — None disables that
    injection.
    """
    if "SONIOX_ENDPOINT_LATENCY_ADJUSTMENT_LEVEL" not in os.environ:
        return 2
    raw = os.environ["SONIOX_ENDPOINT_LATENCY_ADJUSTMENT_LEVEL"].strip().lower()
    if raw in _EXPLICIT_UNSET:
        return None
    try:
        value = int(float(raw))
    except ValueError:
        return 2
    return max(0, min(3, value))


class _ConfigInjectingWS:
    """Merges extra keys into the first JSON message sent on a Soniox WS.

    The plugin sends exactly one JSON config message right after connecting
    (plugins/soniox/stt.py:_connect_ws); keepalives and audio frames follow.
    Only that first send_str is rewritten. Everything else delegates to the
    real aiohttp websocket.
    """

    def __init__(self, ws, extra_config: dict):
        self._inner_ws = ws
        self._extra_config = extra_config
        self._config_sent = False

    async def send_str(self, data: str):
        if not self._config_sent:
            self._config_sent = True
            try:
                config = json.loads(data)
                config.update(self._extra_config)
                data = json.dumps(config)
            except (ValueError, TypeError):
                pass
        return await self._inner_ws.send_str(data)

    def __aiter__(self):
        # Dunder lookup bypasses __getattr__, so delegate iteration explicitly
        # (the plugin reads messages with `async for msg in ws`).
        return self._inner_ws.__aiter__()

    def __getattr__(self, name):
        return getattr(self._inner_ws, name)


class _WSConnectHandle:
    """Wraps aiohttp's ws_connect return value, preserving its dual nature.

    aiohttp's ws_connect returns an awaitable *context manager*; the plugin
    currently awaits it, but `async with` must keep working too so a plugin
    upgrade doesn't break silently (same duck-typing bug class as __aiter__).
    """

    def __init__(self, request, extra_config: dict):
        self._request = request
        self._extra_config = extra_config

    def __await__(self):
        return self._connect().__await__()

    async def _connect(self):
        return _ConfigInjectingWS(await self._request, self._extra_config)

    async def __aenter__(self):
        return _ConfigInjectingWS(await self._request.__aenter__(), self._extra_config)

    async def __aexit__(self, exc_type, exc, tb):
        return await self._request.__aexit__(exc_type, exc, tb)


class _ConfigInjectingSession:
    """aiohttp session proxy whose ws_connect yields a _ConfigInjectingWS."""

    def __init__(self, session, extra_config: dict):
        self._inner_session = session
        self._extra_config = extra_config

    def ws_connect(self, *args, **kwargs):
        return _WSConnectHandle(
            self._inner_session.ws_connect(*args, **kwargs), self._extra_config
        )

    def __getattr__(self, name):
        return getattr(self._inner_session, name)


class _ConfigInjectingSpeechStream(_SonioxSpeechStream):
    def __init__(self, *, stt, conn_options, extra_config: dict):
        super().__init__(stt=stt, conn_options=conn_options)
        self._extra_config = extra_config

    def _ensure_session(self):
        return _ConfigInjectingSession(super()._ensure_session(), self._extra_config)


class _ConfigInjectingSTT(soniox.STT):
    """Soniox STT that adds WS config fields STTOptions doesn't expose yet.

    Stopgap for endpoint_latency_adjustment_level until the plugin grows the
    field (upstream ask in pr/pr_066_noise-robust-endpointing.md). With an
    empty extra_config this behaves exactly like the stock plugin.
    """

    def __init__(self, *, extra_config: dict, **kwargs):
        super().__init__(**kwargs)
        self._extra_config = extra_config

    def stream(self, *, language=None, conn_options=DEFAULT_API_CONNECT_OPTIONS):
        if not self._extra_config:
            return super().stream(conn_options=conn_options)
        return _ConfigInjectingSpeechStream(
            stt=self, conn_options=conn_options, extra_config=self._extra_config
        )


def build_stt(is_phone: bool):
    extra_config: dict = {}
    latency_level = stt_endpoint_latency_adjustment_level()
    if latency_level is not None:
        extra_config["endpoint_latency_adjustment_level"] = latency_level
    return _ConfigInjectingSTT(
        extra_config=extra_config,
        params=soniox.STTOptions(
            model="stt-rt-v5",
            language_hints=["pa", "en", "hi"],
            enable_language_identification=True,
            max_endpoint_delay_ms=stt_max_endpoint_delay_ms(),
            endpoint_sensitivity=stt_endpoint_sensitivity(),
        ),
    )


def llm_model_name() -> str:
    """LLM model id (LLM_MODEL, falling back to OPENAI_LLM_MODEL).

    PR 080 widens the model choice beyond OpenAI: any `gemini-*` id routes to
    the Google plugin (see build_llm). LLM_MODEL is the provider-agnostic knob;
    OPENAI_LLM_MODEL is kept as a fallback so the PR 074 rollback instructions
    (OPENAI_LLM_MODEL=gpt-4o-mini) keep working without a deploy.
    """
    raw = os.getenv("LLM_MODEL", "").strip() or os.getenv("OPENAI_LLM_MODEL", "").strip()
    return raw or "gpt-4.1-mini"


def is_gemini_model(model: str) -> bool:
    return model.startswith("gemini")


def gemini_thinking_budget() -> int:
    """Gemini thinking-token budget (GEMINI_THINKING_BUDGET), default 0.

    Gemini 2.5 models ship with dynamic thinking ON — unbounded seconds of
    silent reasoning before the first spoken token, unacceptable on a live
    call. 0 disables thinking entirely; raise only with latency data. Note:
    gemini-*-pro models refuse budget 0 (their API minimum is 128) — build_llm
    floors the budget there for pro ids so a default config can't 400.
    """
    raw = os.getenv("GEMINI_THINKING_BUDGET", "").strip()
    if not raw:
        return 0
    try:
        return max(0, int(float(raw)))
    except ValueError:
        return 0


def llm_fallback_model_name() -> str | None:
    """Fallback LLM for gemini primaries (LLM_FALLBACK_MODEL), default
    gpt-4.1-mini; set to none/off to disable.

    PR 080 finding: Gemini's NON-configurable PROHIBITED_CONTENT filter
    deterministically blocked a reply once the conversation had accumulated
    name + phone + delivery address (delivery_split_phone, 3/3 repro) — which
    every delivery order does. The google plugin surfaces that block as
    APIStatusError, so a FallbackAdapter hands the turn to OpenAI instead of
    leaving dead air. Money path stays in code (PR 030 lesson).
    """
    raw = os.getenv("LLM_FALLBACK_MODEL", "").strip()
    if raw.lower() in ("none", "off", "0", "disabled"):
        return None
    return raw or "gpt-4.1-mini"


def gemini_thinking_level() -> str:
    """Gemini 3 thinking level (GEMINI_THINKING_LEVEL), default "low" —
    the generation's minimum; it cannot be disabled outright like 2.5's
    thinking_budget=0. "high" only with latency data."""
    raw = os.getenv("GEMINI_THINKING_LEVEL", "").strip().lower()
    return raw if raw in ("low", "high") else "low"


def build_llm():
    model = llm_model_name()
    if not is_gemini_model(model):
        return openai.LLM(model=model)

    from livekit.agents.llm import FallbackAdapter
    from livekit.plugins import google

    api_key = os.getenv("GEMINI_API_KEY", "").strip() or os.getenv(
        "GOOGLE_API_KEY", ""
    ).strip()
    kwargs: dict = {"model": model}
    if api_key:
        kwargs["api_key"] = api_key
    if model.startswith("gemini-3"):
        # Gemini 3 replaced thinking_budget with thinking_level; "low" is its
        # minimum (thinking cannot be fully disabled on this generation).
        kwargs["thinking_config"] = {
            "thinking_level": gemini_thinking_level(),
            "include_thoughts": False,
        }
    else:
        budget = gemini_thinking_budget()
        if "pro" in model:
            budget = max(128, budget)
        kwargs["thinking_config"] = {
            "thinking_budget": budget,
            "include_thoughts": False,
        }
    primary = google.LLM(**kwargs)

    fallback_model = llm_fallback_model_name()
    if fallback_model is None:
        return primary
    # attempt_timeout is passed through as the google client deadline, whose
    # API-enforced minimum is 10s — the 5s adapter default 400s every request.
    return FallbackAdapter(
        [primary, openai.LLM(model=fallback_model)], attempt_timeout=10.0
    )


def build_tts(is_phone: bool):
    # One voice speaks all 60+ languages; "pa" sets the primary language while
    # English/Hindi words inside a Punjabi sentence are handled automatically.
    return soniox.TTS(
        model="tts-rt-v1",
        voice="Maya",
        language="pa",
    )
