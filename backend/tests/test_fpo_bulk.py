import math
import pytest
import analysis.fpo_bulk as fpo
from analysis.fpo_bulk import TransportConfig, _centroid, _max_pairwise_km, _individual_revenue, _aggregated_plan


def test_transport_config_defaults():
    cfg = TransportConfig()
    assert cfg.truck_capacity_q == 100.0
    assert cfg.fixed_hire_per_truck == 2000.0
    assert cfg.per_km_per_truck == 30.0
    assert cfg.per_q_local_rate == 2.0


def test_centroid_is_mean_of_points():
    farmers = [{"lat": 10.0, "lon": 20.0}, {"lat": 12.0, "lon": 24.0}]
    lat, lon = _centroid(farmers)
    assert lat == 11.0
    assert lon == 22.0


def test_max_pairwise_km_zero_for_identical_points():
    farmers = [{"lat": 10.0, "lon": 20.0}, {"lat": 10.0, "lon": 20.0}]
    assert _max_pairwise_km(farmers) == 0.0


def test_max_pairwise_km_positive_for_spread():
    # Punjab-ish to Tamil-Nadu-ish: should be well over 1000 km
    farmers = [{"lat": 31.0, "lon": 75.0}, {"lat": 11.0, "lon": 78.0}]
    assert _max_pairwise_km(farmers) > 1000.0


def test_individual_picks_best_net_at_per_q_rate():
    # rate=3 Rs/q/km. near: 1000-30=970; far: 1200-300=900 -> near wins.
    markets = [
        {"market": "Near", "district": "D1", "state": "S", "modal_price": 1000, "distance_km": 10},
        {"market": "Far", "district": "D2", "state": "S", "modal_price": 1200, "distance_km": 100},
    ]
    rev, chosen = _individual_revenue({"quantity_q": 50}, markets, per_q_local_rate=3.0)
    assert chosen["market"] == "Near"
    assert rev == 50 * (1000 - 10 * 3.0)   # 48500


def test_individual_skips_markets_without_distance():
    markets = [{"market": "NoLoc", "district": "D", "state": "S", "modal_price": 9999, "distance_km": None}]
    rev, chosen = _individual_revenue({"quantity_q": 10}, markets, per_q_local_rate=2.0)
    assert chosen is None
    assert rev == 0.0


def test_aggregated_reaches_farther_premium_mandi():
    cfg = TransportConfig(truck_capacity_q=100, fixed_hire_per_truck=2000,
                          per_km_per_truck=30, per_q_local_rate=3.0)
    markets = [
        {"market": "Near", "district": "D1", "state": "S", "modal_price": 1000, "distance_km": 10},
        {"market": "Far", "district": "D2", "state": "S", "modal_price": 1200, "distance_km": 100},
    ]
    plan = _aggregated_plan(markets, total_q=100, cfg=cfg)
    # Far: 100*1200 - 1*(2000 + 100*30) = 120000 - 5000 = 115000
    assert plan["market"] == "Far"
    assert plan["trucks"] == 1
    assert plan["transport_cost"] == 5000.0
    assert plan["revenue"] == 115000.0


def test_aggregated_truck_count_scales_with_quantity():
    cfg = TransportConfig(truck_capacity_q=100, fixed_hire_per_truck=2000,
                          per_km_per_truck=30)
    markets = [{"market": "M", "district": "D", "state": "S", "modal_price": 1000, "distance_km": 50}]
    plan = _aggregated_plan(markets, total_q=250, cfg=cfg)  # ceil(250/100)=3
    assert plan["trucks"] == 3
    assert plan["transport_cost"] == 3 * (2000 + 50 * 30)   # 10500


def test_aggregated_returns_none_when_no_located_market():
    cfg = TransportConfig()
    markets = [{"market": "X", "district": "D", "state": "S", "modal_price": 1000, "distance_km": None}]
    assert _aggregated_plan(markets, total_q=100, cfg=cfg) is None


def _patch_markets(monkeypatch, markets, source="mandi", crop="testcrop"):
    """Replace get_market_prices with a stub that ignores coords and records
    the top_k it was called with. Returns a calls list (one entry per call)."""
    calls = []

    def stub(crop_arg, lat=None, lon=None, state=None, rate_per_km=0.0, top_k=10):
        calls.append({"lat": lat, "lon": lon, "top_k": top_k})
        return {"source": source, "markets": markets, "crop": crop}

    monkeypatch.setattr(fpo, "get_market_prices", stub)
    return calls


def test_extra_income_is_exact_arithmetic_core_win(monkeypatch):
    markets = [
        {"market": "Near", "district": "D1", "state": "S", "modal_price": 1000, "distance_km": 10},
        {"market": "Far", "district": "D2", "state": "S", "modal_price": 1200, "distance_km": 100},
    ]
    _patch_markets(monkeypatch, markets)
    cfg = fpo.TransportConfig(truck_capacity_q=100, fixed_hire_per_truck=2000,
                              per_km_per_truck=30, per_q_local_rate=3.0)
    farmers = [{"lat": 30.0, "lon": 75.0, "state": "S", "quantity_q": 50},
               {"lat": 30.0, "lon": 75.0, "state": "S", "quantity_q": 50}]
    res = fpo.plan_bulk_sale("testcrop", farmers, cfg)
    # individuals pick Near: 50*(1000-30)=48500 each -> baseline 97000
    # aggregated picks Far: 115000 -> extra 18000
    assert res["price_basis"] == "mandi"
    assert res["baseline"] == 97000.0
    assert res["aggregated_rev"] == 115000.0
    assert res["extra_income"] == 18000.0
    assert res["chosen_mandi"]["market"] == "Far"
    assert all(f["best_market"] == "Near" for f in res["per_farmer"])


