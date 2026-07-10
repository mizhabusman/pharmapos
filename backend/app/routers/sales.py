"""
sales.py — Confirm a sale: rebuild the bill from authoritative prices,
validate stock, deduct inventory, persist the bill.
"""

from fastapi import APIRouter

from app.schemas.sales import SaleRequest
from app.services.checkout import build_authoritative_bill
from app.services.database_manager import commit_sale, validate_stock

router = APIRouter(tags=["sales"])


@router.post("/confirm-sale")
def confirm_sale(sale: SaleRequest):
    # Never trust client-supplied prices/totals — recompute every line item
    # and the grand total from the inventory's own price data.
    billing_items, grand_total, errors = build_authoritative_bill(
        [item.model_dump() for item in sale.billing_items]
    )
    if errors:
        return {"success": False, "error": "Invalid items", "details": errors}
    if not billing_items:
        return {"success": False, "error": "No billable items"}

    # Pre-flight check → rich, per-item stock messages for the UI. The real
    # guard against overselling lives inside commit_sale's guarded UPDATE; this
    # just turns the common case into a friendly, itemised rejection.
    insufficient = validate_stock(billing_items)
    if insufficient:
        return {"success": False, "error": "Insufficient stock", "details": insufficient}

    # Deduct stock AND persist the bill atomically — all-or-nothing, so stock
    # is never reduced without a recorded bill (or vice versa).
    bill_payload = {
        "patient_name": sale.patient_name,
        "age": sale.age,
        "grand_total": grand_total,
        "billing_items": billing_items,
    }
    result = commit_sale(billing_items, bill_payload)
    if not result.get("success"):
        return {"success": False, "error": result.get("message", "Sale could not be completed")}

    # Surface the authoritative total so the client can reconcile its display.
    result["grand_total"] = grand_total
    return result
