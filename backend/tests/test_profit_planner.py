import pandas as pd
from analysis.profit_planner import plan_profit, get_price_reference

BASE = dict(area_acres=2.0, yield_q_per_acre=20.0, input_cost=10000.0,
            labour_cost=5000.0, transport_cost=3000.0, market_price=1500.0)


def test_profit_positive():
    r = plan_profit(**BASE)
    assert r["total_yield_q"] == 40.0
    assert r["total_revenue"] == 60000.0
    assert r["total_cost"] == 18000.0
    assert r["profit"] == 42000.0


def test_break_even_and_target():
    r = plan_profit(**BASE, desired_margin_pct=20)
    assert r["break_even_price"] == 450.0
    assert r["target_sale_price"] == 540.0


def test_recommendation_sell_now():
    r = plan_profit(**BASE)
    assert r["recommendation"].startswith("Sell")


def test_loss_when_price_below_break_even():
    r = plan_profit(**{**BASE, "market_price": 300.0})
    assert r["profit"] < 0
    assert "loss" in r["recommendation"].lower()


def test_zero_yield_guarded():
    r = plan_profit(**{**BASE, "yield_q_per_acre": 0.0})
    assert r["break_even_price"] is None


def test_price_reference_keys():
    r = get_price_reference("Maharashtra", "Onion")
    assert {"latest_price", "avg_price", "volatility_cv", "risk_level"} <= set(r.keys())
    assert r["risk_level"] in ("low", "medium", "high", "unknown")


def test_price_reference_resolves_shared_crop_token(monkeypatch):
    # Same contract as the trend tool: a canonical token from the shared crop
    # picker must resolve to its prices-table name before querying.
    captured = {}

    def fake_query(sql, params):
        captured["commodity"] = params[1]
        return pd.DataFrame({"modal_price": [100.0, 120.0],
                             "year": [2024, 2024], "month": [1, 2]})

    monkeypatch.setattr("analysis.profit_planner.query", fake_query)
    get_price_reference("Maharashtra", "pigeonpeas")
    assert captured["commodity"] == "Arhar (Tur/Red Gram)(Whole)"
