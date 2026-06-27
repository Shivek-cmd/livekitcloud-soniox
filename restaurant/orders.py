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
    punjabi: str
    price: float
    quantity: int
    note: str = ""
    clover_item_id: str | None = None


@dataclass
class OrderCart:
    items: list = field(default_factory=list)
    order_type: Optional[str] = None       # "pickup" | "delivery"
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    delivery_address: Optional[str] = None
    delivery_charge: float = DELIVERY_CHARGE

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

        for existing in self.items:
            if existing.name.lower() == item["name"].lower():
                existing.quantity += quantity
                if note:
                    existing.note = note
                return f"Updated: {existing.quantity}x {item['name']} in cart. Total: {_money(self.total)}"

        self.items.append(CartItem(
            name=item["name"],
            punjabi=item.get("punjabi") or item.get("speak_as") or item["name"],
            price=float(item.get("price") or (item.get("price_cents", 0) / 100)),
            quantity=quantity,
            note=note,
            clover_item_id=item.get("clover_item_id"),
        ))
        return f"Added {quantity}x {item['name']} ({_money(float(item.get('price') or item.get('price_cents', 0) / 100))} each). Total: {_money(self.total)}"

    def remove_item(self, name: str) -> str:
        for i, item in enumerate(self.items):
            if name.lower() in item.name.lower():
                removed = self.items.pop(i)
                return f"Removed {removed.name} from order."
        return f"'{name}' not found in your order."

    def summary(self) -> str:
        if self.is_empty:
            return "Your order is empty."
        lines = ["Current order:"]
        for item in self.items:
            line_total = item.price * item.quantity
            lines.append(f"  {item.quantity}x {item.punjabi} ({item.name}) — {_money(line_total)}")
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
        if not self.customer_phone:
            return False, "Customer phone not provided."
        if self.order_type == "delivery" and not self.delivery_address:
            return False, "Delivery address not provided."
        return True, "OK"
