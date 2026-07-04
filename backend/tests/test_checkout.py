"""Unit tests for authoritative bill construction (server-side pricing)."""

from app.services.checkout import build_authoritative_bill


def test_recomputes_from_db_and_ignores_client_prices(db_path):
    # Client lies about price and billed_qty; server must override both.
    items, grand_total, errors = build_authoritative_bill([
        {"item_code": 1001, "packs_needed": 1, "billed_qty": 999, "line_total": 0.01},
    ])
    assert errors == []
    assert len(items) == 1
    assert items[0]["line_total"] == 150.00        # real price, not 0.01
    assert items[0]["billed_qty"] == 15            # 1 pack * 15 units, not 999
    assert grand_total == 150.00


def test_grand_total_sums_multiple_lines(db_path):
    items, grand_total, errors = build_authoritative_bill([
        {"item_code": 1001, "packs_needed": 2},    # 2 * 150.00 = 300.00
        {"item_code": 1003, "packs_needed": 1},    # 1 *  30.00 =  30.00
    ])
    assert errors == []
    assert grand_total == 330.00


def test_unknown_item_is_rejected(db_path):
    items, grand_total, errors = build_authoritative_bill([
        {"item_code": 999999, "packs_needed": 1},
    ])
    assert items == []
    assert errors and errors[0]["item_code"] == 999999


def test_invalid_quantity_is_rejected(db_path):
    items, _, errors = build_authoritative_bill([
        {"item_code": 1001, "packs_needed": 0},
    ])
    assert items == []
    assert errors and "quantity" in errors[0]["error"].lower()
