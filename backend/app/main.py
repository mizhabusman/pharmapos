"""
main.py — PharmaPOS FastAPI application entry point.

Run from the ``backend/`` directory:
    uvicorn app.main:app --reload
"""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import CORS_ORIGINS, DB_PATH, MAX_UPLOAD_BYTES
from app.routers import billing, extraction, health, sales, search
from app.services.database_manager import initialize_database
from app.services.preprocessor import create_search_index, load_inventory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title="PharmaPOS", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Reject oversized request bodies up front (before multipart spooling / JSON
    # parsing), so a huge upload can't exhaust memory or disk on the server.
    @app.middleware("http")
    async def limit_body_size(request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > MAX_UPLOAD_BYTES:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": {
                            "message": f"Request too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)."
                        }},
                    )
            except ValueError:
                pass
        return await call_next(request)

    # Ensure the ledger tables exist (runs here, not at import time, so tests
    # and any pre-db_setup import don't create tables in the real DB).
    initialize_database()

    # Build the in-memory fuzzy-search index once at startup and share it
    # across requests via app.state (see routers/search.py).
    inventory = create_search_index(load_inventory())
    app.state.inventory = inventory

    if inventory.empty:
        logger.warning(
            "Inventory is EMPTY. Did you build the database? "
            "Run `python scripts/db_setup.py`. Expected DB at: %s",
            DB_PATH,
        )
    else:
        logger.info("Loaded %d inventory items from %s", len(inventory), DB_PATH)

    # All routes are public — authentication was removed for the first release.
    app.include_router(health.router)
    app.include_router(search.router)
    app.include_router(extraction.router)
    app.include_router(billing.router)
    app.include_router(sales.router)

    return app


app = create_app()
