from fastapi import APIRouter, Query, HTTPException
from analysis.channel_compare import compare_channels

router = APIRouter()


@router.get("/compare/channels")
def compare_channels_endpoint(
    crop: str = Query(...),
    lat: float | None = Query(None),
    lon: float | None = Query(None),
    area: float | None = Query(None),
    state: str | None = Query(None),
    district: str | None = Query(None),
    season: str | None = Query(None),
    year: int | None = Query(None),
):
    if lat is None or lon is None:
        raise HTTPException(status_code=400,
                            detail="lat and lon are required for a channel comparison")
    return compare_channels(crop, lat, lon, area_ha=area, state=state,
                            district=district, season=season, year=year)
