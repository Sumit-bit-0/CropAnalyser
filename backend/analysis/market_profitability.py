"""Market Profitability scorer for CropAdvisor (fusion input #2).

Scores how favorable the market is for each whitelist crop, from the `prices`
table via the catalog's market aliases. v1 signal = recent modal price level,
risk-adjusted by price volatility, normalized so the best candidate = 1.0:

    raw = recent_price * (1 - volatility_cv)        # high price, low volatility wins
    score = raw / max(raw across candidates)

Prices are read NATIONALLY by default (market prices are largely national and
state-level slices get sparse); pass `state` for a localized read. recent_price /
avg_price / volatility / risk_level are returned for the explanation layer.

KNOWN v1 LIMITATION: absolute ₹/quintal is a coarse profitability proxy — it
favors intrinsically high-priced crops because we lack per-crop cost and
comparable yield. The design's full "Price − Cost − Risk" needs cost data we
don't have yet. The forward-looking LSTM price outlook is computed only for the
final top crops (expensive per call), not here across all candidates.
"""
from database import query
from analysis.crop_catalog import CANONICAL_CROPS, WHITELIST


def _risk_level(cv: float) -> str:
    if cv < 0.15:
        return "low"
    if cv <= 0.30:
        return "medium"
    return "high"


def market_profitability_scores(crops=None, state: str | None = None) -> dict:
    """Map of {canonical_crop: {score 0-1, recent_price, avg_price, volatility_cv, risk_level}}."""
    crops = list(crops) if crops else WHITELIST
    results = {c: {"score": 0.0, "recent_price": None, "avg_price": None,
                   "volatility_cv": None, "risk_level": "unknown"} for c in crops}

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

    # per-canonical: pool its market aliases, derive recent price + volatility
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
        raw = recent_price * max(0.0, 1.0 - cv)
        raw_scores[canon] = raw
        results[canon] = {
            "score": 0.0,  # filled after normalization
            "recent_price": round(recent_price, 2),
            "avg_price": round(avg_price, 2),
            "volatility_cv": round(cv, 3),
            "risk_level": _risk_level(cv),
        }

    top = max(raw_scores.values(), default=0.0)
    denom = top if top > 0 else 1.0
    for canon, raw in raw_scores.items():
        results[canon]["score"] = round(raw / denom, 3)
    return results
