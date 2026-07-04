"""
Shared pytest fixtures.

Every test runs against a throwaway SQLite database seeded with a tiny,
predictable inventory — the real data/pharmacy_inventory.db is never touched.
We point the app at it by monkeypatching the DB_PATH that database_manager
resolved at import time, then building a fresh app so its in-memory search
index loads from the test DB.
"""

import os
import sqlite3
import sys

import pandas as pd
import pytest

# Make the `app` package importable regardless of pytest's rootdir.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

# Small, deterministic inventory. Columns match what db_setup.py produces
# (and what database_manager / preprocessor read).
SEED_INVENTORY = [
    # item_code, item_name,            units_pack, pack_name, mrp,    stock
    (1001, "Pantop Tab 40mg",   15, "15s", 150.00, 3),
    (1002, "Aciloc Tab 150mg",  10, "10s",  68.50, 0),   # out of stock
    (1003, "Crocin Tab 500mg",  10, "10s",  30.00, 5),
]


def _seed_database(db_path: str) -> None:
    df = pd.DataFrame(
        SEED_INVENTORY,
        columns=["item_code", "item_name", "units_pack", "pack_name", "mrp", "stock"],
    )
    with sqlite3.connect(db_path) as conn:
        df.to_sql("inventory", conn, if_exists="replace", index=False)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bills (
                bill_id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_name TEXT DEFAULT 'Unknown',
                age INTEGER DEFAULT 0,
                grand_total REAL DEFAULT 0.0,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bill_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bill_id INTEGER,
                item_code INTEGER,
                packs_needed INTEGER,
                billed_qty INTEGER,
                line_total REAL,
                FOREIGN KEY (bill_id) REFERENCES bills (bill_id)
            )
        """)


@pytest.fixture()
def db_path(tmp_path, monkeypatch):
    """A freshly seeded temp DB, wired in as the app's database."""
    path = str(tmp_path / "test_pharmacy.db")
    _seed_database(path)
    monkeypatch.setattr("app.services.database_manager.DB_PATH", path)
    return path


@pytest.fixture()
def client(db_path):
    """A TestClient whose app was built against the seeded temp DB."""
    from starlette.testclient import TestClient

    from app.main import create_app

    return TestClient(create_app())


@pytest.fixture()
def db_conn(db_path):
    """Read-only-ish connection for asserting persisted rows."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()