def test_honest_loss_when_pooling_does_not_help(monkeypatch):
    # only a near market; small quantities -> truck fixed cost dominates
    markets = [{"market": "Near", "district": "D", "state": "S", "modal_price": 1000, "distance_km": 10}]
    _patch_markets(monkeypatch, markets)
    cfg = fpo.TransportConfig(truck_capacity_q=100, fixed_hire_per_truck=2000,
                              per_km_per_truck=30, per_q_local_rate=3.0)
    farmers = [{"lat": 30.0, "lon": 75.0, "state": "S", "quantity_q": 5},
               {"lat": 30.0, "lon": 75.0, "state": "S", "quantity_q": 5}]
    res = fpo.plan_bulk_sale("testcrop", farmers, cfg)
    # baseline 2*5*970=9700 ; aggregated 10*1000-2300=7700 ; extra -2000
    assert res["extra_income"] == -2000.0
    assert "locally" in res["message"].lower()


def test_single_farmer_pooling_has_no_benefit(monkeypatch):
    markets = [{"market": "Near", "district": "D", "state": "S", "modal_price": 1000, "distance_km": 10}]
    _patch_markets(monkeypatch, markets)
    cfg = fpo.TransportConfig(truck_capacity_q=100, fixed_hire_per_truck=2000,
                              per_km_per_truck=30, per_q_local_rate=3.0)
    res = fpo.plan_bulk_sale("testcrop", [{"lat": 30.0, "lon": 75.0, "state": "S", "quantity_q": 50}], cfg)
    assert res["extra_income"] < 0


def test_spread_warning_triggers_beyond_threshold(monkeypatch):
    markets = [{"market": "Near", "district": "D", "state": "S", "modal_price": 1000, "distance_km": 10}]
    _patch_markets(monkeypatch, markets)
    farmers = [{"lat": 31.0, "lon": 75.0, "state": "Punjab", "quantity_q": 50},
               {"lat": 11.0, "lon": 78.0, "state": "Tamil Nadu", "quantity_q": 50}]
    res = fpo.plan_bulk_sale("testcrop", farmers)
    assert res["spread_warning"] is not None


def test_market_lookup_is_cached_per_rounded_coord(monkeypatch):
    markets = [{"market": "Near", "district": "D", "state": "S", "modal_price": 1000, "distance_km": 10}]
    calls = _patch_markets(monkeypatch, markets)
    farmers = [{"lat": 30.0, "lon": 75.0, "state": "S", "quantity_q": 10} for _ in range(5)]
    fpo.plan_bulk_sale("testcrop", farmers)
    # 5 identical coords + their identical centroid share one cache key -> 1 call
    assert len(calls) == 1


def test_engine_requests_full_market_list_not_nearest_few(monkeypatch):
    markets = [{"market": "M", "district": "D", "state": "S", "modal_price": 1000, "distance_km": 10}]
    calls = _patch_markets(monkeypatch, markets)
    fpo.plan_bulk_sale("testcrop", [{"lat": 30.0, "lon": 75.0, "state": "S", "quantity_q": 10}])
    # high top_k so a farther premium mandi is never truncated away
    assert all(c["top_k"] >= 100 for c in calls)


def test_mandi_source_but_no_distances_reports_none_baseline(monkeypatch):
    # source is "mandi" yet no market has a usable distance -> optimization
    # impossible, so baseline/aggregated/extra are all None (consistent contract)
    markets = [{"market": "X", "district": "D", "state": "S", "modal_price": 1000, "distance_km": None}]
    _patch_markets(monkeypatch, markets)
    res = fpo.plan_bulk_sale("testcrop", [{"lat": 30.0, "lon": 75.0, "state": "S", "quantity_q": 50}])
    assert res["price_basis"] == "mandi"
    assert res["baseline"] is None
    assert res["aggregated_rev"] is None
    assert res["extra_income"] is None
    assert res["chosen_mandi"] is None


def test_state_fallback_crop_skips_optimization(monkeypatch):
    _patch_markets(monkeypatch, markets=[], source="state_fallback", crop="bajra")
    farmers = [{"lat": 30.0, "lon": 75.0, "state": "Punjab", "quantity_q": 50}]
    res = fpo.plan_bulk_sale("bajra", farmers)
    assert res["price_basis"] == "state_fallback"
    assert res["extra_income"] is None
    assert res["aggregated_rev"] is None
    assert res["chosen_mandi"] is None
    assert "state-level" in res["message"].lower()


def test_no_price_data_returns_clean_message(monkeypatch):
    _patch_markets(monkeypatch, markets=[], source="none", crop="unobtanium")
    farmers = [{"lat": 30.0, "lon": 75.0, "state": "Punjab", "quantity_q": 50}]
    res = fpo.plan_bulk_sale("unobtanium", farmers)
    assert res["price_basis"] == "none"
    assert res["extra_income"] is None
    assert "no market" in res["message"].lower()
