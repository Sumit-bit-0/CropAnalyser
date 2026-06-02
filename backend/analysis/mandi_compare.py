import pandas as pd
from database import query
from analysis.geo import get_centroid, haversine


def _rank_markets(rows: list[dict], lat=None, lon=None, rate_per_km=0.0, top_k=10) -> list[dict]:
    """Pure ranking: attach location/distance/net-price to market rows and sort.

    rows: dicts with state, district, market, variety, modal_price.
    """
    out = []
    have_loc = lat is not None and lon is not None
    for r in rows:
        centroid = get_centroid(r.get("state"), r.get("district"))
        if have_loc and centroid is None:
            continue  # can't place this market relative to the user
        modal = round(float(r["modal_price"]), 2)
        if have_loc:
            dist = round(haversine(lat, lon, centroid[0], centroid[1]), 1)
            transport = round(dist * rate_per_km, 2)
        else:
            dist = None
            transport = 0.0
        out.append({
            "market": r.get("market"), "district": r.get("district"), "state": r.get("state"),
            "variety": r.get("variety"), "modal_price": modal,
            "distance_km": dist, "transport_per_q": transport,
            "net_price": round(modal - transport, 2), "is_best_net": False,
        })

    if have_loc:
        out.sort(key=lambda x: x["distance_km"])
    else:
        out.sort(key=lambda x: x["modal_price"], reverse=True)
    out = out[:top_k]

    if out:
        best = max(out, key=lambda x: x["net_price"])
        best["is_best_net"] = True
    return out


def compare_markets(commodity: str, lat=None, lon=None, rate_per_km=0.0, top_k=10) -> list[dict]:
    df = query(
        """
        SELECT state, district, market, variety, modal_price, price_date
        FROM mandi_prices
        WHERE LOWER(commodity) = LOWER(?)
        """,
        (commodity,),
    )
    if df.empty:
        return []
    # latest modal price per (state, district, market)
    df = df.sort_values("price_date").drop_duplicates(
        subset=["state", "district", "market"], keep="last"
    )
    rows = df.to_dict(orient="records")
    return _rank_markets(rows, lat=lat, lon=lon, rate_per_km=rate_per_km, top_k=top_k)
