"""Resolve market prices for a crop with a graceful fallback chain:
real mandi markets -> state-level average from the prices table -> none.
The one place the fallback lives; api/mandi.py routes through it."""
from analysis.crop_catalog import resolve_crop
from analysis.mandi_compare import compare_markets
from analysis.geo import normalize_state
from database import query


def _state_avg(prices_name: str, state: str):
    """Average modal price for (state, commodity) at the latest available year,
    or None. Joins on a normalized state name so spelling variants match."""
    target = normalize_state(state)
    states = query("SELECT DISTINCT state FROM prices")
    state_map = {normalize_state(s): s for s in states["state"].tolist()}
    actual = state_map.get(target)
    if not actual:
        return None
    df = query(
        """SELECT modal_price, year, month FROM prices
           WHERE LOWER(commodity) = LOWER(?) AND state = ?
           ORDER BY year DESC, month DESC""",
        (prices_name, actual),
    )
    if df.empty:
        return None
    latest_year = df.iloc[0]["year"]
    recent = df[df["year"] == latest_year]
    return round(float(recent["modal_price"].mean()), 2)


def get_market_prices(crop: str, lat=None, lon=None, state=None,
                      rate_per_km: float = 0.0, top_k: int = 10) -> dict:
    ident = resolve_crop(crop)
    if ident.mandi_name:
        markets = compare_markets(ident.mandi_name, lat=lat, lon=lon,
                                  rate_per_km=rate_per_km, top_k=top_k)
        if markets:
            return {"source": "mandi", "markets": markets, "crop": ident.display_name}
    if ident.prices_name and state:
        avg = _state_avg(ident.prices_name, state)
        if avg is not None:
            return {"source": "state_fallback", "markets": [], "state_avg": avg,
                    "state": state, "crop": ident.display_name}
    return {"source": "none", "markets": [], "crop": ident.display_name}
