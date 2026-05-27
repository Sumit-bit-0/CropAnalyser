import pandas as pd
from analysis.markup import get_state_markup, get_crop_markup

def test_get_state_markup_returns_list():
    result = get_state_markup()
    assert isinstance(result, list)
    assert len(result) > 0

def test_get_state_markup_fields():
    result = get_state_markup()
    row = result[0]
    assert "state" in row
    assert "avg_markup_pct" in row
    assert "avg_farm_gate" in row
    assert "avg_modal" in row

def test_get_crop_markup_filters_by_crop():
    result = get_crop_markup("Tomato")
    for row in result:
        assert "state" in row
        assert "avg_markup_pct" in row

def test_markup_pct_is_positive():
    result = get_state_markup()
    for row in result:
        assert row["avg_markup_pct"] >= 0
