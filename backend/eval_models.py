import json
import numpy as np
import torch
import joblib
from sklearn.metrics import mean_absolute_error, r2_score
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

STATES = ["Gujarat", "Maharashtra", "Nct Of Delhi", "Pondicherry", "Punjab"]
COMMODITIES = ["Wheat", "Tomato", "Soyabean", "Sesamum (Sesame,Gingelly,Til)", "Rice"]

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def month_features(period: str) -> tuple[float, float]:
    month = int(period.split("-")[1])
    angle = 2 * np.pi * (month - 1) / 12
    return float(np.sin(angle)), float(np.cos(angle))


results = []

for state in STATES:
    for commodity in COMMODITIES:
        safe_name = f"{state}_{commodity}".replace(" ", "_").replace("/", "-")
        model_path  = MODELS_DIR / f"{safe_name}.pt"
        scaler_path = MODELS_DIR / f"{safe_name}_scaler.joblib"

        if not model_path.exists():
            results.append((state, commodity, None, None, None, None, "no model"))
            continue

        hidden_size, seq_len = _load_arch_meta(safe_name)

        records = get_price_trend(state, commodity)
        if len(records) < seq_len + LSTM_FORECAST_LEN + 5:
            results.append((state, commodity, None, None, None, None, "insufficient data"))
            continue

        prices = np.array([[r["farm_gate_price"], r["modal_price"]] for r in records], dtype=np.float32)
        months = np.array([month_features(r["period"]) for r in records], dtype=np.float32)

        scaler = joblib.load(scaler_path)
        prices_scaled = scaler.transform(prices)
        inputs  = np.concatenate([prices_scaled, months], axis=1)   # (N, 4)
        targets = prices_scaled                                     # (N, 2)

        X, y = [], []
        for i in range(len(inputs) - seq_len - LSTM_FORECAST_LEN):
            X.append(inputs[i:i + seq_len])
            y.append(targets[i + seq_len:i + seq_len + LSTM_FORECAST_LEN])
        X, y = np.array(X), np.array(y)

        # Same split as trainer: last 15% is test
        n_total = len(X)
        n_val   = int(n_total * 0.85)
        X_test  = torch.tensor(X[n_val:]).to(device)
        y_test  = y[n_val:]   # numpy, for metrics

        if len(X_test) == 0:
            n_val  = int(n_total * 0.80)
            X_test = torch.tensor(X[n_val:]).to(device)
            y_test = y[n_val:]

        model = PriceLSTM(input_size=INPUT_SIZE, hidden_size=hidden_size, num_layers=2,
                          forecast_len=LSTM_FORECAST_LEN, output_size=OUTPUT_SIZE).to(device)
        model.load_state_dict(torch.load(model_path, map_location=device))
        model.eval()

        with torch.no_grad():
            preds_scaled = model(X_test).cpu().numpy()   # (N, forecast_len, 2)

        y_flat    = y_test.reshape(-1, 2)
        pred_flat = preds_scaled.reshape(-1, 2)
        y_orig    = scaler.inverse_transform(y_flat)
        pred_orig = scaler.inverse_transform(pred_flat)

        mae  = float(mean_absolute_error(y_orig, pred_orig))
        mape = float(np.mean(np.abs((y_orig - pred_orig) / np.where(y_orig == 0, 1, y_orig))) * 100)
        avg_price = float(np.mean(y_orig))
        r2   = float(r2_score(y_orig, pred_orig))

        results.append((state, commodity, mae, mape, avg_price, r2, "ok"))


print(f"\n{'State':<20} {'Commodity':<32} {'MAE (Rs)':>10} {'MAPE %':>8} {'Avg Rs':>9} {'R2':>7} {'Status'}")
print("-" * 95)

ok_results = [r for r in results if r[-1] == "ok"]

for state, commodity, mae, mape, avg_price, r2, status in results:  # noqa
    if status == "ok":
        # MAPE-based grading (more meaningful than R2 here)
        flag = "GOOD" if mape < 10 else ("OK" if mape < 20 else "POOR")
        print(f"{state:<20} {commodity:<32} {mae:>10.2f} {mape:>7.1f}% {avg_price:>9.0f} {r2:>7.3f}  {flag}")
    else:
        print(f"{state:<20} {commodity:<32} {'-':>10} {'-':>8} {'-':>9} {'-':>7}  [{status}]")

if ok_results:
    maes   = [r[2] for r in ok_results]
    mapes  = [r[3] for r in ok_results]
    r2s    = [r[5] for r in ok_results]
    print("-" * 95)
    print(f"{'AVERAGE':<20} {'':<32} {np.mean(maes):>10.2f} {np.mean(mapes):>7.1f}% {'':>9} {np.mean(r2s):>7.3f}")
    print(f"\nMAPE < 10% (good): {sum(1 for m in mapes if m < 10)}/{len(ok_results)}")
    print(f"MAPE < 20% (ok):   {sum(1 for m in mapes if m < 20)}/{len(ok_results)}")
    print(f"Median MAPE: {np.median(mapes):.1f}%")
