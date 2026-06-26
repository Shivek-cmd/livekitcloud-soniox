"""Voice stack: Soniox STT + OpenAI (GPT) LLM + Soniox TTS.

All three providers are US/EU/JP-hosted, so for North-America (Canada) callers the
whole pipeline stays on-continent → low latency. Soniox handles Punjabi/English/Hindi
code-mixing automatically.

Kept as small factory functions (rather than inlined into agent.py) so a future
multi-tenant build can vary voice/model per restaurant without touching agent logic.
"""

from livekit.plugins import openai, soniox


def build_stt(is_phone: bool):
    return soniox.STT(
        params=soniox.STTOptions(
            model="stt-rt-v5",
            language_hints=["pa", "en", "hi"],
            enable_language_identification=True,
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
