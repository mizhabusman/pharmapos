"""
main.py — PharmaPOS FastAPI application entry point.

Run from the ``backend/`` directory:
    uvicorn app.main:app --reload
"""

import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import (
    CORS_ORIGINS,
    DB_PATH,
    ENVIRONMENT,
    LOGIN_BLOCK_SECONDS,
    LOGIN_MAX_ATTEMPTS,
    LOGIN_WINDOW_SECONDS,
)
from app.core.rate_limit import LoginRateLimiter
from app.core.security import check_startup_security, get_current_user
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

    # Refuse to run with insecure secrets in production; only warn in dev so
    # local work still starts. Keeps a misconfigured server from ever facing
    # the internet with the default signing key or no login password.
    problems = check_startup_security()
    if problems:
        if ENVIRONMENT == "production":
            raise RuntimeError(
                "Refusing to start in production with insecure configuration: "
                + " | ".join(problems)
            )
        for problem in problems:
            logger.warning("SECURITY (fatal in production): %s", problem)

    # Per-app login throttle — brute-force protection for the shared password.
    app.state.login_limiter = LoginRateLimiter(
        max_attempts=LOGIN_MAX_ATTEMPTS,
        window_seconds=LOGIN_WINDOW_SECONDS,
        block_seconds=LOGIN_BLOCK_SECONDS,
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
