from analysis import mandi_compare as mc

# Three markets with controlled coordinates via monkeypatched get_centroid.
ROWS = [
    {"state": "S", "district": "Near", "market": "NearMkt", "variety": "v", "modal_price": 1000},
    {"state": "S", "district": "Mid", "market": "MidMkt", "variety": "v", "modal_price": 1200},
    {"state": "S", "district": "Far", "market": "FarMkt", "variety": "v", "modal_price": 1500},
]
COORDS = {"Near": (20.0, 75.0), "Mid": (20.5, 75.0), "Far": (22.0, 75.0)}


def _fake_centroid(state, district):
    return COORDS.get(district)


def test_rank_sorts_nearest_first(monkeypatch):
    monkeypatch.setattr(mc, "get_centroid", _fake_centroid)
    out = mc._rank_markets(ROWS, lat=20.0, lon=75.0, rate_per_km=0.0, top_k=10)
    assert [r["market"] for r in out] == ["NearMkt", "MidMkt", "FarMkt"]
    assert out[0]["distance_km"] == 0.0


def test_net_price_subtracts_transport(monkeypatch):
    monkeypatch.setattr(mc, "get_centroid", _fake_centroid)
    out = mc._rank_markets(ROWS, lat=20.0, lon=75.0, rate_per_km=2.0, top_k=10)
    near = next(r for r in out if r["market"] == "NearMkt")
    assert near["transport_per_q"] == 0.0
    assert near["net_price"] == 1000.0
    far = next(r for r in out if r["market"] == "FarMkt")
    assert far["transport_per_q"] > 0
    assert far["net_price"] == round(1500 - far["transport_per_q"], 2)


def test_best_net_flagged(monkeypatch):
    monkeypatch.setattr(mc, "get_centroid", _fake_centroid)
    out = mc._rank_markets(ROWS, lat=20.0, lon=75.0, rate_per_km=0.0, top_k=10)
    best = [r for r in out if r["is_best_net"]]
    assert len(best) == 1
    assert best[0]["market"] == "FarMkt"  # highest modal, no transport


def test_skip_markets_without_location(monkeypatch):
    monkeypatch.setattr(mc, "get_centroid", lambda s, d: None)
    out = mc._rank_markets(ROWS, lat=20.0, lon=75.0, rate_per_km=0.0, top_k=10)
    assert out == []


def test_no_location_sorts_by_price(monkeypatch):
    monkeypatch.setattr(mc, "get_centroid", _fake_centroid)
    out = mc._rank_markets(ROWS, lat=None, lon=None, top_k=10)
    assert out[0]["modal_price"] == 1500.0  # highest first
    assert out[0]["distance_km"] is None
