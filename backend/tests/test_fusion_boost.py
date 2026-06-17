import analysis.fusion as fusion
from analysis.fusion import apply_processor_boost, BOOST_CAP


def test_boost_lifts_score_when_processor_wins(monkeypatch):
    monkeypatch.setattr(fusion, "compare_channels", lambda crop, lat, lon: {
        "winner": "processor", "margin_per_q": 300.0,
        "mandi": {"available": True, "net_price": 2270.0},
        "processor": {"available": True, "facility": "X Mill", "distance_km": 20.0},
    })
    new_score, note = apply_processor_boost("wheat", 0.50, 25.6, 85.1)
    assert new_score > 0.50
    assert new_score <= 0.50 * (1 + BOOST_CAP) + 1e-9
    assert "grow-for-industry" in note


def test_no_boost_when_mandi_wins(monkeypatch):
    monkeypatch.setattr(fusion, "compare_channels", lambda crop, lat, lon: {
        "winner": "mandi", "margin_per_q": -100.0,
        "mandi": {"available": True, "net_price": 2400.0},
        "processor": {"available": True, "net_price": 2300.0},
    })
    new_score, note = apply_processor_boost("wheat", 0.50, 25.6, 85.1)
    assert new_score == 0.50
    assert note is None


def test_boost_is_capped(monkeypatch):
    monkeypatch.setattr(fusion, "compare_channels", lambda crop, lat, lon: {
        "winner": "processor", "margin_per_q": 99999.0,
        "mandi": {"available": True, "net_price": 100.0},
        "processor": {"available": True, "facility": "X", "distance_km": 5.0},
    })
    new_score, _ = apply_processor_boost("wheat", 0.50, 25.6, 85.1)
    assert new_score == round(0.50 * (1 + BOOST_CAP), 4)
