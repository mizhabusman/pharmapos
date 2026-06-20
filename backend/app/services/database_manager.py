import sqlite3
import pandas as pd
from typing import List, Dict

from app.services.config import DB_PATH

def fetch_raw_inventory() -> pd.DataFrame:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            return pd.read_sql("SELECT * FROM inventory", conn)
    except Exception as e:
        print(f"Database fetch failed: {e}")
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
                    "item_code": int(data.get("item_code", 0)),
                    "product_name": str(data.get("item_name", "")).strip(),
                    "pack_name": str(data.get("pack_name", "")).strip(),
                    "pack_size": int(data.get("units_pack", 1)),
                    "price_inr": float(data.get("mrp", 0.0)),
                    "stock": int(data.get("stock", 0))
                }
                
    except Exception as e:
        print(f"Failed to fetch medicine {item_code}: {e}")
        
    return {}

def validate_stock(billing_items: List[Dict]) -> List[Dict]:
    """
    Checks if there is enough pack stock for the requested items.
    Returns an empty list if valid, or a list of insufficient items.
    """
    insufficient_items = []
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            for item in billing_items:
                item_code = item.get("item_code")
                # Ensure packs_needed is an integer
                packs_needed = int(item.get("packs_needed", 0))
                
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
                    
                # STRICT TYPE ENFORCEMENT: Convert string "13" from db to integer 13
                try:
                    current_stock = int(row["stock"])
                except (ValueError, TypeError):
                    current_stock = 0
                
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
        print(f"Stock validation failed: {e}")
        return [{"error": f"Database failure during validation: {e}"}]
        
    return insufficient_items

def deduct_stock(billing_items: List[Dict]) -> dict:
    """
    Reduces inventory stock. Uses strict COMMIT/ROLLBACK logic.
    Fails completely if any single item lacks stock to prevent partial updates.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            for item in billing_items:
                item_code = item.get("item_code")
                packs_needed = int(item.get("packs_needed", 0)) # Force Python int
                
                # We use CAST() to force SQLite to treat the CSV strings as real math numbers
                cursor.execute("""
                    UPDATE inventory 
                    SET stock = CAST(stock AS INTEGER) - ? 
                    WHERE item_code = ? AND CAST(stock AS INTEGER) >= ?
                """, (packs_needed, item_code, packs_needed))
                
                if cursor.rowcount == 0:
                    raise sqlite3.IntegrityError(f"Concurrency error: Insufficient stock for item {item_code} during deduction.")
                    
        return {"success": True, "message": "Stock updated successfully"}
        
    except Exception as e:
        print(f"Stock deduction failed: {e}")
        return {"success": False, "message": f"Transaction failed: {str(e)}"}
    
def save_bill(billing_json: dict) -> dict:
    """
    Stores the completed sale in the database.
    Creates a bill header and line items in a single transaction.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Step 1: Insert the Bill Header
            cursor.execute("""
                INSERT INTO bills (patient_name, age, grand_total, timestamp)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                billing_json.get("patient_name", "Unknown"),
                billing_json.get("age", 0),
                billing_json.get("grand_total", 0.0)
            ))
            
            # Step 2: Grab the unique ID the database just created for this bill
            bill_id = cursor.lastrowid
            
            # Step 3: Prepare the Line Items
            items_data = []
            for item in billing_json.get("billing_items", []):
                items_data.append((
                    bill_id,                            # The foreign key linking to the header
                    item.get("item_code"),
                    item.get("packs_needed", 0),
                    item.get("billed_qty", 0),
                    item.get("line_total", 0.0)
                ))
                
            # Step 4: Bulk Insert the Line Items
            cursor.executemany("""
                INSERT INTO bill_items (bill_id, item_code, packs_needed, billed_qty, line_total)
                VALUES (?, ?, ?, ?, ?)
            """, items_data)
            
        return {"success": True, "bill_id": bill_id}
        
    except Exception as e:
        print(f"Failed to save bill: {e}")
        return {"success": False, "message": f"Failed to save ledger record: {str(e)}"}
    
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
        print(f"CRITICAL: Failed to initialize database structure: {e}")

# ==========================================
# AUTO-RUN ON STARTUP
# ==========================================
# By calling this at the bottom of the file, the manager automatically 
# self-checks the database the exact second this file is imported by your app.
initialize_database()