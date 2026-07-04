"""
billing.py — Convert a prescribed quantity into pack-based billing figures.
"""

from fastapi import APIRouter

from app.services.billing_engine import calculate_pack_billing
from app.services.database_manager import get_medicine_by_item_code

router = APIRouter(tags=["billing"])


@router.get("/billing")
def get_billing(item_code: int, rx_qty: int):
    medicine = get_medicine_by_item_code(item_code)
    if not medicine:
        return {"error": "Medicine not found"}

    result = calculate_pack_billing(
        rx_qty=rx_qty,
        pack_size=medicine["pack_size"],
        pack_price=medicine["price_inr"],
    )

    return {"medicine": medicine, "billing": result}
