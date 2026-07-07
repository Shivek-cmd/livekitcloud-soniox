"""Stage 4 — renderer: engine Action -> spoken line, in the caller's language.

Deterministic templates, NOT an LLM. The engine already decided *what* to say
and supplied the exact grounded data (dish voice_lines, options, quantities, the
read-back list). The renderer only phrases it. This is why the money path can't
drift: there is no generative step between "code decided" and "TTS speaks".

Supported languages: "en" (English), "pa" (Gurmukhi Punjabi). "hi"/"mixed" fall
back to English for the fixed lines (dish names are always spoken via voice_line
regardless). One Action -> one line ("" means say nothing).
"""

from __future__ import annotations

_QTY = {
    "en": {1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
           6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"},
    "pa": {1: "ਇੱਕ", 2: "ਦੋ", 3: "ਤਿੰਨ", 4: "ਚਾਰ", 5: "ਪੰਜ",
           6: "ਛੇ", 7: "ਸੱਤ", 8: "ਅੱਠ", 9: "ਨੌਂ", 10: "ਦਸ"},
}


def _lang(lang: str) -> str:
    return lang if lang in ("en", "pa") else "en"


def _qty_word(n, lang: str) -> str:
    if not isinstance(n, int):
        return ""
    return _QTY[_lang(lang)].get(n, str(n))


def _join(parts: list[str], lang: str) -> str:
    parts = [p for p in parts if p]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    joiner = " ਤੇ " if _lang(lang) == "pa" else " and "
    if len(parts) == 2:
        return f"{parts[0]}{joiner}{parts[1]}"
    return ", ".join(parts[:-1]) + joiner + parts[-1]


def _item_phrase(item: dict, lang: str) -> str:
    q = _qty_word(item.get("quantity", 1), lang)
    name = item.get("dish", "")
    note = item.get("note")
    base = f"{q} {name}".strip()
    return f"{base} ({note})" if note else base


def render(action, lang: str = "en") -> str:
    """Return the spoken line for one engine Action. Never raises."""
    lang = _lang(lang)
    k = action.kind
    d = action.data
    pa = lang == "pa"

    if k == "clarify":
        opts = _join(d.get("options", []), lang)
        return f"ਸਾਡੇ ਕੋਲ {opts} ਹੈ ਜੀ — ਕਿਹੜਾ?" if pa else f"We have {opts} — which one?"

    if k == "ask_quantity":
        dish = d.get("dish", "")
        return f"ਕਿੰਨੇ {dish} ਜੀ?" if pa else f"How many {dish}?"

    if k == "confirm_item":
        q = _qty_word(d.get("quantity", 1), lang)
        dish = d.get("dish", "")
        return f"{q} {dish} — ਠੀਕ ਹੈ ਜੀ?" if pa else f"{q} {dish} — is that right?"

    if k == "ask_spice":
        dish = d.get("dish", "")
        return (f"{dish} ਕਿੰਨਾ ਤਿੱਖਾ — mild, medium ਜਾਂ spicy?" if pa
                else f"How spicy for the {dish} — mild, medium, or spicy?")

    if k == "item_added":
        return f"ਠੀਕ ਹੈ ਜੀ — {_item_phrase({**d, 'quantity': d.get('quantity', 1)}, lang)}." if pa \
            else f"Got it — {_item_phrase({**d, 'quantity': d.get('quantity', 1)}, lang)}."

    if k == "anything_else":
        return "ਹੋਰ ਕੁਝ ਜੀ?" if pa else "Anything else?"

    if k == "cancelled_item":
        return "ਕੋਈ ਗੱਲ ਨਹੀਂ ਜੀ।" if pa else "No problem."

    if k == "not_on_menu":
        return ("ਮਾਫ ਕਰਨਾ ਜੀ — ਉਹ ਸਾਡੇ ਮੇਨੂ 'ਤੇ ਨਹੀਂ। ਦੁਬਾਰਾ ਦੱਸੋਗੇ?" if pa
                else "Sorry, we don't have that — could you say the dish again?")

    if k == "ask_allergies":
        return "ਕੋਈ allergy ਜਾਂ special instruction ਜੀ?" if pa else "Any allergies or special instructions?"

    if k == "noted_allergies":
        return "ਠੀਕ ਹੈ ਜੀ।" if (pa and d.get("note")) else ("Noted." if d.get("note") else "")

    if k == "ask_order_type":
        return "Pickup ਜਾਂ delivery ਜੀ?" if pa else "Pickup or delivery?"

    if k == "readback":
        items = _join([_item_phrase(i, lang) for i in d.get("items", [])], lang)
        ot = d.get("order_type") or "pickup"
        name = d.get("name")
        who = f"{name} ਜੀ — " if (pa and name) else (f"Okay {name} — " if name else ("ਠੀਕ ਹੈ ਜੀ — " if pa else "Okay — "))
        tail = "ਸਭ ਠੀਕ ਹੈ ਜੀ?" if pa else "All good?"
        return f"{who}{items}, {ot}. {tail}"

    if k == "readback_rejected":
        return "ਕੋਈ ਗੱਲ ਨਹੀਂ ਜੀ — ਕੀ ਬਦਲਣਾ ਹੈ?" if pa else "No problem — what would you like to change?"

    if k == "ask_name":
        return "ਆਰਡਰ ਲਈ ਨਾਮ ਦੱਸੋ ਜੀ?" if pa else "Can I get a name for the order?"

    if k == "ask_phone":
        name = d.get("name") or ""
        return f"{name} ਜੀ — ਫੋਨ ਨੰਬਰ ਦੱਸੋ?" if pa else f"Thanks {name} — what's the phone number?"

    if k == "order_placed":
        ot = d.get("order_type")
        wait = "30-40 ਮਿੰਟ" if ot == "delivery" else "20-25 ਮਿੰਟ"
        wait_en = "30 to 40 minutes" if ot == "delivery" else "20 to 25 minutes"
        return (f"ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! {wait} ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਧੰਨਵਾਦ ਜੀ!" if pa
                else f"Your order's in! It'll be ready in about {wait_en}. Thank you!")

    if k == "quantity_corrected":
        q = _qty_word(d.get("quantity", 1), lang)
        dish = d.get("dish", "")
        return f"ਠੀਕ ਹੈ ਜੀ — ਹੁਣ {q} {dish}." if pa else f"Got it — {q} {dish} now."

    if k == "item_removed":
        return f"{d.get('dish','')} ਹਟਾ ਦਿੱਤਾ ਜੀ." if pa else f"Removed {d.get('dish','')}."

    if k == "correction_no_such_item":
        return ("ਉਹ item ਤੁਹਾਡੇ ਆਰਡਰ ਵਿੱਚ ਹਾਲੇ ਨਹੀਂ ਜੀ।" if pa
                else f"You don't have {d.get('query','that')} in the order yet.")

    if k == "transfer":
        return "ਇੱਕ ਮਿੰਟ ਜੀ — staff ਨਾਲ connect ਕਰਦੀ ਹਾਂ।" if pa else "One moment — connecting you to a staff member."

    if k == "repeat":
        return "ਮਾਫ ਕਰਨਾ ਜੀ — ਦੁਬਾਰਾ ਦੱਸੋਗੇ?" if pa else "Sorry, could you say that again?"

    if k == "cart_empty_cannot_finish":
        return "ਤੁਹਾਡਾ ਆਰਡਰ ਹਾਲੇ ਖਾਲੀ ਹੈ ਜੀ — ਕੀ ਲੈਣਾ ਹੈ?" if pa else "Your order's empty so far — what would you like?"

    if k in ("already_placed",):
        return ""

    return ""


def render_all(actions, lang: str = "en") -> str:
    """Join the lines for a turn's actions into one spoken utterance."""
    lines = [render(a, lang) for a in actions]
    return " ".join(l for l in lines if l).strip()
