# backend/analysis/demand_gate.py
"""Processing-demand gate: a crop that must be processed locally (e.g. sugarcane
-> sugar mill) only ranks high near a facility. Facilities live in the Postgres
processing_units table; the crop -> facility_type mapping in facility_crop_map.
Both are loaded by tools/ingest. Generic by facility type."""
from database import query, table_exists
from analysis.geo import haversine

NEAR_KM, FAR_KM, FLOOR = 50.0, 150.0, 0.2


def gated_crops() -> dict:
    """crop -> required facility_type, for crops we can actually locate.

    Only crops whose facility_type has at least one facility loaded in
    processing_units are returned. A taxonomy entry whose facility_type has zero
    facilities (e.g. flour_mill before any flour mills are ingested) is a data
    gap, NOT a "no demand" signal, so we must not gate — otherwise the crop would
    be penalised everywhere just because we haven't sourced its facilities yet.

    Queried each call (the tables are tiny) to avoid stale caching across
    requests and tests."""
    if not table_exists("facility_crop_map") or not table_exists("processing_units"):
        return {}
    df = query("""
        SELECT crop, facility_type FROM facility_crop_map
        WHERE facility_type IN (SELECT DISTINCT facility_type FROM processing_units)
    """)
    return dict(zip(df["crop"], df["facility_type"]))


# A facility beyond FAR_KM is floored by proximity_factor regardless of its exact
# distance, so prefilter to a generous lat/lon box in SQL instead of fetching and
# Python-looping every facility of the type. ~2 deg covers >=150km across all of
# India (lon at 37N: 2*111*cos37 ~= 177km). The recommender calls this once per
# gated crop, so this turns thousands-of-rows-per-call into a handful (or zero).
_BOX_DEG = 2.0


def nearest_facility(facility_type: str, lat: float, lon: float):
    """{name, km} of the closest facility of this type within ~the gate radius,
    or None. Distance-prefiltered in SQL so it stays fast when called per crop."""
    if not table_exists("processing_units"):
        return None
    df = query("SELECT name, lat, lon FROM processing_units "
               "WHERE facility_type=? AND lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?",
               (facility_type, lat - _BOX_DEG, lat + _BOX_DEG,
                lon - _BOX_DEG, lon + _BOX_DEG))
    best, best_d = None, float("inf")
    for r in df.itertuples(index=False):
        d = haversine(lat, lon, float(r.lat), float(r.lon))
        if d < best_d:
            best_d, best = d, r
    if best is None:
        return None
    return {"name": best.name, "km": round(best_d, 1)}


def proximity_factor(km) -> float:
    """1.0 within NEAR_KM, linear taper to FLOOR at FAR_KM, FLOOR beyond/unknown."""
    if km is None:
        return FLOOR
    if km <= NEAR_KM:
        return 1.0
    if km >= FAR_KM:
        return FLOOR
    frac = (km - NEAR_KM) / (FAR_KM - NEAR_KM)
    return round(1.0 - frac * (1.0 - FLOOR), 4)
