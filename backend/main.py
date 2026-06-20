from fastapi import FastAPI
from app.services.database_manager import fetch_raw_inventory

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "PharmaPOS backend is alive"}

@app.get("/test-db")
def test_db():
    df = fetch_raw_inventory()
    return {
        "rows": len(df),
        "columns": list(df.columns)
    }