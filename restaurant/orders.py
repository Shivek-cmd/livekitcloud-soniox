from dataclasses import dataclass, field
from typing import Optional
from restaurant.menu import DELIVERY_CHARGE


@dataclass
class CartItem:
    name: str
    punjabi: str
    price: int
    quantity: int
    note: str = ""


@dataclass
class OrderCart:
    items: list = field(default_factory=list)
    order_type: Optional[str] = None       # "pickup" | "delivery"
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    delivery_address: Optional[str] = None

    @property
    def is_empty(self) -> bool:
        return len(self.items) == 0

    @property
    def subtotal(self) -> int:
        return sum(i.price * i.quantity for i in self.items)

    @property
    def total(self) -> int:
        return self.subtotal + (DELIVERY_CHARGE if self.order_type == "delivery" else 0)

    def add_item(self, item: dict, quantity: int, note: str = "") -> str:
        for existing in self.items:
            if existing.name.lower() == item["name"].lower():
                existing.quantity += quantity
                return f"Updated: {existing.quantity}x {item['name']} in cart. Total: ${self.total}"
        self.items.append(CartItem(
            name=item["name"],
            punjabi=item["punjabi"],
            price=item["price"],
            quantity=quantity,
            note=note,
        ))
        return f"Added {quantity}x {item['name']} (${item['price']} each). Total: ${self.total}"

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
            lines.append(f"  {item.quantity}x {item.punjabi} ({item.name}) — ${item.price * item.quantity}")
            if item.note:
                lines.append(f"     Note: {item.note}")
        lines.append(f"Subtotal: ${self.subtotal}")
        if self.order_type == "delivery":
            lines.append(f"Delivery charge: ${DELIVERY_CHARGE}")
        lines.append(f"Total: ${self.total}")
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
