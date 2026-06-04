"""Regional Fit scorer for CropAdvisor (fusion input #1).

Turns district_crop_history into a 0-1 "how regionally proven is this crop here"
signal. Statistical lookup, no ML (per the design): a crop scores high in a
location when it has been grown there consistently (many years) and in volume.

Recency window: only the most recent `RECENT_YEARS` of available data count
(relative to the data's latest year), so "traditional/regional" reflects what is
grown there *now*, not what was grown decades ago. A crop that was large 15-20
years ago but has since dropped off no longer scores as regionally proven.

Scope resolution: use district-level history if a district is given and has data,
else fall back to state-level. Scores are normalized so the most-established crop
in the region = 1.0, making "regional fit" relative to what actually thrives there.
Requested crops with no history in scope score 0.0 (the fusion layer can still rely
on suitability + market for them).

avg_yield is reported for explanation but NOT used in the cross-crop score —
yields aren't comparable across different crops/units.
"""
import math

from database import query, table_exists
from analysis.crop_catalog import WHITELIST

# weight split between "grown consistently" and "grown in volume"
W_CONSISTENCY = 0.5
W_VOLUME = 0.5

# Only the most recent N years of data inform the regional/traditional signal.
RECENT_YEARS = 10


def _max_crop_year() -> int | None:
    r = query("SELECT MAX(crop_year) AS m FROM district_crop_history")
    if r.empty or r.iloc[0]["m"] is None:
        return None
    return int(r.iloc[0]["m"])


def _aggregate(extra_where: str, params: tuple):
    df = query(f"""
        SELECT canonical_crop,
               SUM(production)          AS total_production,
               AVG(crop_yield)          AS avg_yield,
               COUNT(DISTINCT crop_year) AS years_grown
        FROM district_crop_history
        WHERE canonical_crop IS NOT NULL {extra_where}
        GROUP BY canonical_crop
    """, params)
    ty = query(f"""
        SELECT COUNT(DISTINCT crop_year) AS n
        FROM district_crop_history
        WHERE canonical_crop IS NOT NULL {extra_where}
    """, params)
    total_years = int(ty.iloc[0]["n"]) if not ty.empty else 0
    return df, total_years


def _empty(crops):
    return {c: {"score": 0.0, "level": "none", "years_grown": 0,
                "total_production": 0.0, "avg_yield": None} for c in crops}


def regional_fit_scores(state: str, district: str | None = None,
                        season: str | None = None, crops=None,
                        recent_years: int = RECENT_YEARS) -> dict:
    """Map of {canonical_crop: {score 0-1, level, years_grown, total_production, avg_yield}}.

    Only the most recent `recent_years` of data (relative to the dataset's latest
    crop_year) are counted, so the signal reflects current growing patterns.
    """
    crops = list(crops) if crops else WHITELIST
    results = _empty(crops)
    if not table_exists("district_crop_history"):
        return results

    season_clause, season_params = "", ()
    if season:
        season_clause, season_params = " AND LOWER(season) = LOWER(?)", (season,)

    # Restrict to the recent window relative to the dataset's latest year.
    recent_clause, recent_params = "", ()
    if recent_years and recent_years > 0:
        max_year = _max_crop_year()
        if max_year is not None:
            recent_clause = " AND crop_year >= ?"
            recent_params = (max_year - (recent_years - 1),)

    tail_clause = season_clause + recent_clause
    tail_params = season_params + recent_params

    df, total_years, level = None, 0, "none"
    if district:
        where = " AND LOWER(state)=LOWER(?) AND LOWER(district)=LOWER(?)" + tail_clause
        df, total_years = _aggregate(where, (state, district) + tail_params)
        if not df.empty:
            level = "district"
    if df is None or df.empty:
        where = " AND LOWER(state)=LOWER(?)" + tail_clause
        df, total_years = _aggregate(where, (state,) + tail_params)
        if not df.empty:
            level = "state"

    if df is None or df.empty or total_years == 0:
        return results

    df = df.copy()
    df["logvol"] = df["total_production"].clip(lower=0).map(lambda v: math.log1p(v))
    max_logvol = df["logvol"].max() or 1.0

    raw = {}
    for r in df.itertuples(index=False):
        consistency = min(r.years_grown / total_years, 1.0)
        volume = r.logvol / max_logvol
        raw[r.canonical_crop] = {
            "combined": W_CONSISTENCY * consistency + W_VOLUME * volume,
            "years_grown": int(r.years_grown),
            "total_production": float(r.total_production),
            "avg_yield": round(float(r.avg_yield), 3) if r.avg_yield is not None else None,
        }

    max_combined = max((v["combined"] for v in raw.values()), default=0.0) or 1.0
    for crop in crops:
        if crop in raw:
            v = raw[crop]
            results[crop] = {
                "score": round(v["combined"] / max_combined, 3),
                "level": level,
                "years_grown": v["years_grown"],
                "total_production": round(v["total_production"], 1),
                "avg_yield": v["avg_yield"],
            }
    return results
