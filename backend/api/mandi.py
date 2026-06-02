from dataclasses import asdict
from fastapi import APIRouter, Query
from analysis.crop_catalog import list_all_crops
from analysis.price_source import get_market_prices

router = APIRouter()


@router.get("/mandi/commodities")
def mandi_commodities():
    """Full crop union with per-tool availability flags (powers the picker)."""
    return [asdict(c) for c in list_all_crops()]


@router.get("/mandi/compare")
def mandi_compare(
    commodity: str = Query(...),
    lat: float | None = Query(None),
    lon: float | None = Query(None),
    state: str | None = Query(None),
    rate_per_km: float = Query(0.0, ge=0),
    top: int = Query(10, ge=1, le=50),
):
    return get_market_prices(commodity, lat=lat, lon=lon, state=state,
                             rate_per_km=rate_per_km, top_k=top)
