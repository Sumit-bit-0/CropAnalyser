# Agri Market Access Analyser — Claude Code Instructions

## What This Is
India farm-to-retail price gap dashboard. 5 pages: State Map, Crop Analyser, Price Trend,
Revenue Loss Estimator, LSTM Price Forecast. Dual-purpose: DA CV + PM CV for Sumit.

**Project root:** `E:\agri-market-analyser` (moved from C: on 2026-05-29).
**External datasets:** `E:\DataSETAgri` (Agmarknet prices, Crop_recommendation.csv, crop production/yield, FAOSTAT, weather).

## Stack
| Layer | Technology |
|---|---|
| Backend API | Python + FastAPI |
| ML / Forecasting | PyTorch (LSTM), scikit-learn |
| Database | PostgreSQL 16 via Docker (`DATABASE_URL` in `.env`); legacy SQLite `data/processed/agri.db` kept as fallback |
| Frontend | React + Vite + Tailwind + Leaflet + Recharts |
| Deploy | Render (backend) + Vercel (frontend) |

## Project Structure
```
agri-market-analyser/
├── backend/
│   ├── main.py         — FastAPI entry point
│   ├── api/            — route handlers
│   ├── models/         — LSTM training scripts (train_all.py)
│   ├── analysis/       — data analysis modules
│   ├── database.py     — SQLite connection
│   ├── config.py       — env/config
│   ├── tests/          — 29 backend tests (all passing)
│   └── venv/           — Python 3.10.11 virtualenv
├── frontend/
│   ├── src/            — React components
│   └── vite.config.js
├── data/               — raw + processed datasets
├── saved_models/       — trained LSTM .pt files (currently empty)
└── policy-brief/       — PM CV artifact
```

## Running the Project
```bash
# Database (PostgreSQL via Docker) — start first
docker compose up -d          # from repo root; Postgres on localhost:5432
# Re-migrate from SQLite if ever needed:
#   cd backend && venv\Scripts\python.exe -m data.migrate_to_pg

# Backend
cd backend
venv\Scripts\python.exe -m uvicorn main:app --reload

# Frontend
cd frontend
npm run dev

# Run tests (asyncio plugin off — see note below)
cd backend
venv\Scripts\python.exe -m pytest tests -p no:asyncio -q

# Train LSTM models (GPU preferred — RTX 3060)
cd backend
venv\Scripts\python.exe models\train_all.py
```

## GPU Rule
ALL model training must use the NVIDIA RTX 3060 GPU via CUDA — never CPU.
venv has CUDA torch **2.11.0+cu128** (verified: `torch.cuda.is_available()` → True, RTX 3060 Laptop GPU).
Reinstall command if the venv is ever rebuilt:
```bash
venv\Scripts\python.exe -m pip install torch==2.11.0 torchvision==0.26.0 torchaudio==2.11.0 --index-url https://download.pytorch.org/whl/cu128
```
Always verify with `torch.cuda.is_available()` before starting a training run.

## Current Status
- Implementation complete (Tasks 1–14 done)
- 29/29 backend tests passing
- Frontend running
- `saved_models/` is empty — LSTM training not yet done
- Remaining: LSTM training (Task 15) → deploy backend to Render (16) → deploy frontend to Vercel (17)

## Key Rules for Claude

### 1. Subagent Delegation
Delegate to subagents for any exploration spanning more than 3 files:
- Reading how an existing API route works before modifying it
- Researching data pipeline or model architecture
- Running test audits or schema checks

Keep the main context for writing and editing code only.

### 2. GPU Training
Never write CPU-only training code. Always:
- Set `device = torch.device("cuda" if torch.cuda.is_available() else "cpu")`
- Move model and tensors to device
- Print which device is active at training start
- Warn explicitly if falling back to CPU

### 3. Data Sensitivity
- `prices` is ~27.6M rows — never SELECT it whole; query via Postgres (`database.query`). Legacy SQLite `agri.db` (2 GB) is read-only fallback.
- `kaggle.json` does not exist here — data is already loaded

### 4. Tests
Run `pytest tests/ -v` before declaring any backend change complete.
Never break the 29 passing tests.

### 5. CV Artifacts
This project has two audiences:
- **DA CV:** dashboards, LSTM forecasting, data pipeline
- **PM CV:** charter, WBS, risk register in `policy-brief/` (Notion + Trello)
Keep both angles in mind when adding features or writing docs.
