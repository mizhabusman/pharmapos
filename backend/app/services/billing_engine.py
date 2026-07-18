def calculate_pack_billing(
    rx_qty,
    pack_size,
    pack_price
):
    """
    Convert doctor's prescribed quantity into
    billable pharmacy quantities.

    Example:
        rx_qty     = 11
        pack_size  = 10
        pack_price = 68.52

    Result:
        packs_needed = 2
        billed_qty   = 20
        line_total   = 137.04
    """

    # ==========================================
    # SAFETY CHECKS
    # ==========================================

    try:
        rx_qty = int(rx_qty)
    except (TypeError, ValueError):
        rx_qty = 1

    try:
        pack_size = int(pack_size)
    except (TypeError, ValueError):
        pack_size = 1

    try:
        pack_price = float(pack_price)
    except (TypeError, ValueError):
        pack_price = 0.0

    # Never allow invalid values

    rx_qty = max(1, rx_qty)

    pack_size = max(1, pack_size)

    pack_price = max(0.0, pack_price)

    # ==========================================
    # PACK CALCULATION
    # ==========================================

    # Integer ceiling division — avoids the float conversion that overflows
    # (OverflowError) for very large rx_qty.
    packs_needed = -(-rx_qty // pack_size)

    billed_qty = (
        packs_needed * pack_size
    )

    # ==========================================
    # BILLING CALCULATION
    # ==========================================

    line_total = round(
        packs_needed * pack_price,
        2
    )

    # ==========================================
    # RESULT
    # ==========================================

    return {
        "rx_qty": rx_qty,
        "pack_size": pack_size,
        "packs_needed": packs_needed,
        "billed_qty": billed_qty,
        "line_total": line_total
    }   