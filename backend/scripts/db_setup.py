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
        print(f"❌ Error: '{CSV_PATH}' not found.")
        return

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

    print(f"Creating database '{DB_PATH}'...")

    with sqlite3.connect(DB_PATH) as conn:
        # Enforce relational rules
        conn.execute("PRAGMA foreign_keys = ON")

        # 3. Create the 'inventory' table from the dataframe
        df.to_sql("inventory", conn, if_exists="replace", index=False)
        print("✅ Successfully imported 'inventory' table.")

        # 4. Create Ledger Header Table (bills)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bills (
                bill_id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_name TEXT DEFAULT 'Unknown',
                age INTEGER DEFAULT 0,
                grand_total REAL DEFAULT 0.0,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ Successfully created 'bills' table.")

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
        print("✅ Successfully created 'bill_items' table.")

    print("\n🎉 Database rebuild complete! Start the API with 'uvicorn app.main:app --reload'.")


if __name__ == "__main__":
    rebuild_database()
