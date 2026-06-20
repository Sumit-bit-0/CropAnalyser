import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
DB_PATH = DATA_PROCESSED / "agri.db"
MODELS_DIR = ROOT / "saved_models"

# Load env (DATABASE_URL etc.) from the project-root .env if present.
load_dotenv(ROOT / ".env")

# Primary database connection (SQLAlchemy URL). Defaults to the legacy local
# SQLite file so the app still works if no .env is configured.
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

LSTM_SEQUENCE_LEN = 12
LSTM_FORECAST_LEN = 6

# LSTM price-forecast models (~411MB) are too big to ship in the image, so they
# live in a separate public repo and are lazily fetched per (state, commodity) on
# demand. Override with FORECAST_MODELS_BASE_URL if the host changes.
FORECAST_MODELS_BASE_URL = os.getenv(
    "FORECAST_MODELS_BASE_URL",
    "https://raw.githubusercontent.com/Sumit-bit-0/agri-forecast-models/main",
)

# Allowed browser origins for CORS. The known dev + production hosts are always
# allowed so the app never breaks on a mistyped env var; any extra origins in
# CORS_ORIGINS (comma-separated) are unioned in. Each entry is stripped so a
# stray space/newline in the env value can't silently disable an origin.
_BAKED_ORIGINS = ["http://localhost:5173", "https://crop-analyser.vercel.app"]
_env_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
# Drop duplicates while preserving order. If "*" is supplied, honor it alone.
CORS_ORIGINS = ["*"] if "*" in _env_origins else list(dict.fromkeys(_BAKED_ORIGINS + _env_origins))
# Also allow this project's Vercel preview deployments (crop-analyser-<hash>.vercel.app).
CORS_ORIGIN_REGEX = os.getenv("CORS_ORIGIN_REGEX", r"https://crop-analyser-[a-z0-9-]+\.vercel\.app")


def init_dirs() -> None:
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
