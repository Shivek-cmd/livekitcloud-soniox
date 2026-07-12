"""Voice stack: Soniox STT + OpenAI (GPT) LLM + Soniox TTS.

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

    def __getattr__(self, name):
        return getattr(self._inner_ws, name)


class _ConfigInjectingSession:
    """aiohttp session proxy whose ws_connect yields a _ConfigInjectingWS."""

    def __init__(self, session, extra_config: dict):
        self._inner_session = session
        self._extra_config = extra_config

    def ws_connect(self, *args, **kwargs):
        request = self._inner_session.ws_connect(*args, **kwargs)

        async def _connect():
            return _ConfigInjectingWS(await request, self._extra_config)

        return _connect()

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


def build_llm():
    return openai.LLM(model="gpt-4o-mini")


def build_tts(is_phone: bool):
    # One voice speaks all 60+ languages; "pa" sets the primary language while
    # English/Hindi words inside a Punjabi sentence are handled automatically.
    return soniox.TTS(
        model="tts-rt-v1",
        voice="Maya",
        language="pa",
    )
