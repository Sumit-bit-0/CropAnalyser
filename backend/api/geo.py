from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from analysis.geo import locate
from analysis.pincode import resolve_pincode, nearest_pincode

router = APIRouter()


class Coords(BaseModel):
    lat: float
    lon: float


@router.post("/geo/locate")
def geo_locate(body: Coords):
    """Reverse-locate GPS coords. POST (not GET) so the user's precise
    coordinates travel in the request body rather than a URL query string,
    keeping them out of server/proxy access logs and browser history. Prefers
    the nearest bundled pincode (precise area + coords); otherwise falls back to
    the district-centroid locate()."""
    near = nearest_pincode(body.lat, body.lon)
    if near:
        return near
    return locate(body.lat, body.lon)


@router.get("/geo/pincode/{pin}")
def geo_pincode(pin: str):
    """Forward-resolve a 6-digit pincode to {area, district, state, lat, lon}."""
    rec = resolve_pincode(pin)
    if not rec:
        raise HTTPException(status_code=404, detail="Pincode not found")
    return rec
