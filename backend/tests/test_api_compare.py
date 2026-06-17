from fastapi.testclient import TestClient
import api.compare as compare_api
from main import app

client = TestClient(app)


def test_missing_coords_returns_400():
    r = client.get("/api/compare/channels", params={"crop": "wheat"})
    assert r.status_code == 400


def test_happy_path_returns_payload(monkeypatch):
    monkeypatch.setattr(compare_api, "compare_channels",
                        lambda *a, **k: {"crop": "wheat", "winner": "processor",
                                         "margin_per_q": 265.0, "processor": {"available": True},
                                         "mandi": {"available": True}, "total_advantage": None,
                                         "explanation": "ok"})
    r = client.get("/api/compare/channels",
                   params={"crop": "wheat", "lat": 25.6, "lon": 85.1, "area": 2.0})
    assert r.status_code == 200
    assert r.json()["winner"] == "processor"
