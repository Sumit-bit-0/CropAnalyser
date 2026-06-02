from fastapi import APIRouter, Query, HTTPException
from analysis.geo import locate
from analysis.pincode import resolve_pincode, nearest_pincode

router = APIRouter()


@router.get("/geo/locate")
def geo_locate(lat: float = Query(...), lon: float = Query(...)):
    """Reverse-locate GPS coords. Prefers the nearest pincode (precise area +
    coords) when the pincode table is bundled; otherwise falls back to the
    district-centroid locate()."""
    near = nearest_pincode(lat, lon)
    if near:
        return near
    return locate(lat, lon)


@router.get("/geo/pincode/{pin}")
def geo_pincode(pin: str):
    """Forward-resolve a 6-digit pincode to {area, district, state, lat, lon}."""
    rec = resolve_pincode(pin)
    if not rec:
        raise HTTPException(status_code=404, detail="Pincode not found")
    return rec
