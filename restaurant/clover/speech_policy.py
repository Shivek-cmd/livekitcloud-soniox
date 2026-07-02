"""
Production speech policy — what Sierra says aloud (Soniox TTS input).

Soniox TTS with language=pa pronounces Gurmukhi well but misreads Roman menu text
("Aloo Paratha", "2x") — playground tests confirm script matters, not the model.

Default: voice_line = speak_as (Gurmukhi) when available.
English voice_line ONLY for explicit overrides (Fish Pakora, Mango Shake, etc.).
"""

from __future__ import annotations

import re
from typing import Literal

from restaurant.clover.seed_menu import MenuItemSpec

SpeechMode = Literal["english", "mixed", "gurmukhi"]

# English TTS — staff/customers say these in English; Gurmukhi sounds wrong or awkward.
ENGLISH_VOICE_KEYS: frozenset[str] = frozenset(
    {
        "fish_pakora",
        "tandoori_shrimp",
        "butter_prawn_masala",
        "mango_lassi",
        "mango_shake",
        "butter_chicken",
        "chicken_tikka",
        "seekh_kebab",
        "lamb_chops",
        "tandoori_chicken_half",
        "tandoori_chicken_full",
        "paneer_tikka",
        "kulfi",
        # PR 033 — voice_line was a translation (Kesar/Sada/Bakre) that customers
        # never say; speak the menu-card name. Gurmukhi speak_as stays matchable.
        "saffron_rice",
        "plain_rice",
        "jeera_rice",
        "goat_curry",
        "fish_curry",
    }
)

VOICE_LINE_OVERRIDES: dict[str, str] = {
    "fish_pakora": "Fish Pakora",
    "tandoori_shrimp": "Tandoori Shrimp",
    "butter_prawn_masala": "Butter Prawn Masala",
    "mango_lassi": "Mango Lassi",
    "mango_shake": "Mango Shake",
    "kulfi": "Mango Kulfi",
    # PR 033 — Half and Full spoke the identical line "Tandoori Chicken";
    # read-backs could not tell the caller which one was on the order.
    "tandoori_chicken_half": "Half Tandoori Chicken",
    "tandoori_chicken_full": "Full Tandoori Chicken",
}


def _strip_parens(name: str) -> str:
    return re.sub(r"\s*\([^)]*\)\s*", " ", name).strip()


def resolve_item_speech(spec: MenuItemSpec) -> tuple[str, SpeechMode]:
    """
    Return (voice_line, speech_mode) — exact text Soniox TTS should speak for the dish name.
    """
    if spec.key in ENGLISH_VOICE_KEYS:
        line = VOICE_LINE_OVERRIDES.get(spec.key) or _strip_parens(spec.name)
        return line, "english"

    if spec.speak_as:
        return spec.speak_as, "gurmukhi"

    return _strip_parens(spec.name), "english"


def resolve_modifier_speech(name: str) -> tuple[str, SpeechMode]:
    """Spice/modifiers — English words Soniox handles fine."""
    return name, "english"


def resolve_speech_from_label(item: dict) -> tuple[str, SpeechMode]:
    if item.get("voice_line") and item.get("speech_mode"):
        return item["voice_line"], item["speech_mode"]

    key = item.get("key", "")
    name = item.get("clover_name") or item.get("name") or ""
    speak_as = item.get("speak_as") or name
    category_key = item.get("category_key", "")
    veg = bool(item.get("veg", True))

    spec = MenuItemSpec(
        key=key or "unknown",
        name=name,
        price=0,
        category_key=category_key,
        speak_as=speak_as,
        aliases=tuple(item.get("aliases") or ()),
        veg=veg,
    )
    return resolve_item_speech(spec)
