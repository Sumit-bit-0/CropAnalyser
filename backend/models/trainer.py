import copy
import joblib
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import MinMaxScaler
from models.lstm import PriceLSTM
from analysis.trends import get_price_trend
from config import LSTM_SEQUENCE_LEN, LSTM_FORECAST_LEN, MODELS_DIR

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

INPUT_SIZE  = 4   # farm_gate_price, modal_price, sin(month), cos(month)
OUTPUT_SIZE = 2   # farm_gate_price, modal_price


def _month_features(period: str) -> tuple[float, float]:
    """Return (sin, cos) cyclical encoding for the month part of 'YYYY-MM'."""
    month = int(period.split("-")[1])
    angle = 2 * np.pi * (month - 1) / 12
    return float(np.sin(angle)), float(np.cos(angle))


def train(state: str, commodity: str, epochs: int = 300) -> float:
    if not torch.cuda.is_available():
        print("WARNING: CUDA not available — falling back to CPU. Check torch CUDA installation.")
    print(f"Using device: {device}")

    records = get_price_trend(state, commodity)
    if len(records) < LSTM_SEQUENCE_LEN + LSTM_FORECAST_LEN + 5:
        raise ValueError(f"Not enough data for {state}/{commodity}: {len(records)} records")

    prices  = np.array([[r["farm_gate_price"], r["modal_price"]] for r in records], dtype=np.float32)
    months  = np.array([_month_features(r["period"]) for r in records], dtype=np.float32)

    price_scaler = MinMaxScaler()
    prices_scaled = price_scaler.fit_transform(prices)

    # Inputs combine scaled prices with cyclical month features (already in [-1, 1])
    inputs  = np.concatenate([prices_scaled, months], axis=1)   # (N, 4)
    targets = prices_scaled                                       # (N, 2)

    X, y = [], []
    for i in range(len(inputs) - LSTM_SEQUENCE_LEN - LSTM_FORECAST_LEN):
        X.append(inputs[i:i + LSTM_SEQUENCE_LEN])
        y.append(targets[i + LSTM_SEQUENCE_LEN:i + LSTM_SEQUENCE_LEN + LSTM_FORECAST_LEN])
    X, y = np.array(X), np.array(y)

    # Time-ordered split: 70% train, 15% val (early stopping), 15% test
    n_total = len(X)
    n_train = int(n_total * 0.70)
    n_val   = int(n_total * 0.85)

    X_train = torch.tensor(X[:n_train]).to(device)
    y_train = torch.tensor(y[:n_train]).to(device)
    X_val   = torch.tensor(X[n_train:n_val]).to(device)
    y_val   = torch.tensor(y[n_train:n_val]).to(device)
    X_test  = torch.tensor(X[n_val:]).to(device)
    y_test  = torch.tensor(y[n_val:]).to(device)

    if len(X_val) == 0 or len(X_test) == 0:
        # Series too short — fall back to 80/20 with no early stopping
        n_train = int(n_total * 0.80)
        X_train = torch.tensor(X[:n_train]).to(device)
        y_train = torch.tensor(y[:n_train]).to(device)
        X_val   = X_train
        y_val   = y_train
        X_test  = torch.tensor(X[n_train:]).to(device)
        y_test  = torch.tensor(y[n_train:]).to(device)

    loader  = DataLoader(TensorDataset(X_train, y_train), batch_size=32, shuffle=True)
    model   = PriceLSTM(input_size=INPUT_SIZE, hidden_size=64, num_layers=2,
                        forecast_len=LSTM_FORECAST_LEN, output_size=OUTPUT_SIZE).to(device)
    opt     = torch.optim.Adam(model.parameters(), lr=1e-3)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, patience=8, factor=0.5, min_lr=1e-5)
    loss_fn = nn.MSELoss()

    best_val_loss  = float("inf")
    best_state     = copy.deepcopy(model.state_dict())
    patience       = 30
    bad_epochs     = 0

    for epoch in range(epochs):
        model.train()
        epoch_loss = 0.0
        for xb, yb in loader:
            pred = model(xb)
            loss = loss_fn(pred, yb)
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            opt.step()
            epoch_loss += loss.item()
        epoch_loss /= len(loader)

        model.eval()
        with torch.no_grad():
            val_pred  = model(X_val)
            val_loss  = loss_fn(val_pred, y_val).item()
        scheduler.step(val_loss)

        if val_loss < best_val_loss - 1e-6:
            best_val_loss = val_loss
            best_state    = copy.deepcopy(model.state_dict())
            bad_epochs    = 0
        else:
            bad_epochs += 1

        if (epoch + 1) % 25 == 0:
            lr = opt.param_groups[0]["lr"]
            print(f"Epoch {epoch+1}/{epochs} - train: {epoch_loss:.6f}  val: {val_loss:.6f}  lr: {lr:.2e}  bad: {bad_epochs}")

        if bad_epochs >= patience:
            print(f"Early stop at epoch {epoch+1}. Best val loss: {best_val_loss:.6f}")
            break

    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        test_pred = model(X_test)
        test_loss = loss_fn(test_pred, y_test).item()
    print(f"Best val MSE: {best_val_loss:.6f}  Test MSE: {test_loss:.6f}")

    safe_name   = f"{state}_{commodity}".replace(" ", "_").replace("/", "-")
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model_path  = MODELS_DIR / f"{safe_name}.pt"
    scaler_path = MODELS_DIR / f"{safe_name}_scaler.joblib"
    torch.save(model.state_dict(), model_path)
    joblib.dump(price_scaler, scaler_path)
    print(f"Saved model to {model_path}")
    return float(test_loss)
