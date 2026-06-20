from __future__ import annotations

import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st
from pydantic import BaseModel, Field


ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src" / "search_app"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from billing_engine import calculate_pack_billing
from config import DB_PATH
from preprocessor import create_search_index, load_inventory
from prompts import PHARMACIST_EXTRACTION
from searcher import search_medicine


OUTPUT_DIR = ROOT_DIR / "output"
OUTPUT_FILE = OUTPUT_DIR / "billing.json"
DB_FILE = ROOT_DIR / DB_PATH


class ExtractedMedication(BaseModel):
    name: str = Field(description="Medication name normalized for inventory matching.")
    suggested_qty: int = Field(default=1, description="Prescribed unit count. Use 1 if unknown.")


class PrescriptionSchema(BaseModel):
    patient_name: str = Field(default="Unknown", description="Patient name, or Unknown.")
    age: int = Field(default=0, description="Patient age, or 0.")
    medicines: list[ExtractedMedication] = Field(default_factory=list)


@dataclass(frozen=True)
class StockResult:
    ok: bool
    message: str


def initialise_state() -> None:
    defaults = {
        "prescription_data": None,
        "billing_payload": None,
        "manual_rows": "Aldactone Tab 25mg, 8",
        "last_transaction_at": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


@st.cache_data(show_spinner=False)
def get_inventory():
    inventory = load_inventory()
    return create_search_index(inventory)


def clear_inventory_cache() -> None:
    get_inventory.clear()


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_manual_medicines(text: str) -> list[dict[str, Any]]:
    medicines: list[dict[str, Any]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        name = line
        quantity = 1

        if "," in line:
            left, right = line.rsplit(",", 1)
            parsed_qty = safe_int(right.strip(), default=1)
            name = left.strip()
            quantity = max(1, parsed_qty)

        if name:
            medicines.append({"name": name, "suggested_qty": quantity})

    return medicines


def coerce_prescription_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, BaseModel):
        payload = payload.model_dump()

    if not isinstance(payload, dict):
        return {"patient_name": "Unknown", "age": 0, "medicines": []}

    medicines = []
    for med in payload.get("medicines", []) or []:
        if isinstance(med, BaseModel):
            med = med.model_dump()
        if not isinstance(med, dict):
            continue

        name = str(med.get("name", "")).strip()
        if not name:
            continue

        medicines.append(
            {
                "name": name,
                "suggested_qty": max(1, safe_int(med.get("suggested_qty"), default=1)),
            }
        )

    return {
        "patient_name": str(payload.get("patient_name") or "Unknown").strip() or "Unknown",
        "age": max(0, safe_int(payload.get("age"), default=0)),
        "medicines": medicines,
    }


def extract_with_gemini(uploaded_file, api_key: str) -> dict[str, Any]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    image_part = types.Part.from_bytes(
        data=uploaded_file.getvalue(),
        mime_type=uploaded_file.type,
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[image_part, PHARMACIST_EXTRACTION],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=PrescriptionSchema,
            temperature=0.1,
        ),
    )

    return coerce_prescription_payload(json.loads(response.text or "{}"))


def format_inventory_option(inventory, position: int) -> str:
    row = inventory.iloc[position]
    product = row.get("product_name", "Unknown item")
    pack_size = safe_int(row.get("pack_size"), default=1)
    pack_name = str(row.get("pack_name", "") or "").strip()
    stock = safe_int(row.get("stock"), default=0)
    price = float(row.get("price_inr", 0.0) or 0.0)
    pack_label = f"{pack_size}"
    if pack_name:
        pack_label = f"{pack_size} ({pack_name})"
    return f"{product} | Pack: {pack_label} | Stock: {stock} | INR {price:.2f}"


