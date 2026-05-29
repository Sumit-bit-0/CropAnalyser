import torch
import pytest
from models.crop_recommender import CropMLP
from analysis import crop_recommender as cr

SAMPLE = {"N": 90, "P": 42, "K": 43, "temperature": 20.8,
          "humidity": 82.0, "ph": 6.5, "rainfall": 202.9}


def test_cropmlp_output_shape():
    model = CropMLP(in_features=7, n_classes=22)
    x = torch.randn(5, 7)
    out = model(x)
    assert out.shape == (5, 22)


def test_recommend_crops_structure():
    out = cr.recommend_crops(SAMPLE, top_k=3)
    assert len(out) == 3
    assert {"crop", "confidence_pct"} <= set(out[0].keys())
    assert out[0]["confidence_pct"] >= out[1]["confidence_pct"]
    assert sum(r["confidence_pct"] for r in out) <= 100.5


def test_recommend_missing_model_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(cr, "_CACHE", None, raising=False)
    monkeypatch.setattr(cr, "MODELS_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        cr.recommend_crops(SAMPLE)
