"""Internal menu cache types (Clover + voice labels)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CachedModifier:
    clover_modifier_id: str
    name: str
    price_cents: int
    speak_as: str | None = None
    voice_line: str | None = None
    speech_mode: str = "english"
    aliases: list[str] = field(default_factory=list)


@dataclass
class CachedModifierGroup:
    clover_modifier_group_id: str
    name: str
    min_required: int
    max_allowed: int
    modifiers: list[CachedModifier] = field(default_factory=list)


@dataclass
class CachedMenuItem:
    clover_item_id: str
    name: str
    speak_as: str
    voice_line: str
    speech_mode: str
    price_cents: int
    veg: bool
    available: bool
    category_id: str
    category_name: str
    aliases: list[str] = field(default_factory=list)
    modifier_groups: list[CachedModifierGroup] = field(default_factory=list)

    @property
    def price_dollars(self) -> float:
        return self.price_cents / 100.0

    def to_cart_dict(self) -> dict:
        """Shape compatible with OrderCart."""
        return {
            "name": self.name,
            "voice_line": self.voice_line,
            "speech_mode": self.speech_mode,
            "speak_as": self.speak_as,
            "punjabi": self.voice_line,
            "price": self.price_dollars,
            "price_cents": self.price_cents,
            "veg": self.veg,
            "clover_item_id": self.clover_item_id,
            "category": self.category_name,
        }

    def describe(self) -> str:
        veg = "Vegetarian" if self.veg else "Non-vegetarian"
        avail = "" if self.available else " — currently unavailable"
        mods = ""
        if self.modifier_groups:
            group_names = ", ".join(g.name for g in self.modifier_groups)
            mods = f" Options: {group_names}."
        return (
            f'{self.name} — say aloud: "{self.voice_line}" (speech_mode: {self.speech_mode})'
            f" — ${self.price_dollars:.2f} — {veg}{avail}.{mods}"
        )
