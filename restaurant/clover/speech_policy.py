"""
Production speech policy — how Sierra says dish names on Canadian Punjabi restaurant calls.

Real staff code-mix: Punjabi/Hindi sentences + English menu names + English numbers/spice.
Not every dish should be spoken in full Gurmukhi (e.g. Fish Pakora, not machhi/ਮੱਛੀ).
"""

from __future__ import annotations

import re
from typing import Literal

from restaurant.clover.seed_menu import MenuItemSpec

SpeechMode = Literal["english", "mixed", "gurmukhi"]

# Items where voice_line is explicitly set (overrides category rules).
VOICE_LINE_OVERRIDES: dict[str, str] = {
    "fish_pakora": "Fish Pakora",
    "tandoori_shrimp": "Tandoori Shrimp",
    "butter_prawn_masala": "Butter Prawn Masala",
    "chole_bhature_combo": "Chole Bhature Combo",
    "chole": "Chole",
    "bhatura_single": "Bhatura",
}

# Traditional / strongly Punjabi — full Gurmukhi voice_line when speak_as is set.
GURMUKHI_ITEM_KEYS: frozenset[str] = frozenset(
    {
        "sarson_saag",
        "gajar_halwa",
        "kheer",
        "gulab_jamun",
        "rasmalai",
    }
)

# Categories that default to English menu names on calls.
ENGLISH_CATEGORY_KEYS: frozenset[str] = frozenset(
    {
        "combos",
        "tandoor",
        "nonveg_mains",
    }
)

# Starters with meat/fish — English name on calls.
_ENGLISH_STARTER_KEYS: frozenset[str] = frozenset(
    {
        "chicken_tikka",
        "fish_pakora",
        "seekh_kebab",
        "lamb_chops",
        "tandoori_shrimp",
    }
)


def _strip_parens(name: str) -> str:
    """Shorten Clover name for speech: drop (2 pcs), (serves 4), etc."""
    return re.sub(r"\s*\([^)]*\)\s*", " ", name).strip()


def resolve_item_speech(spec: MenuItemSpec) -> tuple[str, SpeechMode]:
    """
    Return (voice_line, speech_mode) for TTS output.

    voice_line — exact text Sierra should say for the dish name.
    speech_mode — hints for sentence wrapping (english | mixed | gurmukhi).
    """
    if spec.key in VOICE_LINE_OVERRIDES:
        return VOICE_LINE_OVERRIDES[spec.key], "english"

    if spec.key in GURMUKHI_ITEM_KEYS and spec.speak_as:
        return spec.speak_as, "gurmukhi"

    if spec.category_key in ENGLISH_CATEGORY_KEYS:
        return _strip_parens(spec.name), "english"

    if spec.category_key == "starters" and spec.key in _ENGLISH_STARTER_KEYS:
        return _strip_parens(spec.name), "english"

    if spec.category_key == "starters" and not spec.veg:
        return _strip_parens(spec.name), "english"

    if spec.category_key in ("breads_rice", "extras"):
        return _strip_parens(spec.name), "english"

    if spec.category_key == "drinks":
        return _strip_parens(spec.name), "mixed"

    if spec.category_key == "desserts":
        return spec.speak_as or _strip_parens(spec.name), "mixed"

    if spec.category_key == "veg_mains":
        return _strip_parens(spec.name), "mixed"

    if spec.category_key == "starters":
        return _strip_parens(spec.name), "mixed"

    return _strip_parens(spec.name), "mixed"


def resolve_modifier_speech(name: str) -> tuple[str, SpeechMode]:
    """Modifiers and spice levels — always English on Canadian calls."""
    return name, "english"


def resolve_speech_from_label(item: dict) -> tuple[str, SpeechMode]:
    """Resolve speech for a voice-label or cache dict (with optional pre-set fields)."""
    if item.get("voice_line") and item.get("speech_mode"):
        return item["voice_line"], item["speech_mode"]

    key = item.get("key", "")
    if key in VOICE_LINE_OVERRIDES:
        return VOICE_LINE_OVERRIDES[key], "english"

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
