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
