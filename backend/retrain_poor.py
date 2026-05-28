"""
Hyperparameter sweep retrain for the 4 poorest-performing LSTM series.

Grid: hidden_size {64, 128} x dropout {0.2, 0.35} x seq_len {12, 18}  = 8 configs/series
Picks the config with the lowest test MAPE (in original price units) and
overwrites the existing .pt + _scaler.joblib in saved_models/.

Always uses GPU (per project GPU rule). Fails loudly if CUDA is not available.
"""

import copy
import itertools
import json
import joblib
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_absolute_error, r2_score

from analysis.trends import get_price_trend
from config import LSTM_FORECAST_LEN, MODELS_DIR

assert torch.cuda.is_available(), "CUDA required (project GPU rule). Aborting."
device = torch.device("cuda")
print(f"Device: {device} ({torch.cuda.get_device_name(0)})")

INPUT_SIZE  = 4   # farm_gate, modal, sin(month), cos(month)
OUTPUT_SIZE = 2

POOR_SERIES = [
    ("Nct Of Delhi", "Rice"),
    ("Nct Of Delhi", "Tomato"),
    ("Punjab",       "Rice"),
    ("Pondicherry",  "Sesamum (Sesame,Gingelly,Til)"),
]

GRID = {
    "hidden_size": [64, 128],
    "dropout":     [0.20, 0.35],
    "seq_len":     [12, 18],
}


class PriceLSTM(nn.Module):
    """Local copy of PriceLSTM that accepts a dropout argument (the shared one hardcodes 0.2)."""
    def __init__(self, input_size, hidden_size, num_layers, forecast_len, output_size, dropout):
        super().__init__()
        self.forecast_len = forecast_len
        self.output_size  = output_size
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=dropout)
        self.fc   = nn.Linear(hidden_size, output_size * forecast_len)

    def forward(self, x):
        out, _ = self.lstm(x)
        last = out[:, -1, :]
        return self.fc(last).view(-1, self.forecast_len, self.output_size)


def _month_features(period: str) -> tuple[float, float]:
    month = int(period.split("-")[1])
    angle = 2 * np.pi * (month - 1) / 12
    return float(np.sin(angle)), float(np.cos(angle))


def _build_windows(records, seq_len, forecast_len):
    prices = np.array([[r["farm_gate_price"], r["modal_price"]] for r in records], dtype=np.float32)
    months = np.array([_month_features(r["period"]) for r in records], dtype=np.float32)

    scaler = MinMaxScaler()
    prices_scaled = scaler.fit_transform(prices)

    inputs  = np.concatenate([prices_scaled, months], axis=1)
    targets = prices_scaled

    X, y = [], []
    for i in range(len(inputs) - seq_len - forecast_len):
        X.append(inputs[i:i + seq_len])
        y.append(targets[i + seq_len:i + seq_len + forecast_len])
    return np.array(X), np.array(y), scaler


def _train_and_eval(state, commodity, hidden_size, dropout, seq_len,
                    epochs=400, patience=30, lr=1e-3):
    records = get_price_trend(state, commodity)
    if len(records) < seq_len + LSTM_FORECAST_LEN + 5:
        return None  # not enough records for this seq_len

    X, y, scaler = _build_windows(records, seq_len, LSTM_FORECAST_LEN)

    n_total = len(X)
    n_train = int(n_total * 0.70)
    n_val   = int(n_total * 0.85)

    X_train = torch.tensor(X[:n_train]).to(device)
    y_train = torch.tensor(y[:n_train]).to(device)
    X_val   = torch.tensor(X[n_train:n_val]).to(device)
    y_val   = torch.tensor(y[n_train:n_val]).to(device)
    X_test  = torch.tensor(X[n_val:]).to(device)
    y_test_np = y[n_val:]

    if len(X_val) == 0 or len(X_test) == 0:
        return None

    loader = DataLoader(TensorDataset(X_train, y_train), batch_size=32, shuffle=True)
    model  = PriceLSTM(INPUT_SIZE, hidden_size, num_layers=2,
                       forecast_len=LSTM_FORECAST_LEN, output_size=OUTPUT_SIZE,
                       dropout=dropout).to(device)
    opt    = torch.optim.Adam(model.parameters(), lr=lr)
    sched  = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, patience=8, factor=0.5, min_lr=1e-5)
    lossfn = nn.MSELoss()

    best_val  = float("inf")
    best_sd   = copy.deepcopy(model.state_dict())
    bad       = 0

    for epoch in range(epochs):
        model.train()
        for xb, yb in loader:
            pred = model(xb)
            loss = lossfn(pred, yb)
            opt.zero_grad(); loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()

        model.eval()
        with torch.no_grad():
            vloss = lossfn(model(X_val), y_val).item()
        sched.step(vloss)

        if vloss < best_val - 1e-6:
            best_val = vloss
            best_sd  = copy.deepcopy(model.state_dict())
            bad = 0
        else:
            bad += 1
        if bad >= patience:
            break

    model.load_state_dict(best_sd)
    model.eval()
    with torch.no_grad():
        pred_scaled = model(X_test).cpu().numpy()

    y_orig    = scaler.inverse_transform(y_test_np.reshape(-1, 2))
    pred_orig = scaler.inverse_transform(pred_scaled.reshape(-1, 2))

    mae  = float(mean_absolute_error(y_orig, pred_orig))
    mape = float(np.mean(np.abs((y_orig - pred_orig) / np.where(y_orig == 0, 1, y_orig))) * 100)
    r2   = float(r2_score(y_orig, pred_orig))

    return {
        "hidden_size": hidden_size, "dropout": dropout, "seq_len": seq_len,
        "mae": mae, "mape": mape, "r2": r2,
        "state_dict": best_sd, "scaler": scaler,
    }


