"""Grow-for-industry vs grow-for-mandi channel comparison.

Composes price_reference (assured processor price) + demand_gate.nearest_facility
(distance to a processor) + mandi_compare.compare_markets (best mandi net) and
nets both channels the same way (price - transport) so they compare apples to
apples. An unavailable channel is marked unavailable, never read as 0.
"""
from analysis.price_reference import assured_price
from analysis.demand_gate import gated_crops, nearest_facility
from analysis.mandi_compare import compare_markets
from analysis.yield_predict import predict_yield

# Estimated transport cost, rupees per quintal per km (truck ~100 q at ~Rs.50/km).
# Documented estimate, overridable by the caller. Must be non-zero so distance
# actually affects the net comparison (compare_markets defaults it to 0.0).
DEFAULT_RATE_PER_KM = 0.5


def _processor_channel(crop, lat, lon, year, rate_per_km):
    ftype = gated_crops().get(crop)
    if ftype is None:
        return {"available": False, "reason": "crop has no processing channel"}
    fac = nearest_facility(ftype, lat, lon)
    if fac is None:
        return {"available": False, "reason": f"no {ftype} on record nearby"}
    price = assured_price(crop, year=year)
    if not price["available"]:
        return {"available": False, "reason": "no MSP/FRP on record"}
    transport = round(fac["km"] * rate_per_km, 2)
    net = round(price["processor_price"] - transport, 2)
    return {
        "available": True, "facility": fac["name"], "distance_km": fac["km"],
        "assured_price": price["msp"], "premium_pct": price["premium_pct"],
        "processor_price": price["processor_price"], "basis": price["basis"],
        "transport_per_q": transport, "net_price": net,
    }


def _mandi_channel(crop, lat, lon, rate_per_km):
    rows = compare_markets(crop, lat, lon, rate_per_km=rate_per_km, top_k=10)
    best = next((r for r in rows if r.get("is_best_net")), None)
    if best is None:
        return {"available": False, "reason": "no mandi price"}
    return {
        "available": True, "market": best["market"], "distance_km": best["distance_km"],
        "modal_price": best["modal_price"], "transport_per_q": best["transport_per_q"],
        "net_price": best["net_price"],
    }


def _explain(crop, proc, mandi, winner):
    if winner == "processor":
        base = (f"Processor pays Rs.{proc['processor_price']:.0f}/q "
                f"({proc['basis']} + est. {proc['premium_pct']:.0f}% premium) and nets "
                f"Rs.{proc['net_price']:.0f}/q after {proc['distance_km']} km transport")
        if mandi.get("available"):
            return base + f", vs the best mandi's Rs.{mandi['net_price']:.0f}/q."
        return base + f"; no mandi price available ({mandi.get('reason')})."
    if winner == "mandi":
        m = (f"Best mandi ({mandi['market']}) nets Rs.{mandi['net_price']:.0f}/q")
        if proc.get("available"):
            return m + f" vs the processor's Rs.{proc['net_price']:.0f}/q."
        return m + f"; processor channel unavailable ({proc.get('reason')})."
    return "No comparison possible: neither a processor nor a mandi price is available."


def compare_channels(crop, lat, lon, *, area_ha=None, state=None, district=None,
                     season=None, year=None, rate_per_km=DEFAULT_RATE_PER_KM):
    proc = _processor_channel(crop, lat, lon, year, rate_per_km)
    mandi = _mandi_channel(crop, lat, lon, rate_per_km)

    if proc.get("available") and mandi.get("available"):
        winner = "processor" if proc["net_price"] >= mandi["net_price"] else "mandi"
        margin = round(proc["net_price"] - mandi["net_price"], 2)
    elif proc.get("available"):
        winner, margin = "processor", None
    elif mandi.get("available"):
        winner, margin = "mandi", None
    else:
        winner, margin = None, None

    total = None
    if margin is not None and area_ha and state and season is not None:
        y = predict_yield(state, district, season, crop, year or 2024)
        yq = y.get("predicted_yield")
        if yq:
            total = {"area_ha": area_ha, "yield_q_per_ha": yq,
                     "value": round(margin * yq * area_ha, 2), "estimate": True}

    return {
        "crop": crop, "processor": proc, "mandi": mandi,
        "winner": winner, "margin_per_q": margin, "total_advantage": total,
        "explanation": _explain(crop, proc, mandi, winner),
    }
