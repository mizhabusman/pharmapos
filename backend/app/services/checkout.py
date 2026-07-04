"""
checkout.py — Build an authoritative bill from trusted, server-side data.

The client sends which item and how many packs it wants to buy, but NEVER
gets to decide prices. This module recomputes ``billed_qty`` and
``line_total`` for every line from the inventory's own ``pack_size`` and
``price_inr``, and sums the grand total server-side. Any money values the
client submitted are ignored — this closes the price-tampering hole where a
caller could post ``line_total: 0.01``.
"""

from typing import Dict, List, Tuple

from app.services.database_manager import get_medicine_by_item_code


def build_authoritative_bill(
    client_items: List[Dict],
) -> Tuple[List[Dict], float, List[Dict]]:
    """
    Recompute billing line items from authoritative inventory prices.

    Args:
        client_items: Raw items from the request. Only ``item_code`` and
                      ``packs_needed`` (the quantity intent) are trusted.

    Returns:
        (items, grand_total, errors)
        - items:       server-computed line items safe to bill and persist
        - grand_total: sum of server-computed line totals (2 dp)
        - errors:      per-item problems (unknown item / invalid quantity);
                       non-empty means the sale must be rejected.
    """
    items: List[Dict] = []
    errors: List[Dict] = []
    grand_total = 0.0

    for client_item in client_items:
        item_code = client_item.get("item_code")

        try:
            packs_needed = int(client_item.get("packs_needed", 0))
        except (TypeError, ValueError):
            packs_needed = 0

        if packs_needed <= 0:
            errors.append({"item_code": item_code, "error": "Invalid quantity"})
            continue

        medicine = get_medicine_by_item_code(item_code)
        if not medicine:
            errors.append({"item_code": item_code, "error": "Item not found in inventory"})
            continue

        pack_size = medicine["pack_size"]
        pack_price = medicine["price_inr"]

        billed_qty = packs_needed * pack_size
        line_total = round(packs_needed * pack_price, 2)
        grand_total += line_total

        items.append({
            "item_code": item_code,
            "packs_needed": packs_needed,
            "billed_qty": billed_qty,
            "line_total": line_total,
        })

    return items, round(grand_total, 2), errors
