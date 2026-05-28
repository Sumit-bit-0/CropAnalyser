import json
import joblib
import numpy as np
import torch
from models.lstm import PriceLSTM
from analysis.trends import get_price_trend
from config import LSTM_SEQUENCE_LEN, LSTM_FORECAST_LEN, MODELS_DIR

INPUT_SIZE  = 4
OUTPUT_SIZE = 2


def _load_arch_meta(safe_name: str) -> tuple[int, int]:
    """Return (hidden_size, seq_len) — from sidecar if present, else defaults."""
    meta_path = MODELS_DIR / f"{safe_name}_meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        return int(meta["hidden_size"]), int(meta["seq_len"])
    return 64, LSTM_SEQUENCE_LEN


def _month_features(period: str) -> tuple[float, float]:
    month = int(period.split("-")[1])
    angle = 2 * np.pi * (month - 1) / 12
    return float(np.sin(angle)), float(np.cos(angle))


def predict(state: str, commodity: str) -> list[dict]:
    safe_name   = f"{state}_{commodity}".replace(" ", "_").replace("/", "-")
    model_path  = MODELS_DIR / f"{safe_name}.pt"
    scaler_path = MODELS_DIR / f"{safe_name}_scaler.joblib"

    if not model_path.exists() or not scaler_path.exists():
        raise FileNotFoundError(f"No trained model for {state}/{commodity}. Train it first.")

    hidden_size, seq_len = _load_arch_meta(safe_name)

    scaler  = joblib.load(scaler_path)
    records = get_price_trend(state, commodity)
    if len(records) < seq_len:
        raise ValueError(f"Not enough history for {state}/{commodity}: {len(records)} records")

    prices = np.array([[r["farm_gate_price"], r["modal_price"]] for r in records], dtype=np.float32)
    months = np.array([_month_features(r["period"]) for r in records], dtype=np.float32)
    prices_scaled = scaler.transform(prices)
    inputs = np.concatenate([prices_scaled, months], axis=1)   # (N, 4)

    seq   = torch.tensor(inputs[-seq_len:]).unsqueeze(0)   # (1, seq_len, 4)
    model = PriceLSTM(input_size=INPUT_SIZE, hidden_size=hidden_size, num_layers=2,
                      forecast_len=LSTM_FORECAST_LEN, output_size=OUTPUT_SIZE)
    model.load_state_dict(torch.load(str(model_path), map_location="cpu"))
    model.eval()

    with torch.no_grad():
        pred_scaled = model(seq).squeeze(0).numpy()  # (forecast_len, 2)

    pred = scaler.inverse_transform(pred_scaled)

    last_record = records[-1]
    last_year   = int(last_record["period"].split("-")[0])
    last_month  = int(last_record["period"].split("-")[1])
    results = []
    for i in range(LSTM_FORECAST_LEN):
        m = last_month + i + 1
        y = last_year + (m - 1) // 12
        m = ((m - 1) % 12) + 1
        results.append({
            "period": f"{y}-{str(m).zfill(2)}",
            "farm_gate_price": round(float(pred[i, 0]), 2),
            "modal_price":     round(float(pred[i, 1]), 2),
            "is_forecast":     True
        })
    return results
