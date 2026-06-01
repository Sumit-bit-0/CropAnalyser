from fastapi.testclient import TestClient
from analysis.geo import haversine, get_centroid, locate
from main import app

client = TestClient(app)


def test_haversine_known_distance():
    # Delhi (28.65, 77.19) to Mumbai (19.07, 72.88) ~ 1150 km
    d = haversine(28.65, 77.19, 19.07, 72.88)
    assert 1100 < d < 1200


def test_haversine_zero():
    assert haversine(20.0, 75.0, 20.0, 75.0) == 0.0


def test_get_centroid_state_fallback():
    # A state always resolves even if the district is unknown
    c = get_centroid("Maharashtra", "NoSuchDistrict12345")
    assert c is not None
    assert 8 < c[0] < 37 and 68 < c[1] < 98  # within India bounds


def test_get_centroid_unknown_state_is_none():
    assert get_centroid("Atlantis", "Nowhere") is None


def test_locate_punjab_coords():
    # Ludhiana, Punjab ~ (30.90, 75.85)
    r = locate(30.90, 75.85)
    assert r["state"] == "Punjab"
    assert r["district"]            # district resolved from the bundled CSV
    assert r["distance_km"] >= 0


def test_locate_karnataka_coords():
    # Bengaluru ~ (12.97, 77.59)
    assert locate(12.97, 77.59)["state"] == "Karnataka"


def test_geo_locate_endpoint():
    r = client.get("/api/geo/locate", params={"lat": 30.90, "lon": 75.85})
    assert r.status_code == 200
    assert r.json()["state"] == "Punjab"


def test_geo_locate_requires_coords():
    assert client.get("/api/geo/locate").status_code == 422
