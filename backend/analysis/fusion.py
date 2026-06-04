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
from analysis.regional_fit import regional_fit_scores, RECENT_YEARS
from analysis.suitability import suitability_scores
from analysis.market_profitability import market_profitability_scores
from analysis.yield_predict import predict_yield
from analysis.price_outlook import price_outlook
from analysis.weather_fit import weather_fit_scores

# Default weights over the three implemented modules (sum to 1.0), used in Smart
# Mode when soil/climate is supplied.
DEFAULT_WEIGHTS = {"suitability": 0.30, "regional": 0.25, "market": 0.30, "weather": 0.15}

# Simple Mode (no soil/climate): with the agronomic signal absent, what a region
# has PROVENLY grown is the most trustworthy default — so regional leads and the
# (absolute-price-biased) market signal is only a tie-breaker. Without this,
# renormalizing DEFAULT_WEIGHTS would hand market the majority vote and bury
# cheap-but-correct staples like maize/rice.
SIMPLE_MODE_WEIGHTS = {"regional": 0.50, "market": 0.30, "weather": 0.20}

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
    if "suitability" in modules and crop in modules["suitability"]:
        s = modules["suitability"][crop]
        if s["score"] >= 0.6:
            why.append(f"strong soil/climate match ({s['prob_pct']:.0f}% model confidence)")
    if "regional" in modules:
        r = modules["regional"][crop]
        if r["score"] >= 0.5 and r["level"] != "none":
            why.append(f"proven in your {r['level']}: grown {r['years_grown']} of the last {RECENT_YEARS} years")
    if "market" in modules:
        m = modules["market"][crop]
        if m["score"] >= 0.6 and m["recent_price"]:
            why.append(f"favorable market: ~₹{m['recent_price']:.0f}/quintal ({m['risk_level']} volatility)")
    if "weather" in modules and crop in modules["weather"]:
        if modules["weather"][crop]["score"] >= 0.6:
            why.append("climate well-suited for this season")
    return why


def _cautions(crop, modules) -> list[str]:
    cautions = []
    if ("suitability" in modules and crop in modules["suitability"]
            and modules["suitability"][crop]["score"] < 0.3):
        cautions.append("weak agronomic match for this soil/climate")
    if "regional" in modules:
        r = modules["regional"][crop]
        if r["level"] == "none" or r["score"] == 0.0:
            cautions.append("no local growing history")
    if "market" in modules and modules["market"][crop]["risk_level"] == "high":
        cautions.append("high price volatility")
    if ("weather" in modules and crop in modules["weather"]
            and modules["weather"][crop]["score"] <= 0.3):
        cautions.append("seasonal climate is marginal for this crop")
    return cautions


def _enrich(rec: dict, modules: dict, state, district, season) -> dict:
    """Attach tradition standing + our yield prediction + price outlook to a rec."""
    crop = rec["crop"]
    reg = modules.get("regional", {}).get(crop, {})
    rec["traditional"] = {"years_grown": int(reg.get("years_grown", 0) or 0),
                          "level": reg.get("level", "none"),
                          "window_years": RECENT_YEARS}
    rec["yield"] = predict_yield(state, district, season, crop, year=2016)
    rec["price_outlook"] = price_outlook(state, crop)
    return rec


def recommend(state: str, district: str | None = None, season: str | None = None,
              features: dict | None = None, goal: str | None = None,
              crops=None, top_k: int = 3, weights: dict | None = None,
              method: str = "geometric", coords: tuple | None = None) -> dict:
    crops = list(crops) if crops else WHITELIST

    # 1. run available modules
    modules: dict[str, dict] = {
        "regional": regional_fit_scores(state, district, season, crops),
        "market": market_profitability_scores(crops),  # national, robust
    }
    if features:  # Smart Mode — soil/climate present
        modules["suitability"] = suitability_scores(features, crops)

    wf = weather_fit_scores(state, district, season, crops, coords=coords)
    if wf:  # only include when it actually ran (coords ok + API up)
        modules["weather"] = wf

    # 2. base weights: explicit override > DEFAULT (Smart) > SIMPLE_MODE (no soil).
    #    Then apply goal multipliers and renormalize over the modules that ran.
    base = weights or (DEFAULT_WEIGHTS if "suitability" in modules else SIMPLE_MODE_WEIGHTS)
    w = {m: base.get(m, 0.0) for m in modules}
    for m, mult in GOAL_MULTIPLIERS.get(goal or "", {}).items():
        if m in w:
            w[m] *= mult
    total = sum(w.values()) or 1.0
    keys = list(w.keys())
    assert keys, "no modules to weight (regional+market are always present)"
    # Round each weight; the last key (by dict insertion order) absorbs the
    # rounding residual so the weights always sum to exactly 1.0.
    rounded = {m: round(w[m] / total, 4) for m in keys[:-1]}
    rounded[keys[-1]] = round(1.0 - sum(rounded.values()), 4)
    w = rounded

    # 3. score + rank. A crop is scored only on the modules that actually cover
    #    it (suitability omits crops outside the soil model); per-crop weights are
    #    renormalized over those, so a missing term degrades instead of zeroing.
    scored = []
    for c in crops:
        avail = {m: modules[m][c]["score"] for m in w if c in modules[m]}
        cw_total = sum(w[m] for m in avail) or 1.0
        cw = {m: w[m] / cw_total for m in avail}
        score = _fuse(avail, cw, method)
        scored.append((c, score, avail))
    scored.sort(key=lambda t: t[1], reverse=True)

    recommendations = [_enrich({
        "crop": c,
        "score": score,
        "breakdown": breakdown,
        "why": _why(c, modules),
        "cautions": _cautions(c, modules),
    }, modules, state, district, season) for c, score, breakdown in scored[:top_k]]

    return {
        "modules_used": sorted(w.keys()),
        "weights_used": w,
        "goal": goal,
        "method": method,
        "recommendations": recommendations,
    }
