import joblib
import numpy as np
import torch
from models.lstm import PriceLSTM
from analysis.trends import get_price_trend
from config import LSTM_SEQUENCE_LEN, LSTM_FORECAST_LEN, MODELS_DIR


def predict(state: str, commodity: str) -> list[dict]:
    safe_name   = f"{state}_{commodity}".replace(" ", "_").replace("/", "-")
    model_path  = MODELS_DIR / f"{safe_name}.pt"
    scaler_path = MODELS_DIR / f"{safe_name}_scaler.joblib"

    if not model_path.exists() or not scaler_path.exists():
        raise FileNotFoundError(f"No trained model for {state}/{commodity}. Train it first.")

    scaler = joblib.load(scaler_path)

    records     = get_price_trend(state, commodity)
    data        = np.array([[r["farm_gate_price"], r["modal_price"]] for r in records], dtype=np.float32)
    data_scaled = scaler.transform(data)

    seq   = torch.tensor(data_scaled[-LSTM_SEQUENCE_LEN:]).unsqueeze(0)  # (1, seq_len, 2)
    model = PriceLSTM(input_size=2, hidden_size=64, num_layers=2, forecast_len=LSTM_FORECAST_LEN)
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
