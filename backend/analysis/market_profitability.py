"""Market Profitability scorer for CropAdvisor (fusion input #2).

Scores how favorable the market is for each candidate crop. v2 signal = gross
revenue PER HECTARE — recent modal price × the crop's typical yield —
risk-adjusted by price volatility and normalized so the best candidate = 1.0:

    revenue = recent_price (₹/quintal) × typical_yield (per hectare)
    raw     = revenue × (1 − volatility_cv)
    score   = raw / max(raw across candidates)

Why per-hectare revenue, not absolute ₹/quintal (the v1 signal): a farmer plants
an AREA, not a quintal. Absolute price made cheap-but-high-yield staples
(rice/wheat/maize ~₹1800–2900/q) lose to expensive-but-low-yield crops
(coffee ₹20,971/q) even where the staples dominate. Multiplying by typical yield
restores the staples — e.g. rice now out-earns low-yield pulses per hectare, and
sugarcane (≈53 t/ha) rises appropriately.

`typical_yield` is the NATIONAL MEDIAN of district_crop_history.crop_yield
(median = robust to outliers). Prices are read NATIONALLY by default; pass
`state` for a localized read. recent_price / avg_price / volatility / risk_level
/ typical_yield are returned for the explanation layer.

KNOWN LIMITATIONS:
  - This is gross revenue, not profit — it ignores per-crop cost of cultivation.
    The full "net profit/ha = (price × yield) − cost" needs a cost dataset we
    don't have yet (CACP / DES). See docs roadmap; that is the next refinement.
  - crop_yield units are inconsistent across crops in the source data (tonnes
    for cereals, bales for cotton/jute, nuts for coconut), so revenue is inflated
    for a few plantation/fibre crops. In practice those crops have little/no
    regional history where it matters, so the geometric fusion floors them via
    the regional term before the distortion can surface them. Crops with no yield
    data at all fall back to a neutral median yield.
"""
from database import query, table_exists
from analysis.crop_catalog import CANONICAL_CROPS, WHITELIST


def _risk_level(cv: float) -> str:
    if cv < 0.15:
        return "low"
    if cv <= 0.30:
        return "medium"
    return "high"


def _national_median_yields(canon_crops: list[str]) -> dict:
    """National median crop_yield per canonical crop (empty if history absent)."""
    if not canon_crops or not table_exists("district_crop_history"):
        return {}
    inlist = ",".join("?" * len(canon_crops))
    df = query(f"""
        SELECT canonical_crop,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY crop_yield) AS yld
        FROM district_crop_history
        WHERE canonical_crop IN ({inlist}) AND crop_yield > 0
        GROUP BY canonical_crop
    """, tuple(canon_crops))
    return {r.canonical_crop: float(r.yld)
            for r in df.itertuples(index=False) if r.yld and r.yld > 0}


def market_profitability_scores(crops=None, state: str | None = None) -> dict:
    """Map of {canonical_crop: {score 0-1, recent_price, avg_price, volatility_cv, risk_level}}."""
    crops = list(crops) if crops else WHITELIST
    results = {c: {"score": 0.0, "recent_price": None, "avg_price": None,
                   "volatility_cv": None, "risk_level": "unknown",
                   "typical_yield": None} for c in crops}

    alias_to_canon = {a: c for c in crops for a in CANONICAL_CROPS[c]["market"]}
    aliases = list(alias_to_canon)
    if not aliases:
        return results

    inlist = ",".join("?" * len(aliases))
    params = tuple(aliases)
    state_clause = ""
    if state:
        state_clause = " AND LOWER(state) = LOWER(?)"
        params = params + (state,)

    # yearly average modal price per market commodity (small result set)
    df = query(f"""
        SELECT commodity, year, AVG(modal_price) AS avg_modal
        FROM prices
        WHERE commodity IN ({inlist}){state_clause}
        GROUP BY commodity, year
        ORDER BY commodity, year
    """, params)
    if df.empty:
        return results

    # typical yield per crop; neutral fallback (median of known yields) for crops
    # with no yield data, so they're neither zeroed nor exploded.
    yields = _national_median_yields(crops)
    fallback_yield = (sorted(yields.values())[len(yields) // 2] if yields else 1.0)

    # per-canonical: pool its market aliases, derive recent price + volatility,
    # then weight by typical yield -> gross revenue per hectare.
    raw_scores = {}
    for canon in crops:
        sub = df[df["commodity"].isin(CANONICAL_CROPS[canon]["market"])]
        if sub.empty:
            continue
        yearly = sub.groupby("year")["avg_modal"].mean()  # avg across this crop's aliases
        recent_price = float(yearly.loc[yearly.index.max()])
        avg_price = float(yearly.mean())
        std_price = float(yearly.std(ddof=0))
        cv = (std_price / avg_price) if avg_price else 0.0
        yld = yields.get(canon, fallback_yield)
        revenue = recent_price * yld
        raw = revenue * max(0.0, 1.0 - cv)
        raw_scores[canon] = raw
        results[canon] = {
            "score": 0.0,  # filled after normalization
            "recent_price": round(recent_price, 2),
            "avg_price": round(avg_price, 2),
            "volatility_cv": round(cv, 3),
            "risk_level": _risk_level(cv),
            "typical_yield": round(yld, 3),
        }

    top = max(raw_scores.values(), default=0.0)
    denom = top if top > 0 else 1.0
    for canon, raw in raw_scores.items():
        results[canon]["score"] = round(raw / denom, 3)
    return results
