"""
config.py — Central application settings for the PharmaPOS backend.

All paths, secrets, and tunable constants live here so the rest of the app
never has to know where the project root is or how pricing is calculated.
Values can be overridden via environment variables (see backend/.env).
"""

import os

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# .../backend/app/core/config.py  ->  core -> app -> backend -> <project root>
CORE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(CORE_DIR)
BACKEND_DIR = os.path.dirname(APP_DIR)
BASE_DIR = os.path.dirname(BACKEND_DIR)

DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "pharmacy_inventory.db")
CSV_PATH = os.path.join(DATA_DIR, "real_database.csv")

# ---------------------------------------------------------------------------
# Environment / secrets
# ---------------------------------------------------------------------------
# Load backend/.env explicitly so secrets resolve regardless of the directory
# the server is launched from.
load_dotenv(os.path.join(BACKEND_DIR, ".env"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Deployment environment: "development" (default) or "production". In
# production the app refuses to boot with insecure/missing secrets; in
# development the same problems are logged as warnings so local work still runs
# (see app.main.create_app + core/security.check_startup_security).
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()

# ---------------------------------------------------------------------------
# Gemini model + pricing (used to report per-scan token cost metrics)
# ---------------------------------------------------------------------------
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_INPUT_PRICE_PER_1M = float(os.getenv("GEMINI_INPUT_PRICE_PER_1M", "0.075"))
GEMINI_OUTPUT_PRICE_PER_1M = float(os.getenv("GEMINI_OUTPUT_PRICE_PER_1M", "0.30"))
INR_CONVERSION_RATE = float(os.getenv("INR_CONVERSION_RATE", "83.5"))

# ---------------------------------------------------------------------------
# CORS — comma-separated list of allowed frontend origins
# ---------------------------------------------------------------------------
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
# Current mode: a single shared login password/PIN (AUTH_PASSWORD). The token
# layer below is identity-agnostic, so switching to per-user accounts later
# only means changing how credentials are verified (see core/security.py).
# The insecure fallback signing key. It is also the default below, so the
# startup guard can treat "still the default" the same as "unset".
INSECURE_SECRET_DEFAULT = "dev-insecure-change-me"

AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "")            # shared login secret
AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY", INSECURE_SECRET_DEFAULT)
AUTH_ALGORITHM = "HS256"
AUTH_TOKEN_EXPIRE_MINUTES = int(os.getenv("AUTH_TOKEN_EXPIRE_MINUTES", "720"))  # 12h

# ---------------------------------------------------------------------------
# Login rate limiting (brute-force throttle — see core/rate_limit.py)
# ---------------------------------------------------------------------------
# After LOGIN_MAX_ATTEMPTS failures from one client IP within
# LOGIN_WINDOW_SECONDS, that IP is blocked for LOGIN_BLOCK_SECONDS.
LOGIN_MAX_ATTEMPTS = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))
LOGIN_WINDOW_SECONDS = int(os.getenv("LOGIN_WINDOW_SECONDS", "300"))   # 5 min
LOGIN_BLOCK_SECONDS = int(os.getenv("LOGIN_BLOCK_SECONDS", "300"))     # 5 min
