"""
main.py — PharmaPOS FastAPI application entry point.

Run from the ``backend/`` directory:
    uvicorn app.main:app --reload
"""

import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import AUTH_PASSWORD, CORS_ORIGINS, DB_PATH
from app.core.security import get_current_user
from app.routers import auth, billing, extraction, health, sales, search
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

    if not AUTH_PASSWORD:
        logger.warning(
            "AUTH_PASSWORD is not set — all logins will fail. "
            "Set it in backend/.env before deploying."
        )

    # Public routes: health check + login.
    app.include_router(health.router)
    app.include_router(auth.router)

    # Protected routes: require a valid bearer token. Wiring the guard here at
    # include-time keeps each router file free of auth concerns.
    protected = [Depends(get_current_user)]
    app.include_router(search.router, dependencies=protected)
    app.include_router(extraction.router, dependencies=protected)
    app.include_router(billing.router, dependencies=protected)
    app.include_router(sales.router, dependencies=protected)

    return app


app = create_app()
