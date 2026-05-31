"""Agronomic Suitability scorer for CropAdvisor (fusion input #3).

Reuses the trained 7-input soil/climate model that already backs Simple Mode
(`crop_recommender`). For fusion we don't want a single predicted crop — we want
a comparable per-crop suitability signal. So we take the model's softmax
probability for each whitelist crop and normalize so the most-suitable candidate
= 1.0 (consistent with regional_fit). `prob_pct` keeps the raw model probability
for the explanation layer ("strong agronomic match: 84%").

All 20 whitelist crops are within the model's 22 training labels, so every
requested crop has a probability. Raises FileNotFoundError if the model isn't
trained, ValueError if a feature is missing (both via predict_proba).
"""
from analysis.crop_recommender import predict_proba
from analysis.crop_catalog import WHITELIST


def suitability_scores(features: dict, crops=None) -> dict:
    """Map of {canonical_crop: {score 0-1 (max-normalized), prob_pct (raw)}}."""
    crops = list(crops) if crops else WHITELIST
    proba = predict_proba(features)  # {label: prob} over the model's labels
    sub = {c: float(proba.get(c, 0.0)) for c in crops}
    top = max(sub.values()) if sub else 0.0
    denom = top if top > 0 else 1.0
    return {c: {"score": round(p / denom, 3), "prob_pct": round(p * 100, 3)}
            for c, p in sub.items()}
