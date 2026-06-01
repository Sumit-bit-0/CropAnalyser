from fastapi import APIRouter, Query
from analysis.geo import locate

router = APIRouter()


@router.get("/geo/locate")
def geo_locate(lat: float = Query(...), lon: float = Query(...)):
    """Reverse-locate GPS coordinates to the nearest state/district."""
    return locate(lat, lon)
