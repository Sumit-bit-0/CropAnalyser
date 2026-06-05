# backend/tests/test_recommend_smart_autosoil.py
from fastapi.testclient import TestClient
import api.recommend as rec
from main import app

client = TestClient(app)


def test_autosoil_when_no_soil(monkeypatch):
    monkeypatch.setattr(rec, "soil_profile",
        lambda state, district=None, *, coords=None, season=None: {
            "features": {"N": 270, "P": 22, "K": 210, "ph": 7.4,
                         "temperature": 27.0, "humidity": 65.0, "rainfall": 1200.0},
            "soil_source": "district", "climate_source": "weather_api"})
    captured = {}
    def _fake_recommend(**kwargs):
        captured.update(kwargs)
        return {"recommendations": [], "weights_used": {}, "modules_used": []}
    monkeypatch.setattr(rec, "fusion_recommend", _fake_recommend)

    r = client.post("/api/recommend/smart", json={"state": "Bihar", "district": "Gopalganj"})
    assert r.status_code == 200
    body = r.json()
    assert body["soil_source"] == "district"
    assert body["climate_source"] == "weather_api"
    assert captured["features"]["N"] == 270   # auto-derived features were passed through


def test_manual_soil_overrides(monkeypatch):
    called = {"soil_profile": False}
    def _sp(*a, **k):
        called["soil_profile"] = True
        return None
    monkeypatch.setattr(rec, "soil_profile", _sp)
    monkeypatch.setattr(rec, "fusion_recommend",
        lambda **k: {"recommendations": [], "weights_used": {}, "modules_used": []})
    soil = {"N": 1, "P": 2, "K": 3, "temperature": 25, "humidity": 50, "ph": 6.5, "rainfall": 100}
    r = client.post("/api/recommend/smart", json={"state": "Bihar", "soil": soil})
    assert r.status_code == 200
    assert r.json()["soil_source"] == "manual"
    assert called["soil_profile"] is False   # manual path skips auto-derive
