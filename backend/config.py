from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
DB_PATH = DATA_PROCESSED / "agri.db"
MODELS_DIR = ROOT / "saved_models"

DATA_RAW.mkdir(parents=True, exist_ok=True)
DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

LSTM_SEQUENCE_LEN = 12   # months of history as input
LSTM_FORECAST_LEN = 6    # months to predict
CORS_ORIGINS = ["http://localhost:5173", "https://your-vercel-app.vercel.app"]
