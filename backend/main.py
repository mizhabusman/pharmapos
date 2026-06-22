import os
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile
from pydantic import BaseModel
from typing import List

from fastapi.middleware.cors import CORSMiddleware

from app.services.database_manager import (
    fetch_raw_inventory,
    get_medicine_by_item_code,
    validate_stock,
    deduct_stock,
    save_bill
)
from app.services.preprocessor import load_inventory, create_search_index
from app.services.searcher import search_medicine
from app.services.image_processor import optimize_for_upload
from app.services.gemini_extractor import run_extraction
from app.services.billing_engine import calculate_pack_billing

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

inventory = create_search_index(load_inventory())


# ================================================================
# REQUEST MODELS
# ================================================================
class BillingItem(BaseModel):
    item_code: int
    packs_needed: int
    billed_qty: int
    line_total: float


class SaleRequest(BaseModel):
    patient_name: str = "Unknown"
    age: int = 0
    grand_total: float
    billing_items: List[BillingItem]


# ================================================================
# ROUTES
# ================================================================
@app.get("/")
def read_root():
    return {"message": "PharmaPOS backend is alive"}


@app.get("/search")
def search(query: str):
    results = search_medicine(query, inventory)
    return {
        "query": query,
        "results": [
            {
                "matched_text": text,
                "score": score,
                "row_index": idx,
                "item_code": int(inventory.iloc[idx]["item_code"])
            }
            for text, score, idx in results
        ]
    }

@app.post("/extract")
async def extract_prescription(file: UploadFile):
    raw_bytes = await file.read()
    compressed_bytes = optimize_for_upload(raw_bytes)
    result = run_extraction(compressed_bytes, GEMINI_API_KEY)
    return result


@app.get("/billing")
def get_billing(item_code: int, rx_qty: int):
    medicine = get_medicine_by_item_code(item_code)
    if not medicine:
        return {"error": "Medicine not found"}

    result = calculate_pack_billing(
        rx_qty=rx_qty,
        pack_size=medicine["pack_size"],
        pack_price=medicine["price_inr"]
    )

    return {
        "medicine": medicine,
        "billing": result
    }


@app.post("/confirm-sale")
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
        "billing_items": billing_items
    }
    save_result = save_bill(bill_payload)

    return save_result