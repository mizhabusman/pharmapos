import logging
import sqlite3
from collections import defaultdict
import pandas as pd
from typing import Dict, List

from app.core.config import DB_PATH

logger = logging.getLogger(__name__)


def _to_int(value, default: int = 0) -> int:
    """Tolerant int: handles the CSV's fractional/text stock (e.g. '4.8033')
    instead of raising and making a real in-stock item look 'not found'."""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def fetch_raw_inventory() -> pd.DataFrame:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            return pd.read_sql("SELECT * FROM inventory", conn)
    except Exception as e:
        logger.error("Database fetch failed: %s", e)
        return pd.DataFrame() # Returns an empty dataframe if the file is missing
    
def get_medicine_by_item_code(item_code: int) -> dict:
    """
    Retrieves a single medicine record by its ID.
    Returns an empty dict if not found.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row  
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM inventory WHERE item_code = ?", (item_code,))
            row = cursor.fetchone()
            
            if row:
                data = dict(row)
                # Map names AND strictly enforce types before returning to the app
                return {
                    "item_code": _to_int(data.get("item_code", 0)),
                    "product_name": str(data.get("item_name", "")).strip(),
                    "pack_name": str(data.get("pack_name", "")).strip(),
                    "pack_size": max(1, _to_int(data.get("units_pack", 1), 1)),
                    "price_inr": max(0.0, _to_float(data.get("mrp", 0.0), 0.0)),
                    "stock": max(0, _to_int(data.get("stock", 0), 0)),
                }
                
    except Exception as e:
        logger.error("Failed to fetch medicine %s: %s", item_code, e)
        
    return {}

def _aggregate_packs(billing_items: List[Dict]) -> Dict[int, int]:
    """
    Sum requested packs per item_code. The same medicine can appear on more
    than one bill line (e.g. two prescriptions), and stock must cover their
    COMBINED quantity — checking each line independently would let a duplicate
    slip past validation only to fail at deduction.
    """
    totals: Dict[int, int] = defaultdict(int)
    for item in billing_items:
        totals[item.get("item_code")] += int(item.get("packs_needed", 0))
    return totals


def validate_stock(billing_items: List[Dict]) -> List[Dict]:
    """
    Checks if there is enough pack stock for the requested items.
    Returns an empty list if valid, or a list of insufficient items.

    Quantities are aggregated per item_code first, so ``required`` reflects the
    total across every line of that medicine, not a single line.
    """
    insufficient_items = []
    requested = _aggregate_packs(billing_items)

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            for item_code, packs_needed in requested.items():
                cursor.execute(
                    "SELECT item_name, pack_name, stock FROM inventory WHERE item_code = ?",
                    (item_code,)
                )
                row = cursor.fetchone()

                if not row:
                    insufficient_items.append({
                        "item_code": item_code,
                        "error": "Item not found in inventory"
                    })
                    continue

                # Tolerant coercion — a fractional/text stock ('4.8033') floors
                # to a whole sellable pack count instead of reading as 0.
                current_stock = _to_int(row["stock"], 0)

                # Now we are safely comparing int < int
                if current_stock < packs_needed:
                    full_name = f"{row['item_name']} {row['pack_name']}".strip()
                    insufficient_items.append({
                        "item_code": item_code,
                        "product_name": full_name,
                        "required": packs_needed,
                        "available": current_stock
                    })

    except Exception as e:
        logger.error("Stock validation failed: %s", e)
        return [{"error": f"Database failure during validation: {e}"}]

    return insufficient_items


def get_stock_for_item_codes(item_codes: List[int]) -> Dict[int, int]:
    """
    Live pack-stock for a set of item codes: ``{item_code: stock}``.

    Used to annotate search results with current availability (the in-memory
    search index's stock is only a startup snapshot and goes stale after sales,
    so we read the DB here). Codes that are missing or unreadable are omitted.
    """
    if not item_codes:
        return {}

    stock_map: Dict[int, int] = {}
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            placeholders = ",".join("?" for _ in item_codes)
            cursor.execute(
                f"SELECT item_code, stock FROM inventory WHERE item_code IN ({placeholders})",
                list(item_codes),
            )
            for row in cursor.fetchall():
                stock_map[_to_int(row["item_code"])] = max(0, _to_int(row["stock"], 0))
    except Exception as e:
        logger.error("Stock lookup failed: %s", e)

    return stock_map

def commit_sale(billing_items: List[Dict], bill_payload: dict) -> dict:
    """
    Atomically deduct stock AND persist the bill in a SINGLE transaction.

    Either the whole sale commits (stock reduced *and* bill recorded) or none
    of it does. Doing both in one transaction closes the integrity gap where
    stock could be deducted in one transaction while the bill failed to save in
    a separate one — leaving inventory reduced with no ledger entry to show for
    it.

    The stock UPDATE is guarded (``WHERE stock >= packs_needed``); a rowcount of
    zero means the stock was taken between the pre-flight ``validate_stock``
    check and now (a race), so the whole sale is aborted and rolled back.

    Returns ``{"success": True, "bill_id": int}`` on success, or
    ``{"success": False, "message": str}`` on any failure (nothing persisted).
    """
    # Never persist a header-only bill with no line items.
    if not billing_items:
        return {"success": False, "message": "No items to bill"}

    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Enforce the bill_items -> bills foreign key for this transaction.
            conn.execute("PRAGMA foreign_keys = ON")
            cursor = conn.cursor()

            # --- 1) Deduct stock (guarded; CAST handles CSV-string columns) ---
            # Aggregate per item first: a medicine on two lines must deduct its
            # COMBINED packs in one guarded UPDATE, otherwise the first line
            # could succeed and the second fail on the same (now-lower) stock.
            for item_code, packs_needed in _aggregate_packs(billing_items).items():
                cursor.execute("""
                    UPDATE inventory
                    SET stock = CAST(stock AS INTEGER) - ?
                    WHERE item_code = ? AND CAST(stock AS INTEGER) >= ?
                """, (packs_needed, item_code, packs_needed))

                if cursor.rowcount == 0:
                    # Raising here aborts the `with` block -> full rollback, so
                    # no earlier deduction or bill row survives.
                    raise sqlite3.IntegrityError(
                        f"Concurrency error: Insufficient stock for item {item_code} during deduction."
                    )

            # --- 2) Insert the bill header ---
            cursor.execute("""
                INSERT INTO bills (patient_name, age, grand_total, timestamp)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                bill_payload.get("patient_name", "Unknown"),
                bill_payload.get("age", 0),
                bill_payload.get("grand_total", 0.0),
            ))
            bill_id = cursor.lastrowid  # unique id the DB assigned this bill

            # --- 3) Insert the line items (foreign-keyed to the header) ---
            items_data = [
                (
                    bill_id,
                    item.get("item_code"),
                    item.get("packs_needed", 0),
                    item.get("billed_qty", 0),
                    item.get("line_total", 0.0),
                )
                for item in billing_items
            ]
            cursor.executemany("""
                INSERT INTO bill_items (bill_id, item_code, packs_needed, billed_qty, line_total)
                VALUES (?, ?, ?, ?, ?)
            """, items_data)

        # Leaving the `with` block commits on success, rolls back on exception.
        return {"success": True, "bill_id": bill_id}

    except sqlite3.IntegrityError as e:
        # Expected failure (stock race) — nothing was committed.
        logger.warning("Sale aborted, rolled back (stock/integrity): %s", e)
        return {"success": False, "message": str(e)}
    except Exception as e:
        logger.error("Sale commit failed, rolled back: %s", e)
        return {"success": False, "message": f"Transaction failed: {str(e)}"}

def initialize_database():
    """
    Permanent database initialization. 
    Runs automatically to ensure transaction tables exist.
    Uses IF NOT EXISTS so it is completely safe to run on every startup.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Enforce relational rules
            conn.execute("PRAGMA foreign_keys = ON")
            cursor = conn.cursor()
            
            # Create Ledger Header Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bills (
                    bill_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_name TEXT DEFAULT 'Unknown',
                    age INTEGER DEFAULT 0,
                    grand_total REAL DEFAULT 0.0,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create Ledger Line Items Table
            cursor.execute("""
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
    except Exception as e:
        logger.error("CRITICAL: Failed to initialize database structure: %s", e)

# ==========================================
# AUTO-RUN ON STARTUP
# ==========================================
# By calling this at the bottom of the file, the manager automatically 
# self-checks the database the exact second this file is imported by your app.
initialize_database()