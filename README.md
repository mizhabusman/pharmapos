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

Run the test suite (from `backend/`):

```bash
pip install -r requirements-dev.txt   # first time only
pytest
```

Tests run against a throwaway seeded database — they never touch
`data/pharmacy_inventory.db`.

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env              # set VITE_API_URL if the API isn't on localhost:8000
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

## Deployment

The frontend is a static build and the backend is a standard ASGI app — they
can be hosted separately.

### Backend

1. Install deps and build the database on the host:
   ```bash
   pip install -r requirements.txt
   python scripts/db_setup.py
   ```
2. Set environment variables (in `backend/.env` or the host's env):
   - `GEMINI_API_KEY` — required.
   - `CORS_ORIGINS` — comma-separated list of your frontend origin(s), e.g.
     `https://pharmapos.example.com`. **Must be set**, or the browser will
     block requests from the deployed frontend.
3. Run the production server (no `--reload`; bind all interfaces; scale workers):
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2
   ```
   Put it behind a reverse proxy (nginx/Caddy) or your platform's HTTPS layer.

> Note: the SQLite DB (`data/pharmacy_inventory.db`) is file-based. For a
> single instance this is fine; for horizontal scaling, move to a networked
> database or ensure all workers share the same volume.

### Frontend

1. Point the build at the deployed API:
   ```bash
   echo "VITE_API_URL=https://api.pharmapos.example.com" > .env
   npm ci
   npm run build            # outputs static files to frontend/dist/
   ```
2. Serve `frontend/dist/` from any static host or CDN (Netlify, Vercel,
   S3+CloudFront, nginx, …). `VITE_API_URL` is baked in at build time, so
   rebuild if the API URL changes.
