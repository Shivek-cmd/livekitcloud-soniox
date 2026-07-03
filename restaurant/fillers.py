"""Intent-based voice fillers — short acks before LLM/tool latency (PR 031)."""

from __future__ import annotations

import os
import random
import re
from collections import deque
from enum import Enum

from restaurant.conversation import CustomerLanguage, UserIntent
from restaurant.order_flow import OrderPhase

_MAX_RECENT = 3

_BLOCKED_PHASES = frozenset({
    OrderPhase.SPECIAL_INSTRUCTIONS,
    OrderPhase.ORDER_TYPE,
    OrderPhase.DELIVERY_ADDRESS,
    OrderPhase.READBACK,
    OrderPhase.CUSTOMER_NAME,
    OrderPhase.CUSTOMER_PHONE,
    OrderPhase.READY_TO_PLACE,
    OrderPhase.PLACED,
})

_BLOCKED_INTENTS = frozenset({
    UserIntent.ORDER_DONE,
    UserIntent.CONFIRM_YES,
    UserIntent.CONFIRM_NO,
    UserIntent.PICKUP,
    UserIntent.DELIVERY,
    UserIntent.HUMAN,
    UserIntent.UNCLEAR,
})

_CHITCHAT_RE = re.compile(
    r"(?:"
    r"how are you|how r u|what.?s up|good morning|good evening|"
    r"hello|hi there|hey there|"
    r"ki haal|kiddan|kive ho|kaise ho|"
    r"ਕਿਵ(?:ੇ|ੇਂ)|ਕੀ ਹਾਲ|"
    r"कैस(?:े|ी) हो"
    r")",
    re.I,
)


class FillerKind(str, Enum):
    ACK = "ack"
    PROCESSING = "processing"


_INTENT_KIND: dict[UserIntent, FillerKind] = {
    UserIntent.ASK_PRICE: FillerKind.PROCESSING,
    UserIntent.ASK_AVAILABILITY: FillerKind.PROCESSING,
    UserIntent.ADD_ITEM: FillerKind.ACK,
    UserIntent.GENERAL: FillerKind.PROCESSING,
}


_POOLS: dict[CustomerLanguage, dict[FillerKind, tuple[str, ...]]] = {
    CustomerLanguage.ENGLISH: {
        FillerKind.ACK: ("Got it.", "Sure.", "Okay."),
        FillerKind.PROCESSING: ("Let me check.", "One moment.", "Just a sec."),
    },
    CustomerLanguage.HINDI: {
        FillerKind.ACK: ("हाँ जी.", "ठीक है.", "जी."),
        FillerKind.PROCESSING: ("एक minute.", "मैं देखती हूँ.", "ज़रा check करती हूँ."),
    },
    CustomerLanguage.PUNJABI: {
        FillerKind.ACK: ("ਹਾਂ ਜੀ.", "ਠੀਕ ਹੈ ਜੀ.", "ਬਿਲਕੁਲ ਜੀ."),
        FillerKind.PROCESSING: ("ਇੱਕ minute.", "ਮੈਂ ਵੇਖਦੀ ਹਾਂ.", "menu check kardi haan."),
    },
    CustomerLanguage.MIXED: {
        FillerKind.ACK: ("ਹਾਂ ਜੀ — sure.", "Okay ji.", "ठीक ji."),
        FillerKind.PROCESSING: ("Let me check ji.", "ਇੱਕ minute.", "One moment ji."),
    },
}


def fillers_enabled() -> bool:
    raw = os.getenv("FILLERS_ENABLED", "").strip().lower()
    if not raw:
        return False
    return raw in ("1", "true", "yes", "on")


def _pool_for_language(lang: CustomerLanguage) -> dict[FillerKind, tuple[str, ...]]:
    if lang == CustomerLanguage.MIXED:
        return _POOLS[CustomerLanguage.MIXED]
    return _POOLS.get(lang, _POOLS[CustomerLanguage.ENGLISH])


def _kind_for_intent(intent: UserIntent) -> FillerKind | None:
    key = _INTENT_KIND.get(intent)
    if key is None:
        return None
    return key


def is_chitchat_turn(text: str, intent: UserIntent) -> bool:
    """Social greeting — no latency filler needed."""
    if intent != UserIntent.GENERAL:
        return False
    t = (text or "").strip()
    if not t:
        return False
    return bool(_CHITCHAT_RE.search(t))


def should_use_filler(
    *,
    intent: UserIntent,
    phase: OrderPhase,
    user_text: str = "",
    hangup_started: bool = False,
    agent_busy: bool = False,
) -> bool:
    if not fillers_enabled():
        return False
    if hangup_started or agent_busy:
        return False
    if intent in _BLOCKED_INTENTS or phase in _BLOCKED_PHASES:
        return False
    if is_chitchat_turn(user_text, intent):
        return False
    if intent == UserIntent.GENERAL and phase == OrderPhase.BROWSING:
        return False
    return _kind_for_intent(intent) is not None


def pick_filler(
    *,
    intent: UserIntent,
    phase: OrderPhase,
    lang: CustomerLanguage,
    user_text: str = "",
    recent: deque[str] | list[str] | None = None,
    hangup_started: bool = False,
    agent_busy: bool = False,
) -> str | None:
    """Return a filler line or None when fillers should not run."""
    if not should_use_filler(
        intent=intent,
        phase=phase,
        user_text=user_text,
        hangup_started=hangup_started,
        agent_busy=agent_busy,
    ):
        return None

    kind = _kind_for_intent(intent)
    assert kind is not None

    pool = list(_pool_for_language(lang)[kind])
    recent_set = set(recent or [])
    candidates = [line for line in pool if line not in recent_set]
    if not candidates:
        candidates = pool
    return random.choice(candidates)


def agent_session_busy(session) -> bool:
    """Best-effort: skip filler when preemptive gen already started."""
    state = getattr(session, "agent_state", None)
    if state is None:
        return False
    label = getattr(state, "value", state)
    return str(label).lower() in ("speaking", "thinking")
