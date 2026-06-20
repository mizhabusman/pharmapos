from fastapi import FastAPI
from app.services.database_manager import fetch_raw_inventory
from app.services.preprocessor import load_inventory, create_search_index
from app.services.searcher import search_medicine

app = FastAPI()

# Load inventory once when server starts (not on every request — faster)
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