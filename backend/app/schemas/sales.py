"""
sales.py — Pydantic request models for the sale/checkout flow.
"""

from typing import List

from pydantic import BaseModel


class BillingItem(BaseModel):
    item_code: int
    packs_needed: int
    billed_qty: int
    line_total: float


class SaleRequest(BaseModel):
    patient_name: str = "Unknown"
    age: int = 0
    gender: str = "Unknown"
    grand_total: float
    billing_items: List[BillingItem]
