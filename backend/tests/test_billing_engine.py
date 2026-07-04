"""Unit tests for the pack-based billing math (no DB required)."""

from app.services.billing_engine import calculate_pack_billing


def test_rounds_up_to_whole_packs():
    # 11 units, pack of 10 -> 2 packs, 20 billed units
    result = calculate_pack_billing(rx_qty=11, pack_size=10, pack_price=68.52)
    assert result["packs_needed"] == 2
    assert result["billed_qty"] == 20
    assert result["line_total"] == round(2 * 68.52, 2)


def test_exact_multiple_needs_no_extra_pack():
    result = calculate_pack_billing(rx_qty=30, pack_size=15, pack_price=150.0)
    assert result["packs_needed"] == 2
    assert result["billed_qty"] == 30
    assert result["line_total"] == 300.0


def test_single_unit_needs_one_pack():
    result = calculate_pack_billing(rx_qty=1, pack_size=10, pack_price=30.0)
    assert result["packs_needed"] == 1
    assert result["billed_qty"] == 10


def test_invalid_inputs_are_coerced_to_safe_minimums():
    result = calculate_pack_billing(rx_qty="bad", pack_size=0, pack_price="oops")
    assert result["rx_qty"] == 1
    assert result["pack_size"] == 1
    assert result["packs_needed"] == 1
    assert result["line_total"] == 0.0
