# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

PharmaPOS — a prescription-to-billing point-of-sale app. Upload a prescription
image → Gemini OCR extracts patient + medicines → RapidFuzz matches drugs to
inventory → pack-based billing → confirm sale against live SQLite stock.

## Layout

- `backend/app/main.py` — FastAPI app factory (`create_app`); builds the
  in-memory search index once at startup into `app.state.inventory`.
- `backend/app/core/config.py` — all paths, secrets, and tunable constants.
  Nothing else should hardcode paths or pricing.
- `backend/app/routers/` — one module per endpoint group (`health`, `search`,
  `extraction`, `billing`, `sales`). Add new endpoints here as routers.
- `backend/app/schemas/` — Pydantic request/response models.
- `backend/app/services/` — business logic, framework-agnostic:
  `searcher` (fuzzy search), `billing_engine` (pack math), `gemini_extractor`
  (OCR), `image_processor` (Pillow compression), `database_manager` (SQLite
  stock + bills), `preprocessor` (inventory load + index), `prompts`.
- `backend/scripts/db_setup.py` — rebuild `data/pharmacy_inventory.db` from
  `data/real_database.csv`.
- `frontend/src/App.jsx` — the entire single-page UI (Tailwind).

## Conventions

- **Run the backend from `backend/`**: `uvicorn app.main:app --reload`.
  Imports are absolute from the `app` package (e.g. `from app.services.x`),
  which resolves because uvicorn adds the launch dir to `sys.path`.
- The SQLite DB lives at `data/pharmacy_inventory.db` and is **generated**
  (gitignored). Regenerate with `python backend/scripts/db_setup.py`.
- Routers read the shared inventory index via `request.app.state.inventory`,
  not a module global.
- Secrets and tunables come from `backend/.env` via `core/config.py` — do not
  reintroduce hardcoded API keys, prices, or CORS origins.

## Commands

```bash
# Backend (from backend/)
uvicorn app.main:app --reload
python scripts/db_setup.py
pytest                              # tests use an isolated temp DB (see tests/conftest.py)

# Frontend (from frontend/)
npm run dev
npm run build
npm run lint
```

## Known gaps (prototype → production)

No authentication yet; no DB migration tooling; `google.generativeai` is
deprecated (migrate to `google-genai`).

Done: `confirm-sale` now recomputes prices server-side (see checkout.py);
pytest suite covers billing, search, checkout, and the API.
