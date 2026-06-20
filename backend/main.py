import os
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile

from app.services.preprocessor import load_inventory, create_search_index
from app.services.searcher import search_medicine
from app.services.image_processor import optimize_for_upload
from app.services.gemini_extractor import run_extraction
from app.services.billing_engine import calculate_pack_billing
from app.services.database_manager import get_medicine_by_item_code

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

app = FastAPI()

inventory = create_search_index(load_inventory())

@app.get("/")
def read_root():
    return {"message": "PharmaPOS backend is alive"}

@app.get("/search")
def search(query: str):
    results = search_medicine(query, inventory)
    return {
        "query": query,
        "results": [
            {"matched_text": text, "score": score, "row_index": idx}
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