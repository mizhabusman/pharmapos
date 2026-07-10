"""
search.py — Fuzzy medicine search against the in-memory inventory index.

The search index is built once at startup and shared via ``app.state.inventory``
(see app/main.py).
"""

from fastapi import APIRouter, Request

from app.services.database_manager import get_stock_for_item_codes
from app.services.searcher import search_medicine

router = APIRouter(tags=["search"])


@router.get("/search")
def search(query: str, request: Request):
    inventory = request.app.state.inventory
    results = search_medicine(query, inventory)

    # Annotate each candidate with LIVE stock so the UI can flag out-of-stock /
    # low-stock right in the dropdown (the search index's stock is a stale
    # startup snapshot; the DB is the source of truth).
    item_codes = [int(inventory.iloc[idx]["item_code"]) for _, _, idx in results]
    stock_map = get_stock_for_item_codes(item_codes)

    return {
        "query": query,
        "results": [
            {
                "matched_text": text,
                "score": score,
                "row_index": idx,
                "item_code": int(inventory.iloc[idx]["item_code"]),
                "stock": stock_map.get(int(inventory.iloc[idx]["item_code"]), 0),
            }
            for text, score, idx in results
        ],
    }
