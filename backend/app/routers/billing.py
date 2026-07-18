"""
billing.py — Convert a prescribed quantity into pack-based billing figures.
"""

from fastapi import APIRouter, HTTPException, Query

from app.services.billing_engine import calculate_pack_billing
from app.services.database_manager import get_medicine_by_item_code

router = APIRouter(tags=["billing"])


@router.get("/billing")
def get_billing(
    item_code: int = Query(ge=0),
    # Bounded so an absurd quantity can't 500 or be silently treated as 1 pack;
    # out-of-range values return a clean 422.
    rx_qty: int = Query(ge=1, le=1_000_000),
):
    medicine = get_medicine_by_item_code(item_code)
    if not medicine:
        raise HTTPException(
            status_code=404,
            detail={"message": "Medicine not found", "item_code": item_code},
        )

    result = calculate_pack_billing(
        rx_qty=rx_qty,
        pack_size=medicine["pack_size"],
        pack_price=medicine["price_inr"],
    )

    return {"medicine": medicine, "billing": result}
