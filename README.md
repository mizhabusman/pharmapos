# PharmaPOS — Prescription Intelligence POS

Turn a photo of a handwritten prescription into a priced pharmacy bill. Upload
an image, let Gemini OCR extract the patient details and medicines (with
quantities calculated from dosage frequency × duration), fuzzy-match each drug
against the pharmacy inventory, compute pack-based billing, and confirm the sale
against live stock.

## Tech stack

| Layer     | Tech                                                        |
|-----------|-------------------------------------------------------------|
| Backend   | FastAPI, Uvicorn, Pydantic                                  |
| AI / OCR  | Google Gemini (`gemini-2.5-flash`)                          |
| Search    | RapidFuzz fuzzy matching                                    |
| Data      | SQLite (`data/pharmacy_inventory.db`), pandas               |
| Frontend  | React 19, Vite, Tailwind CSS v4                             |

## Project structure

```
Prescription_Project_ai/
├── data/                         # Source CSV + generated SQLite DB
│   ├── real_database.csv
│   ├── sample_inventory.csv
│   └── pharmacy_inventory.db      # generated (gitignored)
├── backend/
│   ├── requirements.txt
│   ├── .env                       # secrets (gitignored) — see .env.example
│   ├── .env.example
│   ├── app/
│   │   ├── main.py                # FastAPI app factory
│   │   ├── core/config.py         # paths, secrets, settings
│   │   ├── schemas/               # Pydantic request models
│   │   ├── routers/               # one module per endpoint group
│   │   └── services/              # business logic (search, billing, OCR, db)
│   └── scripts/
│       └── db_setup.py            # rebuild the DB from CSV
└── frontend/                      # React + Vite + Tailwind SPA
```

## Getting started

### 1. Backend

```bash
cd backend
python -m venv ../.venv           # or reuse the existing .venv
../.venv/Scripts/activate         # Windows;  source ../.venv/bin/activate on macOS/Linux
pip install -r requirements.txt

cp .env.example .env              # then add your GEMINI_API_KEY
```

Build the database from the source CSV (first run only, or to reset):

```bash
python scripts/db_setup.py        # run from the backend/ directory
```

Start the API (run from `backend/`):

```bash
uvicorn app.main:app --reload
```

The API serves on `http://localhost:8000` (interactive docs at `/docs`).

### 2. Frontend

```bash
cd frontend
npm install
npm run dev                       # serves on http://localhost:5173
```

## API endpoints

| Method | Path            | Purpose                                            |
|--------|-----------------|----------------------------------------------------|
| GET    | `/`             | Health check                                       |
| POST   | `/extract`      | Prescription image → patient + medicines (Gemini)  |
| GET    | `/search`       | Fuzzy medicine search against inventory            |
| GET    | `/billing`      | Pack-based billing for an item + prescribed qty    |
| POST   | `/confirm-sale` | Validate stock, deduct inventory, persist the bill |

## Configuration

All settings live in `backend/app/core/config.py` and can be overridden via
environment variables in `backend/.env` (see `backend/.env.example`):
`GEMINI_API_KEY`, `GEMINI_MODEL`, Gemini pricing constants, `INR_CONVERSION_RATE`,
and `CORS_ORIGINS`.