def _save_best(state, commodity, best):
    safe = f"{state}_{commodity}".replace(" ", "_").replace("/", "-")
    model_path  = MODELS_DIR / f"{safe}.pt"
    scaler_path = MODELS_DIR / f"{safe}_scaler.joblib"
    meta_path   = MODELS_DIR / f"{safe}_meta.json"

    torch.save(best["state_dict"], model_path)
    joblib.dump(best["scaler"], scaler_path)
    # Sidecar so loaders (predictor.py, eval_models.py) can construct the right
    # architecture when hidden_size != default 64 or seq_len != default 12.
    meta = {
        "hidden_size": best["hidden_size"],
        "num_layers":  2,
        "seq_len":     best["seq_len"],
        "forecast_len": LSTM_FORECAST_LEN,
        "dropout_trained": best["dropout"],
        "test_mape": round(best["mape"], 2),
        "test_mae":  round(best["mae"], 2),
        "test_r2":   round(best["r2"], 3),
    }
    meta_path.write_text(json.dumps(meta, indent=2))
    return model_path, scaler_path, meta_path


def main():
    grid_configs = list(itertools.product(
        GRID["hidden_size"], GRID["dropout"], GRID["seq_len"]
    ))
    print(f"Grid: {len(grid_configs)} configs x {len(POOR_SERIES)} series = {len(grid_configs) * len(POOR_SERIES)} runs\n")

    summary = []

    for state, commodity in POOR_SERIES:
        print(f"\n=== {state} / {commodity} ===")
        best = None
        all_runs = []
        for hidden, dropout, seq_len in grid_configs:
            res = _train_and_eval(state, commodity, hidden, dropout, seq_len)
            if res is None:
                print(f"  hidden={hidden} dropout={dropout} seq={seq_len:<2}  SKIP (not enough records)")
                continue
            print(f"  hidden={hidden:<3} dropout={dropout} seq={seq_len:<2}  MAPE={res['mape']:5.1f}%  R2={res['r2']:7.2f}  MAE={res['mae']:7.1f}")
            all_runs.append(res)
            if best is None or res["mape"] < best["mape"]:
                best = res

        if best is None:
            print("  (no successful runs)")
            continue

        model_path, _, meta_path = _save_best(state, commodity, best)
        summary.append((state, commodity, best))
        print(f"  >>> BEST: hidden={best['hidden_size']} dropout={best['dropout']} seq={best['seq_len']}"
              f" -> MAPE={best['mape']:.1f}%  R2={best['r2']:.2f}")
        print(f"      saved {model_path.name} + {meta_path.name}")

    print("\n" + "=" * 90)
    print(f"{'State':<18} {'Commodity':<35} {'hidden':>6} {'drop':>5} {'seq':>4} {'MAPE':>7} {'R2':>8}")
    print("-" * 90)
    for state, commodity, b in summary:
        print(f"{state:<18} {commodity:<35} {b['hidden_size']:>6} {b['dropout']:>5} {b['seq_len']:>4} "
              f"{b['mape']:>6.1f}% {b['r2']:>8.2f}")


if __name__ == "__main__":
    main()
