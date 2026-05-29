import json
import joblib
import numpy as np
import torch
from config import MODELS_DIR
from models.crop_recommender import CropMLP

FEATURES = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]
_CACHE = None


def _load():
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    model_path = MODELS_DIR / "crop_recommender.pt"
    scaler_path = MODELS_DIR / "crop_recommender_scaler.joblib"
    labels_path = MODELS_DIR / "crop_recommender_labels.json"
    if not (model_path.exists() and scaler_path.exists() and labels_path.exists()):
        raise FileNotFoundError(
            "Crop recommendation model not trained yet. Run models/train_crop_recommender.py"
        )
    ckpt = torch.load(str(model_path), map_location="cpu")
    model = CropMLP(in_features=ckpt["in_features"], n_classes=ckpt["n_classes"])
    model.load_state_dict(ckpt["state_dict"])
    model.eval()
    scaler = joblib.load(scaler_path)
    labels = json.loads(labels_path.read_text())
    _CACHE = (model, scaler, labels)
    return _CACHE


def recommend_crops(features: dict, top_k: int = 3) -> list[dict]:
    missing = [f for f in FEATURES if f not in features]
    if missing:
        raise ValueError(f"Missing features: {missing}")
    model, scaler, labels = _load()
    x = np.array([[float(features[f]) for f in FEATURES]], dtype=np.float32)
    xs = scaler.transform(x).astype(np.float32)
    with torch.no_grad():
        probs = torch.softmax(model(torch.tensor(xs)), dim=1).numpy()[0]
    idx = probs.argsort()[::-1][:top_k]
    return [{"crop": labels[i], "confidence_pct": round(float(probs[i] * 100), 1)} for i in idx]
