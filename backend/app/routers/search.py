"""
search.py — Fuzzy medicine search against the in-memory inventory index.

The search index is built once at startup and shared via ``app.state.inventory``
(see app/main.py).
"""

from fastapi import APIRouter, Request

from app.services.searcher import search_medicine

router = APIRouter(tags=["search"])


@router.get("/search")
def search(query: str, request: Request):
    inventory = request.app.state.inventory
    results = search_medicine(query, inventory)
    return {
        "query": query,
        "results": [
            {
                "matched_text": text,
                "score": score,
                "row_index": idx,
                "item_code": int(inventory.iloc[idx]["item_code"]),
            }
            for text, score, idx in results
        ],
    }
