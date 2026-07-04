"""
main.py — PharmaPOS FastAPI application entry point.

Run from the ``backend/`` directory:
    uvicorn app.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import CORS_ORIGINS
from app.routers import billing, extraction, health, sales, search
from app.services.preprocessor import create_search_index, load_inventory


def create_app() -> FastAPI:
    app = FastAPI(title="PharmaPOS", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Build the in-memory fuzzy-search index once at startup and share it
    # across requests via app.state (see routers/search.py).
    app.state.inventory = create_search_index(load_inventory())

    app.include_router(health.router)
    app.include_router(search.router)
    app.include_router(extraction.router)
    app.include_router(billing.router)
    app.include_router(sales.router)

    return app


app = create_app()
