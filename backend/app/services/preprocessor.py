import pandas as pd
from app.services.database_manager import fetch_raw_inventory

def load_inventory():

    df = fetch_raw_inventory()
    if df.empty:
        return pd.DataFrame(columns=[
            "item_code", "product_name", "price_inr", 
            "pack_size", "pack_name", "stock"
        ])

    # ======================================================
    # STANDARDIZE COLUMN NAMES
    # ======================================================

    df = df.rename(columns={
        "item_name": "product_name",
        "mrp":       "price_inr",
        "units_pack": "pack_size"
    })
    df = df.drop(columns=["slno"], errors="ignore")

    # ======================================================
    # REQUIRED FIELDS
    # ======================================================

    df = df.dropna(
        subset=[
            "item_code",
            "product_name"
        ]
    )

    # ======================================================
    # PRODUCT NAME CLEANUP
    # ======================================================

    df["product_name"] = (
        df["product_name"]
        .astype(str)
        .str.strip()
    )

    # ======================================================
    # ITEM CODE CLEANUP
    # ======================================================

    df["item_code"] = pd.to_numeric(
        df["item_code"],
        errors="coerce"
    )

    df = df.dropna(subset=["item_code"])

    df["item_code"] = (
        df["item_code"]
        .astype(int)
    )

    # ======================================================
    # PRICE CLEANUP
    # ======================================================

    df["price_inr"] = (
        pd.to_numeric(
            df["price_inr"],
            errors="coerce"
        )
        .fillna(0.0)
    )

    # ======================================================
    # PACK SIZE CLEANUP
    # ======================================================

    df["pack_size"] = (
        pd.to_numeric(
            df["pack_size"],
            errors="coerce"
        )
        .fillna(1)
    )

    df["pack_size"] = (
        df["pack_size"]
        .clip(lower=1)
        .astype(int)
    )

    df["stock"] = (
        pd.to_numeric(
            df["stock"],
            errors="coerce"
        )
        .fillna(0)
        .clip(lower=0)
        .astype(int)
    )
    
    return df

def create_search_index(inventory):
    if inventory.empty:
        inventory["search_index"] = ""
        inventory.attrs["search_list"] = []
        return inventory

    inventory["search_index"] = (
        inventory["product_name"].fillna("") + " " +
        inventory.get("pack_name", pd.Series("", index=inventory.index)).fillna("") 
    ).str.lower().str.strip()

    inventory.attrs["search_list"] = inventory["search_index"].tolist()
    return inventory