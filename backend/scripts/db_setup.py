"""
db_setup.py — Rebuild the SQLite inventory database from the source CSV.

Reads data/real_database.csv, (re)creates the `inventory` table, and ensures
the `bills` / `bill_items` ledger tables exist.

Run from anywhere:
    python backend/scripts/db_setup.py
"""

import os
import sqlite3
import sys

import pandas as pd

# Make the `app` package importable when running this script directly.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from app.core.config import CSV_PATH, DB_PATH  # noqa: E402


def rebuild_database():
    print(f"Reading data from {CSV_PATH}...")

    if not os.path.exists(CSV_PATH):
        # Exit non-zero so a deploy pipeline (`db_setup && uvicorn ...`) STOPS
        # here instead of booting a server with an empty inventory.
        print(f"ERROR: '{CSV_PATH}' not found.")
        sys.exit(1)

    # 1. Load the CSV
    df = pd.read_csv(CSV_PATH)

    # 2. Rename columns to EXACTLY match what database_manager.py expects
    df = df.rename(columns={
        "Slno": "slno",
        "Item Code": "item_code",
        "Item Name": "item_name",
        "Units/Pack": "units_pack",
        "Pack Name": "pack_name",
        "MRP": "mrp",
        "SOH In Packs": "stock",
    })

    # 3. Clean numeric columns at build time. The source stock ('SOH In Packs')
    #    contains fractional/garbage values ('4.8033', '1h'); floor them to whole
    #    sellable packs so the stored data is exact (the app also coerces
    #    defensively at read time).
    df["stock"] = pd.to_numeric(df["stock"], errors="coerce").fillna(0).clip(lower=0).astype(int)
    df["mrp"] = pd.to_numeric(df["mrp"], errors="coerce").fillna(0.0).clip(lower=0.0)
    df["units_pack"] = pd.to_numeric(df["units_pack"], errors="coerce").fillna(1).clip(lower=1).astype(int)
    df["item_code"] = pd.to_numeric(df["item_code"], errors="coerce")
    df = df.dropna(subset=["item_code"])
    df["item_code"] = df["item_code"].astype(int)

    print(f"Creating database '{DB_PATH}'...")

    with sqlite3.connect(DB_PATH) as conn:
        # Enforce relational rules
        conn.execute("PRAGMA foreign_keys = ON")

        # 4. Create the 'inventory' table from the dataframe
        df.to_sql("inventory", conn, if_exists="replace", index=False)
        # One row per item_code — a duplicate in a future CSV would otherwise
        # make a sale deduct from every duplicate row. This CREATE fails loudly
        # if the source ever contains a duplicated Item Code.
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_inventory_item_code ON inventory(item_code)"
        )
        print("  - imported 'inventory' table")

        # 4. Create Ledger Header Table (bills)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bills (
                bill_id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_name TEXT DEFAULT 'Unknown',
                age INTEGER DEFAULT 0,
                gender TEXT DEFAULT 'Unknown',
                grand_total REAL DEFAULT 0.0,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("  - ensured 'bills' table")

        # 5. Create Ledger Line Items Table (bill_items)
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
        print("  - ensured 'bill_items' table")

    print("\nDatabase rebuild complete. Start the API with 'uvicorn app.main:app --reload'.")


if __name__ == "__main__":
    rebuild_database()