def deduct_stock_atomically(items: list[dict[str, Any]]) -> StockResult:
    if not items:
        return StockResult(False, "No billable medicines were selected.")

    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")

        for item in items:
            item_code = safe_int(item.get("item_code"), default=-1)
            packs_needed = safe_int(item.get("packs_needed"), default=0)
            if item_code < 0 or packs_needed <= 0:
                conn.rollback()
                return StockResult(False, "A billing line has an invalid item code or pack count.")

            cursor.execute(
                """
                SELECT CAST(stock AS INTEGER)
                FROM inventory
                WHERE item_code = ?
                """,
                (item_code,),
            )
            row = cursor.fetchone()
            if row is None:
                conn.rollback()
                return StockResult(False, f"Item code {item_code} no longer exists in inventory.")

            current_stock = safe_int(row[0], default=0)
            if current_stock < packs_needed:
                conn.rollback()
                return StockResult(
                    False,
                    f"Insufficient stock for {item.get('product_name', item_code)}. "
                    f"Available {current_stock}, needed {packs_needed}.",
                )

            cursor.execute(
                """
                UPDATE inventory
                SET stock = CAST(stock AS INTEGER) - ?
                WHERE item_code = ?
                """,
                (packs_needed, item_code),
            )

            if cursor.rowcount != 1:
                conn.rollback()
                return StockResult(False, f"Could not update item code {item_code}.")

        conn.commit()
        return StockResult(True, "Stock deducted successfully.")

    except sqlite3.Error as exc:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        return StockResult(False, f"Database transaction failed: {exc}")

    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def build_billing_line(raw_name: str, selected_row, rx_qty: int, confidence: float | None) -> dict[str, Any]:
    billing = calculate_pack_billing(
        rx_qty=rx_qty,
        pack_size=selected_row.get("pack_size", 1),
        pack_price=selected_row.get("price_inr", 0.0),
    )

    return {
        "extracted_text": raw_name,
        "item_code": safe_int(selected_row.get("item_code"), default=0),
        "product_name": str(selected_row.get("product_name", "")),
        "match_confidence": None if confidence is None else round(float(confidence), 1),
        "rx_qty": billing["rx_qty"],
        "pack_size": billing["pack_size"],
        "pack_price": round(float(selected_row.get("price_inr", 0.0) or 0.0), 2),
        "packs_needed": billing["packs_needed"],
        "billed_qty": billing["billed_qty"],
        "line_total": billing["line_total"],
    }


def render_sidebar() -> None:
    with st.sidebar:
        st.header("Prescription Input")

        api_key = st.text_input("Gemini API key", type="password")
        uploaded_file = st.file_uploader(
            "Upload prescription image",
            type=["jpg", "jpeg", "png", "webp"],
        )

        if uploaded_file is not None:
            st.image(uploaded_file, use_container_width=True)

        process_disabled = uploaded_file is None or not api_key.strip()
        if st.button("Extract From Image", type="primary", use_container_width=True, disabled=process_disabled):
            with st.spinner("Extracting prescription details..."):
                try:
                    st.session_state.prescription_data = extract_with_gemini(uploaded_file, api_key.strip())
                    st.session_state.billing_payload = None
                    st.rerun()
                except Exception as exc:
                    st.error(f"Gemini extraction failed: {exc}")

        if uploaded_file is not None and not api_key.strip():
            st.caption("Enter a Gemini API key to enable image extraction.")

        st.divider()
        st.subheader("Manual Entry")
        patient_name = st.text_input("Patient name", value="Unknown", key="manual_patient_name")
        patient_age = st.number_input("Age", min_value=0, max_value=130, value=0, step=1, key="manual_patient_age")
        st.text_area(
            "Medicines, one per line",
            key="manual_rows",
            height=140,
            placeholder="Aciloc Tab 150mg, 10",
        )

        if st.button("Use Manual Prescription", use_container_width=True):
            medicines = parse_manual_medicines(st.session_state.manual_rows)
            if not medicines:
                st.warning("Add at least one medicine line.")
            else:
                st.session_state.prescription_data = {
                    "patient_name": patient_name.strip() or "Unknown",
                    "age": int(patient_age),
                    "medicines": medicines,
                }
                st.session_state.billing_payload = None
                st.rerun()

        st.divider()
        if st.button("Reset", use_container_width=True):
            st.session_state.prescription_data = None
            st.session_state.billing_payload = None
            st.session_state.last_transaction_at = None
            st.rerun()


def render_empty_state(inventory) -> None:
    st.info("Upload a prescription image or use manual entry in the sidebar to begin.")
    st.metric("Inventory items loaded", f"{len(inventory):,}")
    with st.expander("Manual entry format"):
        st.write("Enter one medicine per line. Add a comma and quantity when known.")
        st.code("Aldactone Tab 25mg, 8\nAciloc Tab 150mg, 10", language="text")


