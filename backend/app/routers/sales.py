"""
sales.py — Confirm a sale: validate stock, deduct inventory, persist the bill.
"""

from fastapi import APIRouter

from app.schemas.sales import SaleRequest
from app.services.database_manager import deduct_stock, save_bill, validate_stock

router = APIRouter(tags=["sales"])


@router.post("/confirm-sale")
def confirm_sale(sale: SaleRequest):
    billing_items = [item.dict() for item in sale.billing_items]

    insufficient = validate_stock(billing_items)
    if insufficient:
        return {"success": False, "error": "Insufficient stock", "details": insufficient}

    deduction_result = deduct_stock(billing_items)
    if not deduction_result["success"]:
        return {"success": False, "error": deduction_result["message"]}

    bill_payload = {
        "patient_name": sale.patient_name,
        "age": sale.age,
        "grand_total": sale.grand_total,
        "billing_items": billing_items,
    }
    save_result = save_bill(bill_payload)

    return save_result
