"""Stage 4 — LiveKit adapter: wires extractor -> engine -> renderer into a call.

This REPLACES the old free-form agent turn handler. Per turn:

    transcript ─▶ extractor(LLM) ─▶ Proposal ─▶ engine.handle ─▶ Actions ─▶ renderer ─▶ session.say

The base session LLM never generates replies — we own every spoken line, so the
money path is fully deterministic. The LLM is used ONLY inside the extractor.

Every turn is logged (transcript, proposal, actions, cart) so accuracy can be
measured in shadow mode before any restaurant goes live (stage 5).

NOTE: This module imports LiveKit and OpenAI and therefore is not exercised by
the unit tests (which cover engine/resolver/extractor/renderer). It needs a
real call to validate — that is the point of the shadow-mode ramp.
"""

from __future__ import annotations

import json
import logging
import os

from livekit.agents import Agent, JobContext, WorkerOptions, cli
from livekit.agents.llm import StopResponse

from restaurant.conversation import OPENING_GREETING, detect_customer_language
from restaurant.engine.core import OrderEngine, Phase
from restaurant.engine.extractor import extract
from restaurant.engine.renderer import render_all
from restaurant.engine.resolver import CloverResolver
from restaurant.session_config import build_agent_session, build_room_options

logger = logging.getLogger("engine-live")

# What the engine is currently waiting for — handed to the extractor so a bare
# "yes" / "one" / "Sandeep" maps to the right field.
_ASKING = {
    Phase.CLARIFY_ITEM: "which dish did they pick?",
    Phase.ASK_QUANTITY: "how many? (a number)",
    Phase.CONFIRM_ITEM: "yes or no to confirm the item",
    Phase.ASK_SPICE: "a spice level (mild/medium/spicy) or special note",
    Phase.ASK_ALLERGIES: "any allergies or special instructions? (yes/no or a note)",
    Phase.ASK_ORDER_TYPE: "pickup or delivery?",
    Phase.READBACK: "yes or no — is the whole order correct?",
    Phase.ASK_NAME: "the customer's name",
    Phase.ASK_PHONE: "a 10-digit phone number",
}


def _make_completion(model: str):
    """An async fn: chat messages -> model text. Uses OpenAI JSON mode so the
    extractor gets clean JSON. Isolated here so the engine package stays pure."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI()

    async def complete(messages: list[dict]) -> str:
        resp = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0,
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content or "{}"

    return complete


class EngineAgent(Agent):
    """Deterministic order agent. Owns every spoken line; the base LLM is mute."""

    def __init__(self, *, resolver: CloverResolver, is_phone: bool, delivery_charge: float):
        # Minimal instructions — we never let the base LLM speak, but the session
        # pipeline wants an agent. All logic is in on_user_turn_completed.
        super().__init__(instructions="Silent. All replies are produced by code.")
        self.engine = OrderEngine(resolver, delivery_charge=delivery_charge)
        self.is_phone = is_phone
        self.lang = "pa"  # sticky; updated from caller speech
        self._session = None
        self._complete = _make_completion(os.getenv("EXTRACTOR_MODEL", "gpt-4o-mini"))
        self._turns: list[dict] = []

    def bind_session(self, session) -> None:
        self._session = session

    def _update_language(self, text: str) -> None:
        det = detect_customer_language(text)
        if det is not None:
            code = {"en": "en", "pa": "pa", "hi": "hi"}.get(det.value)
            if code in ("en", "pa"):
                self.lang = code

    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        transcript = (new_message.text_content or "").strip()
        if not transcript:
            raise StopResponse()

        self._update_language(transcript)
        asking = _ASKING.get(self.engine.phase)
        proposal = await extract(self._complete, transcript, asking=asking)
        actions = self.engine.handle(proposal)

        # Structured per-turn log for shadow-mode accuracy measurement (stage 5).
        record = {
            "transcript": transcript,
            "phase_in": asking or self.engine.phase.value,
            "proposal": proposal.__dict__,
            "actions": [{"kind": a.kind, "data": a.data} for a in actions],
            "cart": self.engine.order_summary(),
        }
        self._turns.append(record)
        logger.info("ENGINE_TURN %s", json.dumps(record, ensure_ascii=False, default=str))

        # Place the order in Clover the moment the engine reaches PLACED.
        if self.engine.phase == Phase.PLACED:
            await self._submit_order()

        speech = render_all(actions, self.lang)
        if speech and self._session:
            await self._session.say(speech, allow_interruptions=True)
        raise StopResponse()  # we fully own the turn; base LLM stays silent

    async def _submit_order(self) -> None:
        """Hook for Clover submission — reuse restaurant.clover.order_submit.
        Kept thin; the engine already validated the order is complete."""
        try:
            # Build the same cart shape order_submit expects, or call a small
            # adapter. Left as an explicit integration point for the pilot.
            logger.info("ORDER_READY_FOR_CLOVER %s",
                        json.dumps(self.engine.order_summary(), ensure_ascii=False, default=str))
        except Exception:
            logger.exception("Clover submit failed")


async def entrypoint(ctx: JobContext):
    from pathlib import Path

    from restaurant.clover.menu import MenuCache
    from restaurant.menu import DELIVERY_CHARGE
    from restaurant.tenants.config import get_default_tenant

    await ctx.connect()
    participant = await ctx.wait_for_participant()
    is_phone = participant.identity.startswith("sip_") or \
        (participant.attributes or {}).get("sip.callStatus") is not None

    tenant = get_default_tenant()
    cache = MenuCache.load(Path(tenant.cache_path()))
    resolver = CloverResolver(cache)

    session = build_agent_session(is_phone=is_phone)
    agent = EngineAgent(resolver=resolver, is_phone=is_phone, delivery_charge=DELIVERY_CHARGE)
    agent.bind_session(session)

    await session.start(room=ctx.room, agent=agent,
                        room_options=build_room_options(is_phone=is_phone))
    await session.say(OPENING_GREETING, allow_interruptions=False)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, agent_name="engine-restaurant-agent",
                              port=int(os.getenv("AGENT_HTTP_PORT", "8082"))))
