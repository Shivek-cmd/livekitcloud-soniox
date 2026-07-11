"""Web channel sync: push order.state to the browser + handle client cart RPCs.

The browser (LiveKit web SDK) renders the live order panel and supports tap-to-add. The
server-side ``OrderCart`` is the single source of truth. Every cart change publishes the full
order state as a ``order.state`` data packet; clients can also pull it via the
``get_order_state`` RPC (used on connect / reconnect).
"""

from __future__ import annotations

import json
import logging

from livekit import rtc

from restaurant import menu_provider

logger = logging.getLogger("web-sync")

ORDER_STATE_TOPIC = "order.state"


class WebSync:
    def __init__(self, room: rtc.Room, agent) -> None:
        self.room = room
        self.agent = agent

    # ── outbound ────────────────────────────────────────────────────────────
    async def publish_order_state(self) -> None:
        try:
            payload = json.dumps(
                self.agent.cart.to_state_dict(), ensure_ascii=False
            ).encode("utf-8")
            await self.room.local_participant.publish_data(
                payload, reliable=True, topic=ORDER_STATE_TOPIC
            )
        except Exception:
            logger.exception("Failed to publish order.state")

    # ── RPC registration ────────────────────────────────────────────────────
    def register(self) -> None:
        lp = self.room.local_participant
        lp.register_rpc_method("get_order_state", self._rpc_get_state)
        lp.register_rpc_method("cart_add", self._rpc_cart_add)
        lp.register_rpc_method("cart_set_qty", self._rpc_cart_set_qty)
        lp.register_rpc_method("cart_remove", self._rpc_cart_remove)
        logger.info("Web sync RPCs registered")

    def _state_json(self) -> str:
        return json.dumps(self.agent.cart.to_state_dict(), ensure_ascii=False)

    def _ok(self, **extra) -> str:
        return json.dumps(
            {"ok": True, "state": self.agent.cart.to_state_dict(), **extra},
            ensure_ascii=False,
        )

    def _err(self, error: str, **extra) -> str:
        return json.dumps({"ok": False, "error": error, **extra}, ensure_ascii=False)

    async def _rpc_get_state(self, data: rtc.RpcInvocationData) -> str:
        return self._state_json()

    async def _rpc_cart_add(self, data: rtc.RpcInvocationData) -> str:
        try:
            req = json.loads(data.payload or "{}")
        except json.JSONDecodeError:
            return self._err("bad_payload")

        item_id = req.get("item_id")
        if not item_id:
            return self._err("missing_item_id")
        try:
            qty = max(1, int(req.get("qty") or 1))
        except (TypeError, ValueError):
            qty = 1
        modifiers = [str(m) for m in (req.get("modifiers") or [])]

        item = menu_provider.find_item_by_id(item_id)
        if not item:
            return self._err("not_found")
        if item.get("unavailable"):
            return self._err("unavailable")

        note = ", ".join(modifiers)
        self.agent.cart.add_item(item, qty, note)
        await self.publish_order_state()

        needs = [] if modifiers else menu_provider.required_modifier_groups(item_id)
        return self._ok(needs=needs)

    async def _rpc_cart_set_qty(self, data: rtc.RpcInvocationData) -> str:
        try:
            req = json.loads(data.payload or "{}")
        except json.JSONDecodeError:
            return self._err("bad_payload")
        item_id = req.get("item_id")
        if not item_id:
            return self._err("missing_item_id")
        try:
            qty = int(req.get("qty"))
        except (TypeError, ValueError):
            return self._err("bad_qty")
        if not self.agent.cart.set_quantity_by_id(item_id, qty):
            return self._err("not_in_cart")
        await self.publish_order_state()
        return self._ok()

    async def _rpc_cart_remove(self, data: rtc.RpcInvocationData) -> str:
        try:
            req = json.loads(data.payload or "{}")
        except json.JSONDecodeError:
            return self._err("bad_payload")
        item_id = req.get("item_id")
        if not item_id:
            return self._err("missing_item_id")
        if not self.agent.cart.remove_by_id(item_id):
            return self._err("not_in_cart")
        await self.publish_order_state()
        return self._ok()
