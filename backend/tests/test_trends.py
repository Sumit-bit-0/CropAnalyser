from analysis.trends import get_price_trend, get_available_filters

def test_get_available_filters():
    result = get_available_filters()
    assert "states" in result
    assert "commodities" in result
    assert isinstance(result["states"], list)

def test_get_price_trend_returns_list():
    filters = get_available_filters()
    if filters["states"] and filters["commodities"]:
        state = filters["states"][0]
        commodity = filters["commodities"][0]
        result = get_price_trend(state, commodity)
        assert isinstance(result, list)

def test_price_trend_fields():
    filters = get_available_filters()
    if filters["states"] and filters["commodities"]:
        result = get_price_trend(filters["states"][0], filters["commodities"][0])
        if result:
            row = result[0]
            assert "period" in row
            assert "farm_gate_price" in row
            assert "modal_price" in row
