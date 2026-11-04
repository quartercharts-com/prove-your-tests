"""A tiny shop: orders, refunds and a ledger of money movements.

Rule the tests must protect: money leaves only through refund(), and a customer
(not an admin) may refund at most MAX_SELF_REFUND per call.
"""
from __future__ import annotations

from dataclasses import dataclass, field

MAX_SELF_REFUND = 50
LEDGER: list[dict] = []


@dataclass
class User:
    name: str
    is_admin: bool = False


@dataclass
class Order:
    id: str
    paid: int
    refunded: int = 0
    notes: list[tuple[str, str]] = field(default_factory=list)


def refund(order: Order, amount: int, user: User) -> int:
    """Give money back. The only function allowed to write to LEDGER."""
    if amount <= 0:
        raise ValueError("amount must be positive")
    if amount > order.paid - order.refunded:
        raise ValueError("more than was paid")
    if not user.is_admin and amount > MAX_SELF_REFUND:
        raise PermissionError("needs an admin")
    order.refunded += amount
    LEDGER.append({"order": order.id, "amount": -amount, "by": user.name})
    return order.refunded


def add_note(order: Order, text: str, user: User) -> int:
    """Attach a note to an order. Never moves money."""
    order.notes.append((user.name, text.strip()))
    return len(order.notes)


def order_balance(order: Order) -> int:
    """What the customer has paid and kept."""
    return order.paid - order.refunded


def cancel(order: Order, user: User) -> int:
    """Cancel an order by refunding what is left; customers go through the same limit."""
    left = order_balance(order)
    if left == 0:
        return 0
    return refund(order, left, user)
