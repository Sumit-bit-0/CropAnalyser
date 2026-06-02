import pytest

import analysis.pincode as pc


@pytest.fixture(autouse=True)
def _fixture_pincodes(monkeypatch):
    """Inject a tiny offline table so tests never read the bundled CSV."""
    monkeypatch.setattr(pc, "_PINCODES", {
        "851101": {"pincode": "851101", "area": "Begusarai H.O",
                   "district": "Begusarai", "state": "Bihar", "lat": 25.42, "lon": 86.13},
        "141001": {"pincode": "141001", "area": "Ludhiana H.O",
                   "district": "Ludhiana", "state": "Punjab", "lat": 30.91, "lon": 75.85},
    })


def test_resolve_offline_hit():
    r = pc.resolve_pincode("851101")
    assert r["state"] == "Bihar" and r["district"] == "Begusarai"
    assert r["lat"] == 25.42 and r["source"] == "offline"


def test_resolve_rejects_bad_pin():
    assert pc.resolve_pincode("12") is None
    assert pc.resolve_pincode("abcdef") is None
    assert pc.resolve_pincode("") is None


def test_nearest_pincode_picks_closest():
    r = pc.nearest_pincode(30.90, 75.86)   # near Ludhiana
    assert r["pincode"] == "141001"
    assert r["distance_km"] < 5 and r["source"] == "offline"


def test_nearest_pincode_ignores_corrupt_centroids(monkeypatch):
    # Defense in depth: corrupt centroids (out of India's bbox) must never be
    # returned. haversine's radians() aliases huge values to arbitrary globe
    # points, so without a guard a poison row can win "nearest". With only
    # corrupt rows, the function must degrade to None (caller falls back).
    monkeypatch.setattr(pc, "_PINCODES", {
        "000001": {"pincode": "000001", "area": "Poison", "district": "X", "state": "Y",
                   "lat": 33377611.54, "lon": 469168467.49},
        "000002": {"pincode": "000002", "area": "Zero", "district": "X", "state": "Y",
                   "lat": 0.0, "lon": 0.0},
    })
    assert pc.nearest_pincode(30.90, 75.86) is None


def test_resolve_api_fallback(monkeypatch):
    import io, json

    sample = json.dumps([{
        "Status": "Success",
        "PostOffice": [{"Name": "Sample SO", "District": "Patna", "State": "Bihar"}],
    }]).encode()

    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return sample

    monkeypatch.setattr(pc.urllib.request, "urlopen", lambda *a, **k: _Resp())
    monkeypatch.setattr(pc, "get_centroid", lambda s, d: (25.61, 85.14))

    r = pc.resolve_pincode("800001")   # not in the fixture offline table
    assert r["source"] == "api"
    assert r["state"] == "Bihar" and r["district"] == "Patna"
    assert r["lat"] == 25.61 and r["lon"] == 85.14


def test_resolve_api_failure_returns_none(monkeypatch):
    def _boom(*a, **k):
        raise OSError("network down")
    monkeypatch.setattr(pc.urllib.request, "urlopen", _boom)
    assert pc.resolve_pincode("800001") is None


import api.geo as geo_api
from fastapi import HTTPException


def test_route_pincode_found(monkeypatch):
    monkeypatch.setattr(geo_api, "resolve_pincode",
                        lambda pin: {"pincode": pin, "state": "Bihar", "district": "Begusarai",
                                     "area": "Begusarai H.O", "lat": 25.42, "lon": 86.13, "source": "offline"})
    out = geo_api.geo_pincode("851101")
    assert out["state"] == "Bihar" and out["lat"] == 25.42


def test_route_pincode_not_found(monkeypatch):
    monkeypatch.setattr(geo_api, "resolve_pincode", lambda pin: None)
    with pytest.raises(HTTPException) as exc:
        geo_api.geo_pincode("000000")
    assert exc.value.status_code == 404


def test_route_locate_prefers_pincode(monkeypatch):
    monkeypatch.setattr(geo_api, "nearest_pincode",
                        lambda lat, lon: {"pincode": "141001", "state": "Punjab",
                                          "district": "Ludhiana", "area": "Ludhiana H.O",
                                          "lat": 30.91, "lon": 75.85, "distance_km": 2.1, "source": "offline"})
    out = geo_api.geo_locate(30.90, 75.86)
    assert out["pincode"] == "141001" and out["area"] == "Ludhiana H.O"
