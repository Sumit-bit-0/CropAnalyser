"""FPO collective-selling engine: does pooling + trucking a group's harvest
beat each farmer selling alone? Pure arithmetic on real mandi_prices +
distances + an editable truck cost (fixed hire + per-km). No invented
premium. Stateless — no DB writes, no HTTP, no React."""
from dataclasses import dataclass
from math import ceil
from analysis.geo import haversine
from analysis.price_source import get_market_prices

SPREAD_THRESHOLD_KM = 200.0


@dataclass
class TransportConfig:
    truck_capacity_q: float = 100.0       # quintals per truckload (~10 tonnes)
    fixed_hire_per_truck: float = 2000.0  # flat hire per truck (Rs)
    per_km_per_truck: float = 30.0        # Rs per km per truck
    per_q_local_rate: float = 2.0         # Rs per quintal per km (individual)


def _centroid(farmers):
    """Mean (lat, lon) of the farmer locations — proxy for the FPO hub."""
    n = len(farmers)
    return (sum(f["lat"] for f in farmers) / n,
            sum(f["lon"] for f in farmers) / n)


def _max_pairwise_km(farmers):
    """Largest great-circle distance between any two members."""
    d = 0.0
    for i in range(len(farmers)):
        for j in range(i + 1, len(farmers)):
            d = max(d, haversine(farmers[i]["lat"], farmers[i]["lon"],
                                 farmers[j]["lat"], farmers[j]["lon"]))
    return d


def _individual_revenue(farmer, markets, per_q_local_rate):
    """Best net revenue for one farmer's lot, carried at a per-quintal local
    rate (no fixed cost). Returns (revenue, chosen_market_or_None)."""
    q = farmer["quantity_q"]
    best = None
    for m in markets:
        d = m["distance_km"]
        if d is None:
            continue
        net = q * (m["modal_price"] - d * per_q_local_rate)
        if best is None or net > best[0]:
            best = (net, m)
    if best is None:
        return 0.0, None
    return best[0], best[1]


def _aggregated_plan(markets, total_q, cfg):
    """Best net revenue for the pooled load, trucked (fixed hire + per-km).
    Returns a plan dict, or None if no market has a usable distance."""
    trucks = ceil(total_q / cfg.truck_capacity_q)
    best = None
    for m in markets:
        d = m["distance_km"]
        if d is None:
            continue
        cost = trucks * (cfg.fixed_hire_per_truck + d * cfg.per_km_per_truck)
        net = total_q * m["modal_price"] - cost
        if best is None or net > best[0]:
            best = (net, m, cost)
    if best is None:
        return None
    net, m, cost = best
    return {
        "revenue": round(net, 2),
        "market": m["market"], "district": m["district"], "state": m["state"],
        "modal_price": m["modal_price"], "distance_km": m["distance_km"],
        "trucks": trucks, "transport_cost": round(cost, 2),
    }


def _make_market_fetcher(crop):
    """Cache candidate markets per rounded (lat, lon) within one request so a
    village of farmers triggers one DB lookup, not one per farmer. top_k is
    large so a farther, higher-priced mandi is never truncated away (see spec)."""
    cache = {}

    def fetch(lat, lon, state):
        key = (round(lat, 2), round(lon, 2))
        if key not in cache:
            cache[key] = get_market_prices(crop, lat=lat, lon=lon, state=state,
                                           rate_per_km=0, top_k=200)
        return cache[key]

    return fetch


def plan_bulk_sale(crop, farmers, cfg=None):
    """Compare pooled+trucked selling against each farmer selling alone.

    farmers: list of {lat, lon, state, quantity_q}.
    Returns a plan dict with baseline, aggregated_rev, extra_income (all None
    when distance optimization isn't possible), chosen_mandi, per_farmer,
    price_basis, spread_warning, and a human-readable message."""
    cfg = cfg or TransportConfig()
    fetch = _make_market_fetcher(crop)

    origin_lat, origin_lon = _centroid(farmers)
    state = next((f.get("state") for f in farmers if f.get("state")), None)
    origin = fetch(origin_lat, origin_lon, state)
    basis = origin["source"]
    crop_name = origin["crop"]
    total_q = sum(f["quantity_q"] for f in farmers)

    if basis != "mandi":
        msg = ("Only a state-level average is available for this crop — "
               "distance-based pooling can't be computed."
               if basis == "state_fallback"
               else "No market or state price data for this crop.")
        return {
            "crop": crop_name, "price_basis": basis, "total_q": round(total_q, 2),
            "baseline": None, "aggregated_rev": None, "extra_income": None,
            "chosen_mandi": None, "per_farmer": [], "spread_warning": None,
            "message": msg,
        }

    baseline = 0.0
    per_farmer = []
    for f in farmers:
        # A per-farmer location with no data yields an empty market list → contributes 0 to baseline (inputs validated at API layer).
        markets = fetch(f["lat"], f["lon"], f.get("state"))["markets"]
        rev, m = _individual_revenue(f, markets, cfg.per_q_local_rate)
        baseline += rev
        per_farmer.append({
            "lat": f["lat"], "lon": f["lon"], "quantity_q": f["quantity_q"],
            "best_market": m["market"] if m else None, "revenue": round(rev, 2),
        })

    agg = _aggregated_plan(origin["markets"], total_q, cfg)
    aggregated_rev = agg["revenue"] if agg else None
    extra = round(aggregated_rev - baseline, 2) if agg else None
    reported_baseline = round(baseline, 2) if agg else None

    spread = _max_pairwise_km(farmers)
    spread_warning = (
        f"Members span ~{round(spread)} km — likely too far to pool into one "
        "truck; treat this plan as optimistic."
        if spread > SPREAD_THRESHOLD_KM else None
    )

    if extra is None:
        msg = "No located market found for this crop."
    elif extra <= 0:
        msg = "Pooling doesn't beat selling locally here — members should sell individually."
    else:
        msg = f"Pooling to {agg['market']} earns the group Rs {extra} more than selling alone."

    return {
        "crop": crop_name, "price_basis": basis, "total_q": round(total_q, 2),
        "baseline": reported_baseline, "aggregated_rev": aggregated_rev,
        "extra_income": extra, "chosen_mandi": agg, "per_farmer": per_farmer,
        "spread_warning": spread_warning, "message": msg,
    }
