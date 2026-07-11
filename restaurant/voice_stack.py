"""Voice stack: Soniox STT + OpenAI (GPT) LLM + Soniox TTS.

All three providers are US/EU/JP-hosted, so for North-America (Canada) callers the
whole pipeline stays on-continent → low latency. Soniox handles Punjabi/English/Hindi
code-mixing automatically.

Kept as small factory functions (rather than inlined into agent.py) so a future
multi-tenant build can vary voice/model per restaurant without touching agent logic.
"""

import os

from livekit.plugins import openai, soniox


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

    Higher = finalize sooner. Unset = Soniox neutral default — raise only with
    live-call evidence; too aggressive cuts off callers who pause mid-sentence
    (phone-number dictation especially).
    """
    raw = os.getenv("SONIOX_ENDPOINT_SENSITIVITY", "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return max(-1.0, min(1.0, value))


def build_stt(is_phone: bool):
    return soniox.STT(
        params=soniox.STTOptions(
            model="stt-rt-v5",
            language_hints=["pa", "en", "hi"],
            enable_language_identification=True,
            max_endpoint_delay_ms=stt_max_endpoint_delay_ms(),
            endpoint_sensitivity=stt_endpoint_sensitivity(),
        )
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
