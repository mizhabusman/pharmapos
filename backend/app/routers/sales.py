"""
sales.py — Confirm a sale: rebuild the bill from authoritative prices,
validate stock, deduct inventory, persist the bill.
"""

from fastapi import APIRouter

from app.schemas.sales import SaleRequest
from app.services.checkout import build_authoritative_bill
from app.services.database_manager import deduct_stock, save_bill, validate_stock

router = APIRouter(tags=["sales"])


@router.post("/confirm-sale")
def confirm_sale(sale: SaleRequest):
    # Never trust client-supplied prices/totals — recompute every line item
    # and the grand total from the inventory's own price data.
    billing_items, grand_total, errors = build_authoritative_bill(
        [item.dict() for item in sale.billing_items]
    )
    if errors:
        return {"success": False, "error": "Invalid items", "details": errors}
    if not billing_items:
        return {"success": False, "error": "No billable items"}

    insufficient = validate_stock(billing_items)
    if insufficient:
        return {"success": False, "error": "Insufficient stock", "details": insufficient}

    deduction_result = deduct_stock(billing_items)
    if not deduction_result["success"]:
        return {"success": False, "error": deduction_result["message"]}

    bill_payload = {
        "patient_name": sale.patient_name,
        "age": sale.age,
        "grand_total": grand_total,
        "billing_items": billing_items,
    }
    save_result = save_bill(bill_payload)

    # Surface the authoritative total so the client can reconcile its display.
    if save_result.get("success"):
        save_result["grand_total"] = grand_total

    return save_result
