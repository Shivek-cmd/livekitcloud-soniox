from dataclasses import dataclass, field
from typing import Optional

from restaurant.menu import DELIVERY_CHARGE


def _money(amount: float) -> str:
    if abs(amount - round(amount)) < 0.001:
        return f"${int(round(amount))}"
    return f"${amount:.2f}"


@dataclass
class CartItem:
    name: str
    voice_line: str
    price: float
    quantity: int
    note: str = ""
    clover_item_id: str | None = None
    speech_mode: str = "mixed"


@dataclass
class OrderCart:
    items: list = field(default_factory=list)
    order_type: Optional[str] = None       # "pickup" | "delivery"
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    delivery_address: Optional[str] = None
    delivery_charge: float = DELIVERY_CHARGE
    placed: bool = False
    order_id: Optional[str] = None
    eta: Optional[str] = None

    @property
    def is_empty(self) -> bool:
        return len(self.items) == 0

    @property
    def subtotal(self) -> float:
        return sum(i.price * i.quantity for i in self.items)

    @property
    def total(self) -> float:
        return self.subtotal + (self.delivery_charge if self.order_type == "delivery" else 0)

    def add_item(self, item: dict, quantity: int, note: str = "") -> str:
        if item.get("unavailable"):
            return f"Sorry, {item['name']} is not available right now. Ask the customer to pick something else."

        from restaurant.conversation import format_add_tool_reply

        voice = item.get("voice_line") or item.get("speak_as") or item["name"]

        for existing in self.items:
            if existing.name.lower() == item["name"].lower():
                existing.quantity += quantity
                if note:
                    existing.note = note
                return format_add_tool_reply(
                    [(existing.quantity, existing.voice_line or voice)],
                    updated=True,
                )

        self.items.append(CartItem(
            name=item["name"],
            voice_line=voice,
            price=float(item.get("price") or (item.get("price_cents", 0) / 100)),
            quantity=quantity,
            note=note,
            clover_item_id=item.get("clover_item_id"),
            speech_mode=item.get("speech_mode") or "mixed",
        ))
        return format_add_tool_reply([(quantity, voice)])

    def remove_item(self, name: str) -> str:
        from restaurant.conversation import format_remove_tool_reply

        for i, item in enumerate(self.items):
            if name.lower() in item.name.lower():
                removed = self.items.pop(i)
                voice = removed.voice_line or removed.name
                return format_remove_tool_reply(voice)
        return f"INTERNAL: not found. Ask customer to clarify the item name."

    def update_item_quantity(self, name: str, quantity: int) -> str:
        """Set a cart line to an exact quantity (correction — not additive).

        Use this when the customer corrects a quantity already in the cart
        (e.g. "I said one, not two"). add_item() is additive and would
        compound the error instead of fixing it.
        """
        from restaurant.conversation import (
            format_remove_tool_reply,
            format_update_tool_reply,
        )

        for i, item in enumerate(self.items):
            if name.lower() in item.name.lower():
                if quantity <= 0:
                    removed = self.items.pop(i)
                    voice = removed.voice_line or removed.name
                    return format_remove_tool_reply(voice)
                item.quantity = quantity
                voice = item.voice_line or item.name
                return format_update_tool_reply(quantity, voice)
        return "INTERNAL: not found. Ask customer to clarify the item name."

    def set_quantity_by_id(self, clover_item_id: str, quantity: int) -> bool:
        """Set quantity for a cart line identified by Clover id. qty<=0 removes it."""
        for i, item in enumerate(self.items):
            if item.clover_item_id == clover_item_id:
                if quantity <= 0:
                    self.items.pop(i)
                else:
                    item.quantity = quantity
                return True
        return False

    def remove_by_id(self, clover_item_id: str) -> bool:
        for i, item in enumerate(self.items):
            if item.clover_item_id == clover_item_id:
                self.items.pop(i)
                return True
        return False

    def mark_placed(self, order_id: str | None = None, eta: str | None = None) -> None:
        self.placed = True
        self.order_id = order_id
        self.eta = eta

    def status(self) -> str:
        if self.placed:
            return "placed"
        if self.is_empty:
            return "empty"
        if not self.order_type:
            return "building"
        if self.order_type == "delivery" and not self.delivery_address:
            return "awaiting_contact"
        if not (self.customer_name and self.customer_phone):
            return "awaiting_contact"
        return "confirming"

    def to_state_dict(self) -> dict:
        """JSON-serializable order state pushed to the web UI (see plan §4)."""
        return {
            "v": 1,
            "status": self.status(),
            "items": [
                {
                    "id": i.clover_item_id,
                    "name": i.name,
                    "voice_line": i.voice_line,
                    "qty": i.quantity,
                    "unit_price": round(i.price, 2),
                    "line_total": round(i.price * i.quantity, 2),
                    "note": i.note,
                    "modifiers": [i.note] if i.note else [],
                }
                for i in self.items
            ],
            "order_type": self.order_type,
            "delivery_address": self.delivery_address,
            "customer": {"name": self.customer_name, "phone": self.customer_phone},
            "subtotal": round(self.subtotal, 2),
            "delivery_charge": round(self.delivery_charge, 2) if self.order_type == "delivery" else 0,
            "total": round(self.total, 2),
            "eta": self.eta,
            "order_id": self.order_id,
        }

    def summary(self) -> str:
        if self.is_empty:
            return "Your order is empty."
        lines = ["Current order (say quantities in words, never 2x/3x; use voice_line for dish names):"]
        for item in self.items:
            line_total = item.price * item.quantity
            qty_note = f"qty {item.quantity}, say: {item.voice_line}"
            lines.append(f"  {qty_note} ({item.name}) — {_money(line_total)}")
            if item.note:
                lines.append(f"     Note: {item.note}")
        lines.append(f"Subtotal: {_money(self.subtotal)}")
        if self.order_type == "delivery":
            lines.append(f"Delivery charge: {_money(self.delivery_charge)}")
        lines.append(f"Total: {_money(self.total)}")
        if self.order_type:
            lines.append(f"Type: {self.order_type}")
        if self.delivery_address:
            lines.append(f"Address: {self.delivery_address}")
        if self.customer_name:
            lines.append(f"Name: {self.customer_name}")
        if self.customer_phone:
            lines.append(f"Phone: {self.customer_phone}")
        return "\n".join(lines)

    def ready_to_place(self) -> tuple[bool, str]:
        if self.is_empty:
            return False, "Order is empty."
        if not self.order_type:
            return False, "Order type (pickup/delivery) not set."
        if not self.customer_name:
            return False, "Customer name not provided."
        from restaurant.customer_info import is_valid_customer_name

        if not is_valid_customer_name(self.customer_name):
            return False, "Customer name not provided."
        if not self.customer_phone:
            return False, "Customer phone not provided."
        if self.order_type == "delivery" and not self.delivery_address:
            return False, "Delivery address not provided."
        return True, "OK"
