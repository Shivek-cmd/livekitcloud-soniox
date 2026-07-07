"""Stage 3 — the extractor: one utterance -> a structured `Proposal`.

This is the LLM's ENTIRE job in the new design: language understanding, emitted
as strict JSON. It never decides flow and never touches the cart. The parser
below is defensive (LLMs emit imperfect JSON), and is fully unit-testable with
no LLM. The async `extract()` wires it to any completion function so the engine
package stays I/O-free.
"""

from __future__ import annotations

import json
import re
from typing import Awaitable, Callable

from restaurant.engine.core import AddRequest, Proposal

# What the current engine phase is asking for — given to the LLM so it maps a
# bare "yes" / "one" / "Sandeep" to the right field instead of guessing.
EXTRACTION_SYSTEM = """You convert ONE thing the caller just said into strict JSON. \
You do NOT decide anything, add anything, or reply — you only extract meaning. \
The caller speaks Punjabi/Hindi/English, code-mixed.

Return ONLY a JSON object with these optional keys (omit what doesn't apply):
  "adds":        [{"query": "<dish exactly as said>", "quantity": <int or null>}]
  "corrections": [{"query": "<dish>", "quantity": <the corrected TOTAL int>}]
  "removals":    ["<dish>"]
  "choice":      "<which option they picked, or a free note e.g. a spice level>"
  "quantity_answer": <int>        // when they answered "how many?"
  "yes": true|false               // affirmative to the current question
  "no":  true|false               // negative to the current question
  "order_type": "pickup"|"delivery"
  "name": "<name>"
  "phone": "<digits>"
  "address": "<full delivery address>"
  "done_adding": true             // "that's all / bas / nothing else"
  "wants_human": true
  "understood": true|false        // false ONLY if you truly caught nothing

Rules:
- NEVER invent a dish or a quantity. If no number was said, quantity is null.
- One dish said = one entry in "adds". Do not split or multiply a single dish.
- Put the dish text as the caller said it; the system resolves it to the menu.
- A quantity fix ("I said one, not two", "make it three") goes in "corrections",
  never in "adds".
"""


def build_messages(transcript: str, asking: str | None = None) -> list[dict]:
    """Messages for the extraction call. `asking` = what the engine is currently
    waiting for (e.g. 'how many?', 'pickup or delivery?', 'which dish?')."""
    ctx = f"The system is currently asking the caller: {asking}\n" if asking else ""
    return [
        {"role": "system", "content": EXTRACTION_SYSTEM},
        {"role": "user", "content": f'{ctx}Caller said: "{transcript}"\nJSON:'},
    ]


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _coerce_int(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, str) and v.strip().lstrip("-").isdigit():
        return int(v.strip())
    return None


def parse_proposal(raw: str | dict) -> Proposal:
    """Turn (possibly messy) LLM output into a Proposal. Never raises."""
    data: dict = {}
    if isinstance(raw, dict):
        data = raw
    elif isinstance(raw, str):
        text = raw.strip()
        m = _JSON_RE.search(text)
        if m:
            try:
                parsed = json.loads(m.group(0))
                if isinstance(parsed, dict):
                    data = parsed
            except (ValueError, TypeError):
                data = {}

    p = Proposal()

    for a in data.get("adds") or []:
        if isinstance(a, dict) and (a.get("query") or "").strip():
            p.adds.append(AddRequest(str(a["query"]).strip(), _coerce_int(a.get("quantity"))))

    for c in data.get("corrections") or []:
        if isinstance(c, dict) and (c.get("query") or "").strip():
            qty = _coerce_int(c.get("quantity"))
            if qty is not None:
                p.corrections.append((str(c["query"]).strip(), qty))

    for r in data.get("removals") or []:
        if isinstance(r, str) and r.strip():
            p.removals.append(r.strip())

    if isinstance(data.get("choice"), str) and data["choice"].strip():
        p.choice = data["choice"].strip()

    p.quantity_answer = _coerce_int(data.get("quantity_answer"))
    p.yes = bool(data.get("yes"))
    p.no = bool(data.get("no"))

    ot = data.get("order_type")
    if ot in ("pickup", "delivery"):
        p.order_type = ot

    if isinstance(data.get("name"), str) and data["name"].strip():
        p.name = data["name"].strip()
    if isinstance(data.get("address"), str) and data["address"].strip():
        p.address = data["address"].strip()
    if data.get("phone") is not None:
        digits = "".join(ch for ch in str(data["phone"]) if ch.isdigit())
        if digits:
            p.phone = digits

    p.done_adding = bool(data.get("done_adding"))
    p.wants_human = bool(data.get("wants_human"))
    # understood defaults True; only an explicit false (or empty extraction) flips it
    p.understood = bool(data.get("understood", True)) and (data != {})
    return p


async def extract(
    complete: Callable[[list[dict]], Awaitable[str]],
    transcript: str,
    *,
    asking: str | None = None,
) -> Proposal:
    """Run the extraction LLM call and parse it. `complete` is any async fn that
    takes chat messages and returns the model's text — injected by the LiveKit
    adapter so this module never imports a provider."""
    if not (transcript or "").strip():
        return Proposal(understood=False)
    try:
        raw = await complete(build_messages(transcript, asking))
    except Exception:
        return Proposal(understood=False)
    return parse_proposal(raw)
