import analysis.channel_compare as cc


def _patch(monkeypatch, *, gated, facility, assured, mandi_rows):
    monkeypatch.setattr(cc, "gated_crops", lambda: gated)
    monkeypatch.setattr(cc, "nearest_facility", lambda ft, lat, lon: facility)
    monkeypatch.setattr(cc, "assured_price", lambda crop, year=None: assured)
    monkeypatch.setattr(cc, "compare_markets",
                        lambda crop, lat, lon, rate_per_km, top_k: mandi_rows)


def test_processor_wins_when_near_and_assured_beats_mandi(monkeypatch):
    _patch(monkeypatch,
           gated={"wheat": "flour_mill"},
           facility={"name": "X Flour Mill", "km": 22.0},
           assured={"available": True, "msp": 2425, "basis": "MSP",
                    "premium_pct": 5, "processor_price": 2546.25},
           mandi_rows=[{"is_best_net": True, "net_price": 2270.0, "market": "Patna",
                        "distance_km": 60.0, "modal_price": 2300, "transport_per_q": 30.0}])
    out = cc.compare_channels("wheat", 25.6, 85.1)
    assert out["processor"]["available"] is True
    assert out["mandi"]["available"] is True
    assert out["winner"] == "processor"
    assert out["margin_per_q"] > 0
    # net = 2546.25 - 22*0.5 = 2535.25
    assert out["processor"]["net_price"] == 2535.25


def test_mandi_wins_when_facility_far(monkeypatch):
    _patch(monkeypatch,
           gated={"wheat": "flour_mill"},
           facility={"name": "Far Mill", "km": 200.0},
           assured={"available": True, "msp": 2425, "basis": "MSP",
                    "premium_pct": 5, "processor_price": 2546.25},
           mandi_rows=[{"is_best_net": True, "net_price": 2500.0, "market": "Patna",
                        "distance_km": 10.0, "modal_price": 2510, "transport_per_q": 5.0}])
    out = cc.compare_channels("wheat", 25.6, 85.1)
    # processor net = 2546.25 - 200*0.5 = 2446.25 < 2500
    assert out["winner"] == "mandi"


def test_processor_unavailable_when_no_facility(monkeypatch):
    _patch(monkeypatch,
           gated={"wheat": "flour_mill"},
           facility=None,
           assured={"available": True, "msp": 2425, "basis": "MSP",
                    "premium_pct": 5, "processor_price": 2546.25},
           mandi_rows=[{"is_best_net": True, "net_price": 2270.0, "market": "Patna",
                        "distance_km": 60.0, "modal_price": 2300, "transport_per_q": 30.0}])
    out = cc.compare_channels("wheat", 25.6, 85.1)
    assert out["processor"]["available"] is False
    assert out["winner"] == "mandi"
    assert out["margin_per_q"] is None


def test_processor_unavailable_when_no_msp(monkeypatch):
    _patch(monkeypatch,
           gated={"wheat": "flour_mill"},
           facility={"name": "X", "km": 10.0},
           assured={"available": False, "msp": None, "basis": None,
                    "premium_pct": 5, "processor_price": None},
           mandi_rows=[{"is_best_net": True, "net_price": 2270.0, "market": "Patna",
                        "distance_km": 60.0, "modal_price": 2300, "transport_per_q": 30.0}])
    out = cc.compare_channels("wheat", 25.6, 85.1)
    assert out["processor"]["available"] is False
    assert out["winner"] == "mandi"


def test_both_unavailable_gives_null_winner(monkeypatch):
    _patch(monkeypatch,
           gated={},  # crop not gated -> no facility type
           facility=None,
           assured={"available": False, "msp": None, "basis": None,
                    "premium_pct": 5, "processor_price": None},
           mandi_rows=[])
    out = cc.compare_channels("wheat", 25.6, 85.1)
    assert out["winner"] is None
    assert "cannot" in out["explanation"].lower() or "no" in out["explanation"].lower()
