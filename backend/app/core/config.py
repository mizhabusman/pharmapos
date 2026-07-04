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
