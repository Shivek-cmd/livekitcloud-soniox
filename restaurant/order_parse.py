"""Extract multiple menu line items from one caller utterance."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from restaurant import menu_provider
from restaurant.text_match import word_bounded

_DEFAULT_AUTO_ADD_MIN_CONF = 0.8


def _auto_add_min_confidence() -> float:
    try:
        return float(os.getenv("AUTO_ADD_MIN_CONFIDENCE", str(_DEFAULT_AUTO_ADD_MIN_CONF)))
    except ValueError:
        return _DEFAULT_AUTO_ADD_MIN_CONF

_SPLIT_RE = re.compile(
    r"\s+(?:"
    r"and|&|,|"
    r"aur|te|plus|"
    r"ਅਤੇ|ਤੇ"
    r")\s+",
    re.I,
)

_STRIP_LEADING = re.compile(
    r"^(?:"
    r"please\s+|"
    r"can you\s+|could you\s+|would you\s+|"
    r")?"
    r"(?:"
    r"add|order|get me|give me|i want|i'd like|i'll take|"
    r"add karo|order karo|order kar|dedo|de do|"
    r"ਚਾਹੀ(?:ਦਾ|ਦੀ|ਦੇ)|ਜੋੜ|ਆਰਡਰ"
    r")\s+",
    re.I,
)

_QTY_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "a": 1,
    "an": 1,
    "ਇੱਕ": 1,
    "ਐਕ": 1,
    "ਦੋ": 2,
    "ਤਿੰਨ": 3,
}

_QTY_RE = re.compile(
    word_bounded(
        r"one|two|three|four|five|six|seven|eight|nine|ten|"
        r"a|an|"
        r"ਇੱਕ|ਐਕ|ਦੋ|ਤਿੰਨ|"
        r"(\d+)"
    ),
    re.I,
)

_QTY_ITEM_CHUNKS = re.compile(
    r"(?:"
    r"one|two|three|four|five|six|seven|eight|nine|ten|"
    r"ਇੱਕ|ਐਕ|ਦੋ|ਤਿੰਨ|"
    r"\d+"
    r")\s+[\w\u0900-\u097F\u0A00-\u0A7F]+(?:\s+[\w\u0900-\u097F\u0A00-\u0A7F]+)*",
    re.I,
)


@dataclass(frozen=True)
class ParsedOrderLine:
    quantity: int
    item: dict
    # 1.0 = exact/static match; Clover fuzzy matches carry their real score
    confidence: float = 1.0


def _extract_qty(segment: str) -> tuple[int, str]:
    segment = segment.strip()
    match = _QTY_RE.search(segment)
    if not match:
        return 1, segment
    token = match.group(0)
    if token.isdigit():
        qty = int(token)
    else:
        qty = _QTY_WORDS.get(token.lower(), 1)
    rest = (segment[: match.start()] + segment[match.end() :]).strip()
    rest = re.sub(r"^(?:of|x)\s+", "", rest, flags=re.I)
    return max(1, qty), rest


def _resolve_item(text: str) -> dict | None:
    cleaned = _STRIP_LEADING.sub("", (text or "").strip()).strip()
    if not cleaned:
        return None

    hit = menu_provider.find_item(cleaned)
    if hit and not hit.get("unavailable"):
        return hit

    hit = menu_provider.resolve_item_in_text(cleaned)
    if hit and not hit.get("unavailable"):
        return hit

    for chunk in re.findall(r"[A-Za-z\u0900-\u097F\u0A00-\u0A7F]{3,}", cleaned):
        hit = menu_provider.find_item(chunk)
        if hit and not hit.get("unavailable"):
            return hit
    return None


def parse_order_lines(text: str) -> list[ParsedOrderLine]:
    """Best-effort: extract (qty, menu item) pairs from one utterance."""
    raw = (text or "").strip()
    if not raw:
        return []

    parts = [p.strip() for p in _SPLIT_RE.split(raw) if p.strip()]
    if len(parts) <= 1:
        chunks = _QTY_ITEM_CHUNKS.findall(raw)
        parts = chunks if len(chunks) >= 2 else [raw]

    out: list[ParsedOrderLine] = []
    seen: set[str] = set()
    for part in parts:
        qty, rest = _extract_qty(part)
        item = _resolve_item(rest if rest else part)
        if not item:
            continue
        key = item["name"].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(
            ParsedOrderLine(
                quantity=qty,
                item=item,
                confidence=float(item.get("match_confidence", 1.0)),
            )
        )
    return out


def item_needs_modifiers(item: dict) -> bool:
    clover_id = item.get("clover_item_id")
    if clover_id:
        return bool(menu_provider.required_modifier_groups(clover_id))
    return menu_provider.item_has_spice_level(item.get("name", ""))


def can_auto_add_lines(lines: list[ParsedOrderLine]) -> bool:
    """True when we can add every line in code without modifier prompts.

    Auto-add speaks a code-owned confirm with no LLM review, so every line
    must be a high-confidence match — weaker resolutions go through the
    normal LLM tool path where the model confirms with the caller.
    """
    if len(lines) < 2:
        return False
    min_conf = _auto_add_min_confidence()
    if any(line.confidence < min_conf for line in lines):
        return False
    return all(not item_needs_modifiers(line.item) for line in lines)
