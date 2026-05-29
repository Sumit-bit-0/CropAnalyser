import json
import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from config import DATA_RAW, MODELS_DIR, init_dirs
from models.crop_recommender import CropMLP

FEATURES = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]


def main():
    init_dirs()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type != "cuda":
        print("WARNING: CUDA not available — training on CPU (violates project GPU rule).")
    print(f"Training crop recommender on device: {device}")

    df = pd.read_csv(DATA_RAW / "crop_recommendation.csv")
    labels = sorted(df["label"].unique().tolist())
    label_to_idx = {c: i for i, c in enumerate(labels)}

    X = df[FEATURES].values.astype(np.float32)
    y = df["label"].map(label_to_idx).values.astype(np.int64)

    scaler = StandardScaler().fit(X)
    Xs = scaler.transform(X).astype(np.float32)

    Xtr, Xva, ytr, yva = train_test_split(Xs, y, test_size=0.2, stratify=y, random_state=42)
    Xtr_t = torch.tensor(Xtr, device=device); ytr_t = torch.tensor(ytr, device=device)
    Xva_t = torch.tensor(Xva, device=device); yva_t = torch.tensor(yva, device=device)

    model = CropMLP(in_features=len(FEATURES), n_classes=len(labels)).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=0.01)
    loss_fn = nn.CrossEntropyLoss()

    for epoch in range(200):
        model.train(); opt.zero_grad()
        loss = loss_fn(model(Xtr_t), ytr_t)
        loss.backward(); opt.step()
        if (epoch + 1) % 50 == 0:
            model.eval()
            with torch.no_grad():
                acc = (model(Xva_t).argmax(1) == yva_t).float().mean().item()
            print(f"epoch {epoch+1}: loss={loss.item():.4f} val_acc={acc:.4f}")

    model.eval()
    with torch.no_grad():
        val_acc = (model(Xva_t).argmax(1) == yva_t).float().mean().item()
    print(f"FINAL val_acc={val_acc:.4f}")

    torch.save(
        {"state_dict": model.cpu().state_dict(),
         "in_features": len(FEATURES), "n_classes": len(labels)},
        MODELS_DIR / "crop_recommender.pt",
    )
    joblib.dump(scaler, MODELS_DIR / "crop_recommender_scaler.joblib")
    (MODELS_DIR / "crop_recommender_labels.json").write_text(json.dumps(labels))
    print(f"Saved artifacts to {MODELS_DIR}")


if __name__ == "__main__":
    main()
