"""Fusion layer for CropAdvisor — combines the module scores into ranked,
explained recommendations.

Blends the available 0-1 module scores with configurable weights. Default
aggregation is a WEIGHTED GEOMETRIC MEAN (multi-criteria): a crop must be
reasonable on every dimension, so a near-zero score in any module drags the
total down instead of being outvoted by one strong dimension.

    final = Π (floor + (1-floor)·score[crop][m]) ^ weight[m]      (geometric)
            = exp( Σ weight[m]·ln(softened score) )

The small `floor` softens zeros: a missing/weak dimension penalizes hard but
doesn't brittlely annihilate the score. This fixes the additive flaw where an
agronomically-absurd crop (coffee in Punjab) could top the list on market price
alone. `method="additive"` (the old Σ weight·score) is kept for comparison.

Graceful degradation: a module that can't run (e.g. Suitability with no soil/
climate features = Simple Mode) is dropped and the remaining weights are
renormalized — never blocks a recommendation. Weather/NDVI are Phase 2/3 and
simply absent for now.

Farming goal nudges the weights (Max Profit -> market, Low Risk -> proven
regional). Sustainable / Water-Efficient are accepted but no-ops in v1 (no
supporting data yet). Each recommendation carries a per-module breakdown plus
plain-language `why` / `cautions` for the explanation layer.
"""
import math

from analysis.crop_catalog import WHITELIST
from analysis.regional_fit import regional_fit_scores
from analysis.suitability import suitability_scores
from analysis.market_profitability import market_profitability_scores

# v1 default weights over the three implemented modules (sum to 1.0).
DEFAULT_WEIGHTS = {"suitability": 0.35, "regional": 0.30, "market": 0.35}

# Geometric-mean softening: a 0 score becomes this floor, so one weak dimension
# strongly penalizes the total without zeroing it outright.
SOFTENING_FLOOR = 0.05


def _fuse(breakdown: dict, w: dict, method: str) -> float:
    """Aggregate a crop's per-module scores into one 0-1 score. `w` sums to 1."""
    if method == "additive":
        return round(sum(w[m] * breakdown[m] for m in w), 4)
    # weighted geometric mean over softened scores (default)
    log_sum = sum(
        w[m] * math.log(SOFTENING_FLOOR + (1 - SOFTENING_FLOOR) * breakdown[m])
        for m in w
    )
    return round(math.exp(log_sum), 4)

# goal -> per-module weight multipliers (applied before renormalization)
GOAL_MULTIPLIERS = {
    "max_profit": {"market": 1.6},
    "low_risk":   {"regional": 1.4},   # locally proven crops carry less risk
    "sustainable": {},                 # no supporting data in v1
    "water_efficient": {},             # no supporting data in v1
}


def _why(crop, modules) -> list[str]:
    why = []
    if "suitability" in modules:
        s = modules["suitability"][crop]
        if s["score"] >= 0.6:
            why.append(f"strong soil/climate match ({s['prob_pct']:.0f}% model confidence)")
    if "regional" in modules:
        r = modules["regional"][crop]
        if r["score"] >= 0.5 and r["level"] != "none":
            why.append(f"proven in your {r['level']}: grown {r['years_grown']} years on record")
    if "market" in modules:
        m = modules["market"][crop]
        if m["score"] >= 0.6 and m["recent_price"]:
            why.append(f"favorable market: ~₹{m['recent_price']:.0f}/quintal ({m['risk_level']} volatility)")
    return why


def _cautions(crop, modules) -> list[str]:
    cautions = []
    if "suitability" in modules and modules["suitability"][crop]["score"] < 0.3:
        cautions.append("weak agronomic match for this soil/climate")
    if "regional" in modules:
        r = modules["regional"][crop]
        if r["level"] == "none" or r["score"] == 0.0:
            cautions.append("no local growing history")
    if "market" in modules and modules["market"][crop]["risk_level"] == "high":
        cautions.append("high price volatility")
    return cautions


def recommend(state: str, district: str | None = None, season: str | None = None,
              features: dict | None = None, goal: str | None = None,
              crops=None, top_k: int = 3, weights: dict | None = None,
              method: str = "geometric") -> dict:
    crops = list(crops) if crops else WHITELIST

    # 1. run available modules
    modules: dict[str, dict] = {
        "regional": regional_fit_scores(state, district, season, crops),
        "market": market_profitability_scores(crops),  # national, robust
    }
    if features:  # Smart Mode — soil/climate present
        modules["suitability"] = suitability_scores(features, crops)

    # 2. weights: keep available modules, apply goal, renormalize
    w = {m: (weights or DEFAULT_WEIGHTS).get(m, 0.0) for m in modules}
    for m, mult in GOAL_MULTIPLIERS.get(goal or "", {}).items():
        if m in w:
            w[m] *= mult
    total = sum(w.values()) or 1.0
    w = {m: round(v / total, 4) for m, v in w.items()}

    # 3. score + rank
    scored = []
    for c in crops:
        breakdown = {m: modules[m][c]["score"] for m in w}
        score = _fuse(breakdown, w, method)
        scored.append((c, score, breakdown))
    scored.sort(key=lambda t: t[1], reverse=True)

    recommendations = [{
        "crop": c,
        "score": score,
        "breakdown": breakdown,
        "why": _why(c, modules),
        "cautions": _cautions(c, modules),
    } for c, score, breakdown in scored[:top_k]]

    return {
        "modules_used": sorted(w.keys()),
        "weights_used": w,
        "goal": goal,
        "method": method,
        "recommendations": recommendations,
    }
