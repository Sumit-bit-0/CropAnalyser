import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import MinMaxScaler
from models.lstm import PriceLSTM
from analysis.trends import get_price_trend
from config import LSTM_SEQUENCE_LEN, LSTM_FORECAST_LEN, MODELS_DIR


def train(state: str, commodity: str, epochs: int = 50) -> float:
    records = get_price_trend(state, commodity)
    if len(records) < LSTM_SEQUENCE_LEN + LSTM_FORECAST_LEN + 5:
        raise ValueError(f"Not enough data for {state}/{commodity}: {len(records)} records")

    data = np.array([[r["farm_gate_price"], r["modal_price"]] for r in records], dtype=np.float32)
    scaler = MinMaxScaler()
    data_scaled = scaler.fit_transform(data)

    X, y = [], []
    for i in range(len(data_scaled) - LSTM_SEQUENCE_LEN - LSTM_FORECAST_LEN):
        X.append(data_scaled[i:i + LSTM_SEQUENCE_LEN])
        y.append(data_scaled[i + LSTM_SEQUENCE_LEN:i + LSTM_SEQUENCE_LEN + LSTM_FORECAST_LEN])
    X, y = np.array(X), np.array(y)

    split = int(len(X) * 0.8)
    X_train = torch.tensor(X[:split])
    y_train = torch.tensor(y[:split])
    X_test  = torch.tensor(X[split:])
    y_test  = torch.tensor(y[split:])

    loader  = DataLoader(TensorDataset(X_train, y_train), batch_size=16, shuffle=True)
    model   = PriceLSTM(input_size=2, hidden_size=64, num_layers=2, forecast_len=LSTM_FORECAST_LEN)
    opt     = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()

    model.train()
    for epoch in range(epochs):
        for xb, yb in loader:
            pred = model(xb)
            loss = loss_fn(pred, yb)
            opt.zero_grad()
            loss.backward()
            opt.step()
        if (epoch + 1) % 10 == 0:
            print(f"Epoch {epoch+1}/{epochs} — loss: {loss.item():.6f}")

    model.eval()
    with torch.no_grad():
        val_pred = model(X_test)
        val_loss = loss_fn(val_pred, y_test).item()
    print(f"Validation MSE: {val_loss:.6f}")

    safe_name   = f"{state}_{commodity}".replace(" ", "_").replace("/", "-")
    model_path  = MODELS_DIR / f"{safe_name}.pt"
    scaler_path = MODELS_DIR / f"{safe_name}_scaler.npy"
    torch.save(model.state_dict(), model_path)
    np.save(str(scaler_path), {"scale_": scaler.scale_, "min_": scaler.min_})
    print(f"Saved model to {model_path}")
    return float(val_loss)
