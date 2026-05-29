from fastapi import APIRouter, Query
from analysis.mandi_compare import compare_markets, list_commodities

router = APIRouter()


@router.get("/mandi/commodities")
def mandi_commodities():
    return list_commodities()


@router.get("/mandi/compare")
def mandi_compare(
    commodity: str = Query(...),
    lat: float | None = Query(None),
    lon: float | None = Query(None),
    rate_per_km: float = Query(0.0, ge=0),
    top: int = Query(10, ge=1, le=50),
):
    return compare_markets(commodity, lat=lat, lon=lon, rate_per_km=rate_per_km, top_k=top)
