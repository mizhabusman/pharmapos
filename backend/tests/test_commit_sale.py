"""
Tests for commit_sale — the atomic (deduct stock + persist bill) transaction.

The whole point of commit_sale is all-or-nothing: a sale must never deduct
stock without recording a bill, and a failure partway through must leave the
database exactly as it started.
"""

from app.services.database_manager import commit_sale


def _bill_payload(items, name="Atomic Test", age=42, grand_total=0.0):
    return {
        "patient_name": name,
        "age": age,
        "grand_total": grand_total,
        "billing_items": items,
    }


def test_commit_sale_deducts_stock_and_persists_bill(db_path, db_conn):
    # item 1001 starts with stock 3.
    items = [
        {"item_code": 1001, "packs_needed": 2, "billed_qty": 30, "line_total": 300.00},
    ]
    result = commit_sale(items, _bill_payload(items, grand_total=300.00))

    assert result["success"] is True
    bill_id = result["bill_id"]

    # Bill header persisted with the right total.
    header = db_conn.execute(
        "SELECT patient_name, grand_total FROM bills WHERE bill_id = ?", (bill_id,)
    ).fetchone()
    assert header["grand_total"] == 300.00

    # Exactly one line item persisted.
    lines = db_conn.execute(
        "SELECT COUNT(*) AS n FROM bill_items WHERE bill_id = ?", (bill_id,)
    ).fetchone()["n"]
    assert lines == 1

    # Stock deducted by two packs (3 -> 1).
    stock = db_conn.execute(
        "SELECT CAST(stock AS INTEGER) AS s FROM inventory WHERE item_code = 1001"
    ).fetchone()["s"]
    assert stock == 1


def test_commit_sale_rolls_back_entirely_when_one_item_is_short(db_path, db_conn):
    # A multi-item sale where the FIRST item is fine (1001 has 3 packs) but the
    # SECOND asks for more than exists (1003 has 5). This simulates a stock race
    # slipping past the pre-flight validate_stock check. The guarded UPDATE must
    # abort the whole transaction — including the first item's deduction.
    items = [
        {"item_code": 1001, "packs_needed": 2, "billed_qty": 30, "line_total": 300.00},
        {"item_code": 1003, "packs_needed": 99, "billed_qty": 990, "line_total": 2970.00},
    ]
    result = commit_sale(items, _bill_payload(items, grand_total=3270.00))

    assert result["success"] is False

    # No bill header and no line items were written.
    assert db_conn.execute("SELECT COUNT(*) AS n FROM bills").fetchone()["n"] == 0
    assert db_conn.execute("SELECT COUNT(*) AS n FROM bill_items").fetchone()["n"] == 0

    # Crucially, the FIRST item's stock is untouched — the partial deduction was
    # rolled back, not left half-applied.
    stock_1001 = db_conn.execute(
        "SELECT CAST(stock AS INTEGER) AS s FROM inventory WHERE item_code = 1001"
    ).fetchone()["s"]
    stock_1003 = db_conn.execute(
        "SELECT CAST(stock AS INTEGER) AS s FROM inventory WHERE item_code = 1003"
    ).fetchone()["s"]
    assert stock_1001 == 3
    assert stock_1003 == 5
