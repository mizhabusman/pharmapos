import streamlit as st
import json
import io
from PIL import Image
from datetime import datetime
import google.generativeai as genai

from preprocessor import load_inventory, create_search_index
from searcher import search_medicine
from billing_engine import calculate_pack_billing
from database_manager import validate_stock, deduct_stock, save_bill
from prompts import PHARMACIST_EXTRACTION
from image_processor import optimize_for_upload

# ================================================================
# PAGE CONFIG
# ================================================================
st.set_page_config(
    page_title="Pharmacy POS",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ================================================================
# DESIGN SYSTEM
# ================================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

.stApp                { background-color: #E2F5E9 !important; }
.block-container {
    background-color: #FFFFFF; border-radius: 16px;
    padding: 0rem 3rem 3rem 3rem !important;
    margin-top: 3rem; margin-bottom: 3rem;
    box-shadow: 0 10px 25px rgba(0,0,0,0.06);
    max-width: 95% !important; font-family: 'Inter', sans-serif;
}

/* ── Top bar ───────────────────────────────────────────── */
.custom-header-bar {
    background-color: #4ADE80; margin: 0 -3rem 2rem -3rem;
    padding: 1.2rem 3rem; border-top-left-radius: 16px;
    border-top-right-radius: 16px;
    display: flex; justify-content: space-between; align-items: center;
}
.brand-title { font-size: 1.8rem; font-weight: 800; color: #064E3B; letter-spacing: -0.5px; }

/* ── Invoice header ────────────────────────────────────── */
.invoice-header {
    display: flex; justify-content: space-between;
    align-items: flex-start; margin-bottom: 1.5rem;
}
.invoice-patient-name {
    font-size: 2rem; font-weight: 800; color: #111827; letter-spacing: -0.5px;
}
.invoice-meta { font-size: 0.85rem; color: #6B7280; margin-top: 4px; }
.invoice-badge {
    background: #F0FDF4; border: 1px solid #86EFAC;
    border-radius: 8px; padding: 10px 18px; text-align: right;
}
.invoice-badge-label { font-size: 0.7rem; color: #16A34A; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
.invoice-badge-total { font-size: 1.6rem; font-weight: 800; color: #15803D; }

/* ── Input label styling ───────────────────────────────── */
.stTextInput label p, .stNumberInput label p, .stSelectbox label p {
    font-size: 0.95rem !important; font-weight: 700 !important; color: #111827 !important;
}

/* ── Premium Ledger Header & Dividers ──────────────────── */
.ledger-header {
    display: flex; padding: 12px 16px;
    font-weight: 700; font-size: 0.75rem; color: #6B7280;
    text-transform: uppercase; letter-spacing: 0.05em;
    border-bottom: 2px solid #E5E7EB;
    margin-top: 1rem; margin-bottom: 0.5rem;
}
.ledger-divider {
    border-bottom: 1px solid #F3F4F6;
    margin: 16px 0;
}

/* ── Billing row read-only values ──────────────────────── */
.val-text {
    font-size: 0.95rem; font-weight: 500; color: #374151;
    padding-top: 9px; display: block;
}
.val-total {
    font-size: 1rem; font-weight: 700; color: #111827;
    text-align: right; padding-top: 9px; display: block;
}
.val-muted {
    font-size: 0.95rem; color: #9CA3AF;
    padding-top: 9px; display: block;
}

/* ── AI extraction badge ───────────────────────────────── */
.ai-badge {
    display: inline-flex; align-items: center; gap: 5px;
    background-color: #EEF2FF; color: #4F46E5;
    font-size: 0.78rem; font-weight: 600;
    padding: 3px 10px; border-radius: 6px;
    margin-bottom: 8px; border: 1px solid #C7D2FE;
}
.manual-badge {
    display: inline-flex; align-items: center; gap: 5px;
    background-color: #D1FAE5; color: #065F46;
    font-size: 0.78rem; font-weight: 600;
    padding: 3px 10px; border-radius: 6px;
    margin-bottom: 8px; border: 1px solid #6EE7B7;
}

/* ── Stock warning ─────────────────────────────────────── */
.stock-warning {
    background: #FEF2F2; border: 1px solid #FECACA;
    border-radius: 6px; padding: 6px 12px;
    color: #DC2626; font-size: 0.83rem; font-weight: 600;
    margin-top: 4px;
}

/* ── PRIMARY buttons (green) ───────────────────────────── */
.stButton > button[kind="primary"] {
    background-color: #10B981 !important; color: white !important;
    border-radius: 8px !important; font-weight: 600 !important;
    font-size: 0.95rem !important; border: none !important;
    box-shadow: 0 2px 4px rgba(16,185,129,0.2) !important;
    transition: all 0.15s ease;
}
.stButton > button[kind="primary"]:hover {
    background-color: #059669 !important;
    box-shadow: 0 4px 8px rgba(16,185,129,0.25) !important;
}
.stButton > button[kind="primary"]:disabled {
    background-color: #D1FAE5 !important; color: #6EE7B7 !important;
}

/* ── SECONDARY buttons (grey outline) ──────────────────── */
.stButton > button[kind="secondary"] {
    background-color: #FFFFFF !important; color: #374151 !important;
    border: 1.5px solid #D1D5DB !important; border-radius: 8px !important;
    font-weight: 500 !important; font-size: 0.9rem !important;
    box-shadow: none !important; transition: all 0.15s ease;
}
.stButton > button[kind="secondary"]:hover {
    background-color: #F9FAFB !important; border-color: #9CA3AF !important;
    color: #111827 !important;
}

/* ── TERTIARY buttons (Delete Row Icon) ────────────────── */
.stButton > button[kind="tertiary"] {
    background-color: transparent !important; color: #9CA3AF !important;
    border: none !important; box-shadow: none !important;
    font-size: 1.2rem !important; padding: 0 !important;
    transition: all 0.15s ease;
}
.stButton > button[kind="tertiary"]:hover {
    color: #EF4444 !important; transform: scale(1.1);
    background-color: transparent !important;
}

/* ── Number Input Overrides ────────────────────────────── */
button[data-testid="stepUp"]:focus, button[data-testid="stepDown"]:focus,
button[data-testid="stepUp"]:active, button[data-testid="stepDown"]:active {
    background-color: #10B981 !important;
    color: #FFFFFF !important;
    border-color: #10B981 !important;
    outline: none !important;
}
div[data-baseweb="input"]:focus-within {
    border-color: #10B981 !important;
}
div[data-testid="stNumberInput"] button {
    display: flex !important;
    opacity: 1 !important;
}

/* ── Grand total area ──────────────────────────────────── */
.grand-total-row {
    display: flex; justify-content: flex-end;
    align-items: center; gap: 16px;
    padding: 16px 0 8px;
    border-top: 2px solid #E5E7EB;
    margin-top: 8px;
}
.grand-label { font-size: 1.1rem; font-weight: 700; color: #374151; }
.grand-value { font-size: 1.8rem; font-weight: 800; color: #10B981; }

/* ── File uploader ─────────────────────────────────────── */
div[data-testid="stFileUploadDropzone"] {
    background-color: #F9FAFB !important;
    border: 2px dashed #D1D5DB !important;
    border-radius: 12px !important;
}

/* ── Tabs ──────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"]    { gap: 2rem; border-bottom: 2px solid #E5E7EB; }
.stTabs [data-baseweb="tab"]         { font-size: 1rem; font-weight: 600; padding-bottom: 1rem; color: #6B7280; }
.stTabs [aria-selected="true"]       { color: #064E3B !important; border-bottom: 2px solid #10B981 !important; }

/* ── Confirmed receipt ─────────────────────────────────── */
.receipt-wrap {
    background: linear-gradient(135deg, #F0FDF4, #ECFDF5);
    border: 1px solid #A7F3D0; border-radius: 12px;
    padding: 28px 32px; text-align: center; margin: 40px 0;
}
.receipt-icon  { font-size: 3rem; margin-bottom: 8px; }
.receipt-title { font-size: 1.5rem; font-weight: 800; color: #065F46; }
.receipt-bill  { font-size: 1rem; color: #047857; margin-top: 4px; }
.receipt-amt   { font-size: 2.5rem; font-weight: 800; color: #10B981; margin: 12px 0; }
</style>
""", unsafe_allow_html=True)

# ================================================================
# SESSION STATE & CACHING
# ================================================================
_DEFAULTS = {
    "cart": [], "pt_name": "", "pt_age": None, "confirmed_bill": None, "uploader_key": 0,
    "session_tokens": 0, "session_cost_inr": 0.0, "last_scan_metrics": None,
    "uploaded_image_bytes": None   # ← persists image across reruns
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

@st.cache_data(ttl=60, show_spinner=False)
def get_inventory():
    df = load_inventory()
    search_idx = create_search_index(df)
    all_item_codes = []
    item_code_to_name = {}
    for _, row in df.iterrows():
        code = int(row["item_code"])
        all_item_codes.append(code)
        item_code_to_name[code] = str(row["product_name"])
    return search_idx, df, all_item_codes, item_code_to_name

search_index, inventory_df, all_item_codes, item_code_to_name = get_inventory()

# ================================================================
# AI ENGINE
# ================================================================
def run_extraction(image_bytes: bytes, api_key: str) -> dict:
    """Sends compressed image to Gemini and calculates token usage metrics."""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        "gemini-2.5-flash",
        generation_config={"response_mime_type": "application/json"}
    )
    full_prompt = PHARMACIST_EXTRACTION + """
Return EXACTLY this JSON — no other text:
{"patient_name": "string", "age": 0, "medicines": [{"name": "string", "suggested_qty": 1}]}
"""
    picture = {"mime_type": "image/jpeg", "data": image_bytes}
    resp = model.generate_content([picture, full_prompt])

    metadata = resp.usage_metadata
    input_tokens  = metadata.prompt_token_count
    output_tokens = metadata.candidates_token_count
    total_tokens  = metadata.total_token_count

    INPUT_PRICE_PER_1M  = 0.075
    OUTPUT_PRICE_PER_1M = 0.30
    INR_CONVERSION_RATE = 83.5

    input_cost  = (input_tokens  / 1_000_000) * INPUT_PRICE_PER_1M
    output_cost = (output_tokens / 1_000_000) * OUTPUT_PRICE_PER_1M
    total_usd   = input_cost + output_cost
    total_inr   = total_usd * INR_CONVERSION_RATE

    return {
        "extracted_data": json.loads(resp.text),
        "metrics": {
            "input_tokens":  input_tokens,
            "output_tokens": output_tokens,
            "total_tokens":  total_tokens,
            "cost_usd":      total_usd,
            "cost_inr":      total_inr
        }
    }

# ================================================================
# BILLING GRID FRAGMENT
# ================================================================
@st.fragment
def render_billing_grid():

    col_info, col_badge = st.columns([3, 1.5], gap="large")

    with col_info:
        st.text_input("Patient Name", key="pt_name", placeholder="Walk-in Patient")
        st.number_input("Age", min_value=0, max_value=150, key="pt_age", placeholder="Enter age")

    badge_placeholder = col_badge.empty()

    st.divider()

    st.markdown("""
    <div class="ledger-header">
        <div style="flex:3.8;">Medicine Description</div>
        <div style="flex:0.85;">Unit(s) / Pack</div>
        <div style="flex:1.3;">Dispense Qty</div>
        <div style="flex:1.0;">Total Packs</div>
        <div style="flex:0.85; text-align:right;">Total</div>
        <div style="flex:0.3; text-align:center;"></div>
    </div>
    """, unsafe_allow_html=True)

    TABLE_COLS = [3.8, 0.85, 1.3, 1.0, 0.85, 0.3]

    grand_total         = 0.0
    final_billing_items = []
    cart_has_errors     = False

    for i, item in enumerate(st.session_state.cart):
        with st.container():
            is_custom = item.get("is_custom", False)
            if is_custom:
                st.markdown('<div class="manual-badge">✍️ Manually Added</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="ai-badge">✨ {item["extracted"]}</div>', unsafe_allow_html=True)

            row = st.columns(TABLE_COLS, gap="small", vertical_alignment="center")

            # ── Medicine cell ──
            with row[0]:
                if is_custom:
                    selected_code = st.selectbox(
                        "Search inventory", options=all_item_codes, index=None,
                        placeholder="Type to search all medicines...",
                        format_func=lambda x: item_code_to_name.get(x, "Unknown"),
                        key=f"med_manual_{i}", label_visibility="collapsed"
                    )
                else:
                    is_manual = st.session_state.get(f"manual_{i}", False)
                    med_col, btn_col = st.columns([4.2, 1.0], gap="small", vertical_alignment="center")

                    # ── Capture top_scores once for this row ──
                    top_scores = item.get("top_scores", {})

                    with med_col:
                        if not is_manual:
                            selected_code = st.selectbox(
                                "Medicine",
                                options=item["top_5_options"],
                                index=0,
                                # Score shown inline on the right of each option label
                                format_func=lambda x, ts=top_scores: (
                                    f"{item_code_to_name.get(x, 'Unknown')}  ·  {ts[x]}%"
                                    if x in ts else item_code_to_name.get(x, "Unknown")
                                ),
                                key=f"med_auto_{i}",
                                label_visibility="collapsed"
                            )
                        else:
                            selected_code = st.selectbox(
                                "Search inventory", options=all_item_codes, index=None,
                                placeholder="Search all medicines...",
                                format_func=lambda x: item_code_to_name.get(x, "Unknown"),
                                key=f"med_manual_{i}", label_visibility="collapsed"
                            )

                    with btn_col:
                        if not is_manual:
                            if st.button("Manual", key=f"btn_{i}", use_container_width=True, type="secondary"):
                                st.session_state[f"manual_{i}"] = True
                                st.rerun()
                        else:
                            if st.button("← Auto", key=f"btn_{i}", use_container_width=True, type="secondary"):
                                st.session_state[f"manual_{i}"] = False
                                st.rerun()

            # ── Handle unselected state ──
            if selected_code is None:
                with row[1]: st.markdown('<span class="val-muted">—</span>', unsafe_allow_html=True)
                with row[2]: st.markdown('<span class="val-muted" style="text-align:center; display:block; padding-top:9px;">—</span>', unsafe_allow_html=True)
                with row[3]: st.markdown('<span class="val-muted">—</span>', unsafe_allow_html=True)
                with row[4]: st.markdown('<span class="val-total" style="color:#9CA3AF;">₹0.00</span>', unsafe_allow_html=True)
                with row[5]:
                    if st.button("🗑️", key=f"del_null_{i}", type="tertiary", help="Remove item"):
                        st.session_state.cart.pop(i)
                        st.rerun()
                st.markdown('<div class="ledger-divider"></div>', unsafe_allow_html=True)
                continue

            # ── Look up selected medicine ──
            sel         = inventory_df[inventory_df["item_code"] == selected_code].iloc[0]
            pack_size   = int(sel["pack_size"])
            price_inr   = float(sel["price_inr"])
            avail_stock = int(sel["stock"])
            max_pills   = avail_stock * pack_size

            with row[1]:
                st.markdown(f'<span class="val-text">{pack_size} unit(s)</span>', unsafe_allow_html=True)

            with row[2]:
                qty_key = f"qty_{i}"
                if max_pills == 0:
                    st.session_state[qty_key] = 0
                    rx_qty = 0
                    st.number_input("Qty", min_value=0, max_value=0, step=1, key=qty_key, label_visibility="collapsed", disabled=True)
                    st.markdown('<div style="font-size:0.72rem; color:#EF4444; margin-top:2px; font-weight:600; line-height:1.2;">Out of stock</div>', unsafe_allow_html=True)
                    cart_has_errors = True
                else:
                    if qty_key not in st.session_state:
                        st.session_state[qty_key] = max(1, int(item.get("suggested_qty", 1)))

                    show_limit_alert = False
                    if st.session_state[qty_key] > max_pills:
                        st.session_state[qty_key] = max_pills
                        show_limit_alert = True

                    rx_qty = st.number_input("Qty", min_value=1, step=1, key=qty_key, label_visibility="collapsed")

                    if show_limit_alert:
                        st.markdown(f'<div style="font-size:0.72rem; color:#EF4444; margin-top:1.5px; font-weight:600; line-height:1;">Only {max_pills} available</div>', unsafe_allow_html=True)

            if max_pills == 0:
                billing = {"packs_needed": 0, "billed_qty": 0, "line_total": 0.0}
            else:
                billing = calculate_pack_billing(rx_qty=rx_qty, pack_size=pack_size, pack_price=price_inr)

            with row[3]:
                st.markdown(
                    f'<div style="line-height:1.3; padding-top:4px;">'
                    f'<div style="font-size:0.95rem; font-weight:600; color:#374151;">{billing["packs_needed"]} Pack(s)</div>'
                    f'<div style="font-size:0.75rem; color:#9CA3AF;">({billing["billed_qty"]} units total)</div>'
                    f'</div>', unsafe_allow_html=True
                )

            with row[4]:
                st.markdown(f'<span class="val-total">₹{billing["line_total"]:.2f}</span>', unsafe_allow_html=True)

            with row[5]:
                if st.button("🗑️", key=f"del_{i}", type="tertiary", help="Remove item"):
                    st.session_state.cart.pop(i)
                    st.rerun()

            grand_total += billing["line_total"]
            final_billing_items.append({
                "item_code": selected_code, "product_name": str(sel["product_name"]),
                "rx_qty": rx_qty, "pack_size": pack_size, "packs_needed": billing["packs_needed"],
                "billed_qty": billing["billed_qty"], "line_total": billing["line_total"]
            })

            st.markdown('<div class="ledger-divider"></div>', unsafe_allow_html=True)

    badge_placeholder.markdown(
        f"""<div class="invoice-badge">
            <div class="invoice-badge-label">Current Total</div>
            <div class="invoice-badge-total">₹{grand_total:.2f}</div>
            <div style="font-size:0.78rem;color:#047857;margin-top:2px;">
                💊 {len(st.session_state.cart)} item(s)</div>
        </div>""",
        unsafe_allow_html=True
    )

    st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
    if st.button("➕ Add Item", type="secondary"):
        st.session_state.cart.append({"extracted": "Manual Entry", "suggested_qty": 1, "is_custom": True, "top_5_options": []})
        st.rerun()

    st.markdown(
        f'<div class="grand-total-row">'
        f'<span class="grand-label">Grand Total</span>'
        f'<span class="grand-value">₹{grand_total:.2f}</span>'
        f'</div>', unsafe_allow_html=True
    )

    st.markdown("")

    confirm_label = "💳  Confirm Sale & Deduct Stock" if not cart_has_errors else "⚠️  Resolve Stock Issues Above"

    if st.button(confirm_label, use_container_width=True, type="primary", disabled=cart_has_errors):
        if not final_billing_items:
            st.warning("No items in bill.")
        else:
            with st.spinner("Processing transaction..."):
                issues = validate_stock(final_billing_items)
                if issues:
                    st.error("🚨 Transaction blocked — stock changed during session")
                else:
                    deduct_res = deduct_stock(final_billing_items)
                    if not deduct_res["success"]:
                        st.error(f"Deduction failed: {deduct_res['message']}")
                    else:
                        payload = {
                            "patient_name": st.session_state.pt_name or "Walk-in Patient",
                            "age":          st.session_state.pt_age or 0,
                            "grand_total":  round(grand_total, 2),
                            "billing_items": final_billing_items
                        }
                        save_res = save_bill(payload)
                        if save_res["success"]:
                            get_inventory.clear()
                            st.session_state.confirmed_bill = {
                                "bill_id": save_res["bill_id"], "grand_total": grand_total, "payload": payload
                            }
                            for k in list(st.session_state.keys()):
                                if k.startswith(("med_", "qty_", "pt_", "manual_")):
                                    del st.session_state[k]
                            st.session_state.cart = []
                            st.session_state.uploader_key += 1
                            st.rerun()

# ================================================================
# TOP BAR
# ================================================================
st.markdown("""
<div class="custom-header-bar">
    <div class="brand-title">💊 AI Powered Pharmacy POS</div>
    <iframe srcdoc="
        <!DOCTYPE html>
        <html>
        <head>
            <link href='https://fonts.googleapis.com/css2?family=Inter:wght@600;700;800&display=swap' rel='stylesheet'>
            <style>
                body {
                    margin: 0; padding: 0;
                    font-family: 'Inter', sans-serif;
                    background-color: #4ADE80;
                    text-align: right;
                    display: flex; flex-direction: column;
                    justify-content: center; height: 100vh; overflow: hidden;
                }
                .time { font-size: 1.35rem; font-weight: 800; color: #064E3B; letter-spacing: 0.5px; margin-bottom: 2px; }
                .date { font-size: 0.95rem; font-weight: 700; color: #065F46; }
            </style>
        </head>
        <body>
            <div class='time' id='time'></div>
            <div class='date' id='date'></div>
            <script>
                function update() {
                    const now = new Date();
                    document.getElementById('time').innerText = now.toLocaleTimeString('en-US', {hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true});
                    document.getElementById('date').innerText = now.toLocaleDateString('en-US', {weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'});
                }
                setInterval(update, 1000);
                update();
            </script>
        </body>
        </html>
    " width="300" height="60" style="border:none; overflow:hidden; background-color:transparent;" scrolling="no"></iframe>
</div>
""", unsafe_allow_html=True)

# ================================================================
# TABS
# ================================================================
tab1, tab2 = st.tabs(["🧾  Billing Terminal", "📦  Live Inventory"])

with tab2:
    st.markdown("### Real-Time Inventory")
    st.caption("Stock numbers update 60 seconds after each confirmed sale.")
    col_btn, _ = st.columns([1, 6])
    with col_btn:
        if st.button("🔄 Refresh", use_container_width=True, type="secondary"):
            get_inventory.clear()
            st.rerun()
    st.dataframe(
        inventory_df[["item_code", "product_name", "pack_size", "price_inr", "stock"]],
        use_container_width=True, height=600, hide_index=True
    )

with tab1:
    left, right = st.columns([1, 4], gap="large")

    # ── LEFT: Upload panel ──
    with left:
        st.markdown(
            "<div style='font-size:1rem; font-weight:700; color:#111827; margin-bottom:1rem;'>"
            "Prescription</div>", unsafe_allow_html=True
        )

        api_key = ""
        try:
            api_key = st.secrets["GEMINI_API_KEY"]
        except Exception:
            with st.expander("🔑 Setup API Key", expanded=True):
                api_key = st.text_input("Gemini API Key", type="password", label_visibility="collapsed", placeholder="Paste your key here")

        uploaded = st.file_uploader(
            "Upload Prescription", type=["jpg", "jpeg", "png"],
            label_visibility="collapsed", key=f"uploader_{st.session_state.uploader_key}"
        )

        # Save bytes the moment a file arrives — survives all reruns after that
        if uploaded:
            st.session_state.uploaded_image_bytes = uploaded.getvalue()

        # Display from session state, not from `uploaded` (which resets every rerun)
        if st.session_state.uploaded_image_bytes:
            image = Image.open(io.BytesIO(st.session_state.uploaded_image_bytes))
            st.image(image, use_container_width=True)
            st.markdown("")

            if st.button("🔍  Extract Data", use_container_width=True, type="primary"):
                if not api_key:
                    st.error("API Key required")
                else:
                    with st.spinner("Compressing image & AI reading..."):
                        try:
                            compressed_bytes = optimize_for_upload(
                                st.session_state.uploaded_image_bytes
                            )
                            response_data = run_extraction(compressed_bytes, api_key)
                            raw           = response_data["extracted_data"]

                            st.session_state.last_scan_metrics  = response_data["metrics"]
                            st.session_state.session_tokens    += response_data["metrics"]["total_tokens"]
                            st.session_state.session_cost_inr  += response_data["metrics"]["cost_inr"]

                            cart = []
                            for med in raw.get("medicines", []):
                                hits   = search_medicine(med["name"], inventory_df, limit=5)
                                top5   = []
                                scores = {}                          # ← item_code → confidence %
                                if hits:
                                    for h in hits:
                                        code = int(inventory_df.iloc[h[2]]["item_code"])
                                        top5.append(code)
                                        scores[code] = round(h[1])
                                else:
                                    top5 = [all_item_codes[0]]

                                cart.append({
                                    "extracted":     med["name"],
                                    "suggested_qty": max(1, int(med.get("suggested_qty", 1))),
                                    "top_5_options": top5,
                                    "top_scores":    scores,        # ← stored per cart item
                                })

                            # Clear stale widget keys from previous bill so
                            # selectboxes don't inherit old selections
                            for k in list(st.session_state.keys()):
                                if k.startswith(("med_", "qty_", "manual_")):
                                    del st.session_state[k]

                            st.session_state.cart           = cart
                            st.session_state.pt_name        = raw.get("patient_name", "")
                            st.session_state.pt_age         = int(raw.get("age")) if raw.get("age") else None
                            st.session_state.confirmed_bill = None
                            st.rerun()

                        except Exception as e:
                            st.error(f"Extraction failed: {e}")

        # ── Scan Analytics — compact ──
        if st.session_state.get("last_scan_metrics"):
            m = st.session_state.last_scan_metrics
            st.markdown(
                f"""<div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:8px;
                               padding:8px 12px;margin-top:8px;font-size:0.78rem;color:#374151;">
                    <div style="font-weight:700;color:#64748B;font-size:0.68rem;
                                text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px;">
                        📊 Scan Analytics
                    </div>
                    <div style="display:flex;justify-content:space-between;margin-bottom:3px;">
                        <span style="color:#6B7280;">This scan</span>
                        <span style="font-weight:600;">{m['total_tokens']:,} tok
                            &nbsp;·&nbsp;₹{m['cost_inr']:.4f}
                        </span>
                    </div>
                    <div style="display:flex;justify-content:space-between;
                                border-top:1px solid #E2E8F0;padding-top:4px;margin-top:2px;">
                        <span style="color:#6B7280;">Session</span>
                        <span style="font-weight:600;color:#059669;">
                            {st.session_state.session_tokens:,} tok
                            &nbsp;·&nbsp;₹{st.session_state.session_cost_inr:.4f}
                        </span>
                    </div>
                </div>""",
                unsafe_allow_html=True
            )

        if st.session_state.cart:
            st.markdown("")
            if st.button("Clear & Start Over", use_container_width=True, type="secondary"):
                for k in list(st.session_state.keys()):
                    if k.startswith(("med_", "qty_", "pt_", "manual_")):
                        del st.session_state[k]
                st.session_state.cart                 = []
                st.session_state.confirmed_bill       = None
                st.session_state.uploader_key        += 1
                st.session_state.last_scan_metrics    = None
                st.session_state.uploaded_image_bytes = None   # ← clear image
                st.rerun()

    # ── RIGHT: Billing panel ──
    with right:
        if st.session_state.confirmed_bill:
            bill = st.session_state.confirmed_bill
            st.markdown(f"""
            <div class="receipt-wrap">
                <div class="receipt-icon">✅</div>
                <div class="receipt-title">Sale Complete</div>
                <div class="receipt-bill">Receipt #{bill['bill_id']}</div>
                <div class="receipt-amt">₹{bill['grand_total']:.2f}</div>
            </div>
            """, unsafe_allow_html=True)

            rcpt_col1, rcpt_col2 = st.columns(2, gap="medium")
            with rcpt_col1:
                st.download_button(
                    label="📄  Download Invoice", data=json.dumps(bill["payload"], indent=4),
                    file_name=f"invoice_{bill['bill_id']}.json", mime="application/json",
                    use_container_width=True, type="primary"
                )
            with rcpt_col2:
                if st.button("⬅️  Start New Sale", use_container_width=True, type="secondary"):
                    for k in list(st.session_state.keys()):
                        if k.startswith(("med_", "qty_", "pt_", "manual_")):
                            del st.session_state[k]
                    st.session_state.cart                 = []
                    st.session_state.confirmed_bill       = None
                    st.session_state.uploader_key        += 1
                    st.session_state.last_scan_metrics    = None
                    st.session_state.uploaded_image_bytes = None   # ← clear image
                    st.rerun()
            st.stop()

        if not st.session_state.cart:
            st.markdown(
                "<div style='text-align:center;padding-top:80px;color:#9CA3AF;'>"
                "<div style='font-size:2.5rem;margin-bottom:12px;'>📋</div>"
                "<div style='font-size:1.1rem;font-weight:600;'>Ready for next patient</div>"
                "<div style='font-size:0.9rem;margin-top:6px;margin-bottom:20px;'>Upload a prescription on the left or start a walk-in sale.</div>"
                "</div>", unsafe_allow_html=True
            )
            _, col2, _ = st.columns([1, 1.2, 1])
            with col2:
                if st.button("🛒 Start Walk-in Sale", type="primary", use_container_width=True):
                    st.session_state.cart = [{"extracted": "Manual Entry", "suggested_qty": 1, "is_custom": True, "top_5_options": []}]
                    st.session_state.pt_name = ""
                    st.session_state.pt_age  = None
                    st.session_state.uploader_key     += 1
                    st.session_state.last_scan_metrics = None
                    st.rerun()
            st.stop()

        render_billing_grid()