def render_billing_app(inventory) -> None:
    prescription = coerce_prescription_payload(st.session_state.prescription_data)
    medicines = prescription.get("medicines", [])

    if not medicines:
        st.warning("No medicines were found in this prescription. Use manual entry to add medicines.")
        return

    patient_col, age_col, count_col = st.columns([2, 1, 1])
    with patient_col:
        patient_name = st.text_input("Patient name", value=prescription["patient_name"])
    with age_col:
        patient_age = st.number_input("Age", min_value=0, max_value=130, value=prescription["age"], step=1)
    with count_col:
        st.metric("Medicines", len(medicines))

    st.divider()

    header = st.columns([1.4, 3.3, 0.8, 1.1, 1.1, 1.1])
    header[0].markdown("**Extracted**")
    header[1].markdown("**Inventory Match**")
    header[2].markdown("**Rx Qty**")
    header[3].markdown("**Bill Qty**")
    header[4].markdown("**Stock**")
    header[5].markdown("**Total**")

    billing_items: list[dict[str, Any]] = []
    grand_total = 0.0
    checkout_disabled = inventory.empty

    for index, med in enumerate(medicines):
        raw_name = str(med.get("name", "")).strip()
        suggested_qty = max(1, safe_int(med.get("suggested_qty"), default=1))
        matches = search_medicine(raw_name, inventory) if not inventory.empty else []
        match_positions = [match[2] for match in matches]
        confidence_by_position = {match[2]: match[1] for match in matches}

        if not match_positions and not inventory.empty:
            match_positions = list(range(min(50, len(inventory))))

        cols = st.columns([1.4, 3.3, 0.8, 1.1, 1.1, 1.1])

        with cols[0]:
            st.code(raw_name or "Unknown", language=None)
            if matches:
                st.caption(f"Best match {matches[0][1]:.1f}%")
            else:
                st.caption("Manual review required")

        with cols[1]:
            if inventory.empty:
                st.error("Inventory database is empty or unavailable.")
                continue

            selected_position = st.selectbox(
                f"Match for {raw_name or index}",
                options=match_positions,
                format_func=lambda pos: format_inventory_option(inventory, pos),
                label_visibility="collapsed",
                key=f"match_{index}",
            )
            selected_row = inventory.iloc[selected_position]

        with cols[2]:
            rx_qty = st.number_input(
                f"Quantity for {raw_name or index}",
                min_value=1,
                value=suggested_qty,
                step=1,
                label_visibility="collapsed",
                key=f"qty_{index}",
            )

        line = build_billing_line(
            raw_name=raw_name,
            selected_row=selected_row,
            rx_qty=rx_qty,
            confidence=confidence_by_position.get(selected_position),
        )

        available_stock = safe_int(selected_row.get("stock"), default=0)
        enough_stock = available_stock >= line["packs_needed"]
        if not enough_stock:
            checkout_disabled = True

        with cols[3]:
            st.markdown(f"**{line['billed_qty']}**")
            st.caption(f"{line['packs_needed']} pack(s)")

        with cols[4]:
            st.markdown(f"**{available_stock}**")
            if enough_stock:
                st.caption("Available")
            else:
                st.error("Low stock")

        with cols[5]:
            st.markdown(f"**INR {line['line_total']:.2f}**")

        billing_items.append(line)
        grand_total += line["line_total"]

    st.divider()

    left, right = st.columns([2, 1])
    with left:
        if checkout_disabled:
            st.warning("Checkout is blocked until every selected item has enough stock.")
        elif st.session_state.last_transaction_at:
            st.success(f"Last transaction completed at {st.session_state.last_transaction_at}.")

        if st.session_state.billing_payload:
            st.download_button(
                "Download billing.json",
                data=st.session_state.billing_payload,
                file_name="billing.json",
                mime="application/json",
            )
            with st.expander("Billing JSON"):
                st.code(st.session_state.billing_payload, language="json")

    with right:
        st.metric("Grand total", f"INR {grand_total:.2f}")
        if st.button(
            "Confirm and Deduct Stock",
            type="primary",
            use_container_width=True,
            disabled=checkout_disabled or not billing_items,
        ):
            payload = {
                "patient_name": patient_name.strip() or "Unknown",
                "age": int(patient_age),
                "billing_items": billing_items,
                "grand_total": round(grand_total, 2),
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }

            result = deduct_stock_atomically(billing_items)
            if not result.ok:
                st.error(result.message)
                return

            OUTPUT_DIR.mkdir(exist_ok=True)
            st.session_state.billing_payload = json.dumps(payload, indent=2)
            OUTPUT_FILE.write_text(st.session_state.billing_payload, encoding="utf-8")
            st.session_state.last_transaction_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            clear_inventory_cache()
            st.success(result.message)
            st.rerun()


def main() -> None:
    st.set_page_config(page_title="Pharmacy Prescription POS", page_icon="Rx", layout="wide")
    initialise_state()

    st.markdown(
        """
        <style>
        .stApp { background: #f7f8fb; }
        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 0.75rem 1rem;
        }
        .stCodeBlock pre {
            border-radius: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    render_sidebar()

    st.title("Pharmacy Prescription POS")
    st.caption("Extract, verify, bill by full packs, and deduct stock from the local inventory database.")

    inventory = get_inventory()
    if inventory.empty:
        st.error(f"No inventory rows could be loaded from {DB_FILE}.")
    elif not DB_FILE.exists():
        st.error(f"Database file not found: {DB_FILE}")

    if st.session_state.prescription_data is None:
        render_empty_state(inventory)
    else:
        render_billing_app(inventory)


if __name__ == "__main__":
    main()
