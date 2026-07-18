"""Integration tests for the HTTP endpoints (against a seeded temp DB)."""


def test_health(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json() == {"message": "PharmaPOS backend is alive"}


def test_search_returns_matches(client):
    r = client.get("/search", params={"query": "Pantop"})
    assert r.status_code == 200
    results = r.json()["results"]
    assert results and results[0]["item_code"] == 1001


def test_billing_uses_inventory_price(client):
    r = client.get("/billing", params={"item_code": 1001, "rx_qty": 15})
    assert r.status_code == 200
    body = r.json()
    assert body["medicine"]["price_inr"] == 150.00
    assert body["billing"]["packs_needed"] == 1
    assert body["billing"]["line_total"] == 150.00


def test_billing_unknown_item_returns_404(client):
    r = client.get("/billing", params={"item_code": 999999, "rx_qty": 1})
    assert r.status_code == 404
    assert r.json()["detail"]["item_code"] == 999999


def test_billing_rejects_zero_or_negative_qty(client):
    assert client.get("/billing", params={"item_code": 1001, "rx_qty": 0}).status_code == 422
    assert client.get("/billing", params={"item_code": 1001, "rx_qty": -5}).status_code == 422


def test_billing_rejects_absurd_qty_instead_of_500(client):
    # Previously a ~309+ digit rx_qty caused an OverflowError 500.
    r = client.get("/billing", params={"item_code": 1001, "rx_qty": "1" + "0" * 400})
    assert r.status_code == 422


def test_search_rejects_overlong_query(client):
    r = client.get("/search", params={"query": "a" * 500})
    assert r.status_code == 422


def test_fractional_stock_item_is_sellable(client):
    # item 1005 has TEXT stock '4.8' — must read as 4 packs, not 404/out-of-stock.
    r = client.get("/billing", params={"item_code": 1005, "rx_qty": 10})
    assert r.status_code == 200
    assert r.json()["medicine"]["stock"] == 4
    # and it can actually be sold within that stock
    payload = {
        "patient_name": "Frac", "age": 30, "grand_total": 0,
        "billing_items": [{"item_code": 1005, "packs_needed": 3, "billed_qty": 30, "line_total": 150}],
    }
    assert client.post("/confirm-sale", json=payload).json()["success"] is True


def test_zero_price_item_is_rejected(client):
    # item 1004 has MRP 0 — must not sell for free.
    payload = {
        "patient_name": "Free", "age": 30, "grand_total": 0,
        "billing_items": [{"item_code": 1004, "packs_needed": 1, "billed_qty": 10, "line_total": 0}],
    }
    body = client.post("/confirm-sale", json=payload).json()
    assert body["success"] is False
    assert body["error"] == "Invalid items"


def test_search_results_include_live_stock(client):
    r = client.get("/search", params={"query": "Pantop"})
    assert r.status_code == 200
    top = next(x for x in r.json()["results"] if x["item_code"] == 1001)
    assert top["stock"] == 3          # seed stock for Pantop
    aciloc = next((x for x in r.json()["results"] if x["item_code"] == 1002), None)
    if aciloc:
        assert aciloc["stock"] == 0   # out of stock in the seed


def test_confirm_sale_aggregates_duplicate_lines_over_stock(client):
    # item 1001 has stock 3; two lines asking 2 + 2 = 4 packs must be rejected,
    # and the reported requirement must reflect the COMBINED quantity.
    payload = {
        "patient_name": "Dup", "age": 20, "grand_total": 0,
        "billing_items": [
            {"item_code": 1001, "packs_needed": 2, "billed_qty": 30, "line_total": 300},
            {"item_code": 1001, "packs_needed": 2, "billed_qty": 30, "line_total": 300},
        ],
    }
    body = client.post("/confirm-sale", json=payload).json()
    assert body["success"] is False
    assert body["error"] == "Insufficient stock"
    detail = body["details"][0]
    assert detail["required"] == 4 and detail["available"] == 3


def test_confirm_sale_duplicate_lines_within_stock_deduct_combined(client, db_conn):
    # item 1003 has stock 5; two lines of 2 + 2 = 4 <= 5 succeed, deducting the
    # combined 4 once and recording both lines.
    payload = {
        "patient_name": "Dup2", "age": 20, "grand_total": 0,
        "billing_items": [
            {"item_code": 1003, "packs_needed": 2, "billed_qty": 20, "line_total": 60},
            {"item_code": 1003, "packs_needed": 2, "billed_qty": 20, "line_total": 60},
        ],
    }
    body = client.post("/confirm-sale", json=payload).json()
    assert body["success"] is True
    stock = db_conn.execute(
        "SELECT CAST(stock AS INTEGER) AS s FROM inventory WHERE item_code = 1003"
    ).fetchone()["s"]
    assert stock == 1                                     # 5 - (2+2)
    lines = db_conn.execute(
        "SELECT COUNT(*) AS n FROM bill_items WHERE bill_id = ?", (body["bill_id"],)
    ).fetchone()["n"]
    assert lines == 2                                     # both lines recorded


def test_confirm_sale_enforces_server_price(client, db_conn):
    # Attempt to underpay: client claims line_total 0.01.
    payload = {
        "patient_name": "Tamper",
        "age": 40,
        "grand_total": 0.01,
        "billing_items": [
            {"item_code": 1001, "packs_needed": 1, "billed_qty": 999, "line_total": 0.01},
        ],
    }
    r = client.post("/confirm-sale", json=payload)
    body = r.json()
    assert body["success"] is True
    assert body["grand_total"] == 150.00

    # The persisted bill reflects the real price, not the tampered one.
    saved = db_conn.execute(
        "SELECT grand_total FROM bills WHERE bill_id = ?", (body["bill_id"],)
    ).fetchone()
    assert saved["grand_total"] == 150.00

    # Stock was deducted by exactly one pack (3 -> 2).
    stock = db_conn.execute(
        "SELECT CAST(stock AS INTEGER) AS s FROM inventory WHERE item_code = 1001"
    ).fetchone()["s"]
    assert stock == 2


def test_confirm_sale_rejects_insufficient_stock(client):
    # item 1002 has 0 stock.
    payload = {
        "patient_name": "Nope",
        "age": 30,
        "grand_total": 0,
        "billing_items": [
            {"item_code": 1002, "packs_needed": 1, "billed_qty": 10, "line_total": 68.5},
        ],
    }
    r = client.post("/confirm-sale", json=payload)
    body = r.json()
    assert body["success"] is False
    assert body["error"] == "Insufficient stock"


def test_confirm_sale_rejects_unknown_item(client):
    payload = {
        "patient_name": "Ghost",
        "age": 30,
        "grand_total": 10,
        "billing_items": [
            {"item_code": 424242, "packs_needed": 1, "billed_qty": 1, "line_total": 10},
        ],
    }
    r = client.post("/confirm-sale", json=payload)
    assert r.json()["success"] is False
